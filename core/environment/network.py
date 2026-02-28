import httpx
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from core.environment.constraints import SandboxConfig


class NetworkAccessor:
    """
    Handles all external HTTP requests and API integrations.
    Strictly adheres to URL policies defined in SandboxConfig.
    """

    def __init__(self, config: SandboxConfig, timeout: int = 10):
        self.config = config
        self.timeout = timeout

    def _validate_url(self, url: str):
        """Ensures the domain is permitted by the sandbox configuration."""
        parsed = urlparse(url)
        domain = parsed.hostname or ""

        if not self.config.is_domain_allowed(domain):
            raise PermissionError(
                f"Network Access Denied: The domain '{domain}' is blocked by sandbox constraints."
            )

    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Performs a GET request to the specified URL securely.
        Returns the raw text content and status code.
        """
        self._validate_url(url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return {"url": url, "status_code": response.status_code, "content": response.text}
            except httpx.HTTPError as e:
                return {
                    "url": url,
                    "status_code": getattr(e.response, "status_code", 500)
                    if hasattr(e, "response")
                    else 500,
                    "error": str(e),
                }

    async def web_search(self, query: str) -> Dict[str, Any]:
        """
        Placeholder for web search capability.
        Would normally integrate with Tavily or DuckDuckGo here.
        """
        # A full integration would connect to a specific tool, but for base Layer 1
        # we provide the interface definition.
        return {
            "query": query,
            "results": [
                {
                    "title": "Search Setup",
                    "link": "https://example.com",
                    "snippet": "Integration pending Phase 5.",
                }
            ],
        }
