"""
AutoPatch Background Worker Process (backend/app/workers/worker.py)
Handles asynchronous documentation ingestion, health-check polling,
and resumable LangGraph repair execution via Redis queues with in-memory fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from backend.app.agents.workflow import LangGraphOrchestrator, compute_sha256_hash
    from backend.app.sandbox.runner import IsolatedSandboxRunner
except ImportError:
    from app.agents.workflow import LangGraphOrchestrator, compute_sha256_hash
    from app.sandbox.runner import IsolatedSandboxRunner

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] [autopatch-worker] %(message)s",
)
logger = logging.getLogger("autopatch.worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2.0"))
QUEUE_KEY = "autopatch:jobs:queue"


class AutoPatchWorker:
    def __init__(self) -> None:
        self.running = True
        self.redis_client: Any = None
        self.local_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.sandbox_runner = IsolatedSandboxRunner(timeout_seconds=15)
        self.orchestrator = LangGraphOrchestrator(sandbox_runner=self.sandbox_runner)

    async def connect_redis(self) -> bool:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await client.ping()
            self.redis_client = client
            logger.info("Connected to Redis job queue at %s", REDIS_URL)
            return True
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s). Running worker in local async queue fallback mode.",
                exc,
            )
            self.redis_client = None
            return False

    async def enqueue_job(self, job_type: str, payload: Dict[str, Any]) -> str:
        job_id = f"job_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        job = {
            "job_id": job_id,
            "job_type": job_type,
            "payload": payload,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.redis_client is not None:
            await self.redis_client.rpush(QUEUE_KEY, json.dumps(job))
        else:
            await self.local_queue.put(job)
        logger.info("Enqueued job %s (%s)", job_id, job_type)
        return job_id

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = job.get("job_id", "unknown")
        job_type = job.get("job_type", "")
        payload = job.get("payload", {})
        logger.info("Processing job %s [type=%s]", job_id, job_type)

        if job_type == "INGEST_DOCUMENT":
            content = str(payload.get("content", ""))
            content_hash = compute_sha256_hash(content)
            chunks = [p.strip() for p in content.split("\n\n") if p.strip()]
            logger.info(
                "Document ingested: title=%s hash=%s chunks=%d",
                payload.get("title", "Untitled"),
                content_hash,
                len(chunks),
            )
            return {"status": "INDEXED", "content_hash": content_hash, "chunk_count": len(chunks)}

        if job_type == "EXECUTE_LANGGRAPH_REPAIR":
            incident = payload.get("incident", {})
            integration = payload.get("integration", {})
            docs = payload.get("documentation_sources", [])
            result = self.orchestrator.execute_until_human_checkpoint(
                incident=incident,
                integration=integration,
                documentation_sources=docs,
            )
            logger.info(
                "Completed LangGraph repair checkpoint for incident=%s state=%s",
                incident.get("id"),
                result.get("state"),
            )
            return result

        logger.warning("Unknown job_type=%s for job_id=%s", job_type, job_id)
        return {"status": "SKIPPED", "reason": f"Unsupported job_type: {job_type}"}

    async def run_forever(self) -> None:
        await self.connect_redis()
        logger.info("AutoPatch Worker started (poll_interval=%ss)", POLL_INTERVAL)
        while self.running:
            try:
                job_raw: Optional[str] = None
                if self.redis_client is not None:
                    res = await self.redis_client.blpop(QUEUE_KEY, timeout=int(POLL_INTERVAL) or 1)
                    if res:
                        _, job_raw = res
                else:
                    try:
                        job_obj = await asyncio.wait_for(
                            self.local_queue.get(), timeout=POLL_INTERVAL
                        )
                        await self.process_job(job_obj)
                    except asyncio.TimeoutError:
                        pass

                if job_raw:
                    job_obj = json.loads(job_raw)
                    await self.process_job(job_obj)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in worker loop: %s", exc, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

        if self.redis_client is not None:
            await self.redis_client.aclose()
        logger.info("AutoPatch Worker shut down cleanly.")

    def stop(self) -> None:
        self.running = False


async def main() -> None:
    worker = AutoPatchWorker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
