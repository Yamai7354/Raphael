from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import os


class SandboxConfig(BaseModel):
    """
    Defines the strict operational boundaries for the Raphael System.
    """

    allowed_directories: List[str] = Field(
        default_factory=lambda: [os.getcwd()],
        description="Absolute paths that the system is allowed to read from or write to.",
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None,
        description="List of allowed HTTP domains. If None, all domains are allowed except blocked ones.",
    )
    blocked_domains: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0"],
        description="List of domains the system is strictly forbidden to contact.",
    )
    max_memory_mb: int = Field(
        default=1024, description="Maximum memory allocated to sandbox processes in MB."
    )
    max_cpu_percent: int = Field(
        default=80, description="Maximum CPU percentage allocated to sandbox processes."
    )

    @field_validator("allowed_directories", mode="before")
    @classmethod
    def ensure_absolute_paths(cls, v):
        if v is None:
            return v
        return [os.path.abspath(os.path.expanduser(p)) for p in v]

    def is_path_allowed(self, target_path: str) -> bool:
        """Helper to verify if a path falls within the allowed sandbox boundaries."""
        abs_target = os.path.abspath(os.path.expanduser(target_path))
        for allowed_dir in self.allowed_directories:
            if abs_target.startswith(allowed_dir):
                return True
        return False

    def is_domain_allowed(self, domain: str) -> bool:
        """Helper to verify if a network domain is permitted."""
        for blocked in self.blocked_domains:
            if blocked in domain:
                return False

        if self.allowed_domains is not None:
            for allowed in self.allowed_domains:
                if allowed in domain:
                    return True
            return False

        return True
