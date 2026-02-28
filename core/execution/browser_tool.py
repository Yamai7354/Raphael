import logging
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup

from core.execution.tool_registry import BaseTool

logger = logging.getLogger(__name__)


class WebBrowserTool(BaseTool):
    """
    Allows agents to access the internet and read web pages.
    """

    def __init__(self):
        super().__init__(
            name="web_browser",
            description="Fetches and extracts text content from a given URL.",
        )
        # We can add a custom user-agent to avoid basic 403 Forbidden errors
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url")
        if not url:
            return {"error": "Missing required parameter: 'url'"}

        timeout = params.get("timeout", 15)

        try:
            logger.info(f"WebBrowserTool fetching URL: {url}")
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()  # Check for HTTP HTTP errors

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove scripts and styles
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()

            # Get text
            text = soup.get_text(separator=" ", strip=True)

            # Truncate if the text is excessively long to save context window
            # (e.g., limit to ~8000 characters)
            max_length = 8000
            if len(text) > max_length:
                text = text[:max_length] + "... [Content Truncated due to length]"

            return {"url": url, "content": text, "status": response.status_code}

        except requests.exceptions.RequestException as e:
            logger.error(f"WebBrowserTool failed to fetch {url}: {e}")
            return {"error": f"Failed to fetch {url}: {str(e)}"}
