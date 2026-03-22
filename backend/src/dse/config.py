from __future__ import annotations

import logging
import sys

import structlog
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud (GCS only — Elasticsearch replaced Vertex AI Search)
    google_cloud_project: str = ""

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "dse-memories"
    elasticsearch_vector_dims: int = 3072

    # Gemini
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-3.1-flash-lite-preview"
    gemini_embedding_model: str = "gemini-embedding-2-preview"

    # GCS / MinIO
    gcs_bucket_name: str = "dse-memories"
    storage_endpoint_url: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_working_memory_ttl_seconds: int = 7200
    redis_cache_ttl_seconds: int = 300

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "dse-local"
    temporal_task_queue: str = "dse-main"

    # Kafka / Redpanda
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_memory_events: str = "dse.memory.events"
    kafka_topic_cdc_events: str = "dse.cdc.events"
    kafka_consumer_group: str = "dse-mma-workers"

    # Phase 2 algorithm settings
    contradiction_cosine_threshold: float = 0.92
    contradiction_auto_resolve_confidence_delta: float = 0.30
    graph_default_hop_depth: int = 1
    graph_max_hop_depth: int = 3

    # Phase 3: Semantic Compression
    compression_min_cluster_size: int = 5
    compression_min_avg_confidence: float = 0.70
    compression_similarity_threshold: float = 0.75
    compression_lookback_days: int = 30
    compression_source_importance_decay: float = 0.5

    # Phase 3: Prospective Memory
    prospective_scan_interval_seconds: int = 60
    prospective_archive_after_days: int = 7

    # Phase 3: Relation Discovery
    discovery_similarity_threshold: float = 0.75
    discovery_min_llm_confidence: float = 0.70
    discovery_max_pairs_per_batch: int = 200

    # Phase 3: Temporal Reasoning
    temporal_window_days: int = 7

    # Phase 3: Importance Estimator
    importance_score_min: float = 0.05
    importance_score_max: float = 1.0
    importance_user_access_recovery: float = 0.15
    importance_agent_access_recovery: float = 0.05

    # Application
    app_env: str = "local"
    use_mock_llm: bool = False
    use_mock_search: bool = False
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Security
    jwt_secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:3000"

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        if self.is_production:
            if self.jwt_secret_key == "change-me-in-production":
                raise ValueError("JWT_SECRET_KEY must be changed in production")
            if not self.gemini_api_key and not self.use_mock_llm:
                raise ValueError("GEMINI_API_KEY is required when USE_MOCK_LLM=false")
        return self


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with appropriate renderer for the environment."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if settings.is_local:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


settings = Settings()
