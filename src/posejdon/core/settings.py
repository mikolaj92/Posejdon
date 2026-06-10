from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from posejdon.core.constants import (
    DEFAULT_ENV,
    DEFAULT_LLM_MAX_INPUT_TOKENS,
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    DEFAULT_LLM_MAX_REVIEW_SEGMENTS,
    DEFAULT_LLM_MAX_VERIFICATION_SEGMENTS,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_SEGMENT_MAX_CHARS,
    DEFAULT_POLICY_PROFILE,
    DEFAULT_STORAGE_ROOT,
)
from posejdon.core.enums import LLMProfile, ProcessingMode


class PosejdonSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSEJDON_", extra="ignore")

    env: str = DEFAULT_ENV
    storage_root: str = DEFAULT_STORAGE_ROOT
    default_policy: str = DEFAULT_POLICY_PROFILE
    enable_llm: bool = True
    llm_required: bool = False
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str = DEFAULT_LLM_MODEL
    llm_profile: LLMProfile | None = None
    processing_mode: ProcessingMode | None = None
    debug_continue_on_renderer_failure: bool | None = None
    llm_max_input_tokens: int = Field(default=DEFAULT_LLM_MAX_INPUT_TOKENS, ge=256, le=8192)
    llm_max_output_tokens: int = Field(default=DEFAULT_LLM_MAX_OUTPUT_TOKENS, ge=64, le=4096)
    llm_segment_max_chars: int = Field(default=DEFAULT_LLM_SEGMENT_MAX_CHARS, ge=256, le=40000)
    llm_max_review_segments: int = Field(default=DEFAULT_LLM_MAX_REVIEW_SEGMENTS, ge=1, le=2048)
    llm_max_verification_segments: int = Field(
        default=DEFAULT_LLM_MAX_VERIFICATION_SEGMENTS,
        ge=1,
        le=4096,
    )
    mlx_model_path: str | None = None
    enable_presidio: bool = True
    enable_gliner: bool = True
    enable_spacy: bool = True
    require_presidio: bool = False
    require_gliner: bool = False
    require_spacy: bool = False
    vault_hmac_key: str | None = None
    vault_retention_days: int | None = None
    regex_catalog_path: str = "storage/regex_catalog.sqlite3"
    log_level: str = "INFO"
    strip_metadata: bool = True
    allow_file_path: bool = False
