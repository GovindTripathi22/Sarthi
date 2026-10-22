from __future__ import annotations

import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = False
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./autopatch_local.db")
    
    # Security & Auth
    secret_key: str = os.getenv("SECRET_KEY", "autopatch-insecure-dev-secret-key-change-in-prod-32bytes")
    token_expire_minutes: int = 60 * 24  # 24 hours
    allow_local_proxy: bool = True  # Allowed in development; strictly disabled in production
    
    # LLM Settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "deterministic_demo")  # deterministic_demo | gemini | openai
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    
    # GitHub Integration
    github_token: Optional[str] = os.getenv("GITHUB_TOKEN", None)
    github_owner: str = os.getenv("GITHUB_OWNER", "GovindTripathi22")
    github_repo: str = os.getenv("GITHUB_REPO", "Sarthi")
    github_base_branch: str = os.getenv("GITHUB_BASE_BRANCH", "main")
    
    # Sandbox Settings
    sandbox_mode: str = "subprocess"  # subprocess | docker
    sandbox_timeout_seconds: int = 15
    sandbox_image: str = "autopatch/sandbox-py312:1.4"
    
    # Deployment Settings
    staging_target_url: Optional[str] = os.getenv("STAGING_TARGET_URL", None)
    production_target_url: Optional[str] = os.getenv("PRODUCTION_TARGET_URL", None)


settings = Settings()
