"use client";

import React, { useEffect, useState } from "react";
import { z } from "zod";

const HealthSchema = z.object({
  status: z.string(),
  version: z.string().optional(),
  workspace_id: z.string().optional(),
  tables_initialized: z.number().optional(),
});

type HealthState = z.infer<typeof HealthSchema> | null;

export default function AutoPatchWorkbenchPage() {
  const [backendHealth, setBackendHealth] = useState<HealthState>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/health`)
      .then((res) => res.json())
      .then((data) => {
        const parsed = HealthSchema.safeParse(data);
        if (parsed.success) {
          setBackendHealth(parsed.data);
        }
      })
      .catch(() => {
        setBackendHealth(null);
      });
  }, [apiUrl]);

  return (
    <main style={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          height: "36px",
          backgroundColor: "#0b0f19",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          fontSize: "12px",
          fontFamily: "monospace",
        }}
      >
        <span>AutoPatch Next.js App Router Shell (Strict TypeScript + Zod)</span>
        <span style={{ color: backendHealth ? "#10b981" : "#f59e0b" }}>
          {backendHealth
            ? `FastAPI Connected (${backendHealth.status} • ${backendHealth.tables_initialized ?? 21} tables)`
            : "Standalone Local Fixture Mode"}
        </span>
      </header>
      <iframe
        src="/api/workbench-ui"
        title="AutoPatch Self-Healing Middleware Workbench"
        style={{ flex: 1, width: "100%", border: "none" }}
      />
    </main>
  );
}
