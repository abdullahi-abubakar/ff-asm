"""
Central configuration.
All runtime values come from environment variables so the suite
works locally (BASE_URL=http://localhost:8080) and inside Docker
(BASE_URL=http://api:8080) without touching a single line of code.
"""
import os
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class User:
    username: str
    password: str

    def __repr__(self) -> str:
        return f"User({self.username})"

    @property
    def auth(self) -> Tuple[str, str]:
        """Ready-made tuple for requests auth="""
        return (self.username, self.password)


@dataclass(frozen=True)
class Settings:
    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #
    base_url: str = field(
        default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
    )

    # ------------------------------------------------------------------ #
    # Pre-populated test users (from exercise spec)
    # ------------------------------------------------------------------ #
    user1: User = field(default_factory=lambda: User("test1", "test123"))
    user2: User = field(default_factory=lambda: User("test2", "test456"))

    # ------------------------------------------------------------------ #
    # API surface (from swagger doc)
    # ------------------------------------------------------------------ #
    api_base: str = "/api/v1"
    swagger_json_path: str = "/swagger/doc.json"
    request_timeout: int = 10

    # ------------------------------------------------------------------ #
    # Load-test thresholds
    # ------------------------------------------------------------------ #
    load_users: int = 50
    load_spawn_rate: int = 10
    load_run_time: str = "60s"
    max_p95_ms: int = 1_000       # p95 must be under 1 s
    max_error_rate: float = 0.01  # < 1 % failures

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def swagger_url(self) -> str:
        return f"{self.base_url}{self.swagger_json_path}"

    @property
    def integrations_url(self) -> str:
        return f"{self.base_url}{self.api_base}/integrations"

    @property
    def assets_url(self) -> str:
        return f"{self.base_url}{self.api_base}/assets"

    def url(self, path: str) -> str:
        return f"{self.base_url}{self.api_base}{path}"


settings = Settings()