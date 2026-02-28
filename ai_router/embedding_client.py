import httpx
from typing import Union, List


class EmbeddingClient:
    """Client to interface with the distributed embedding servers dynamically."""

    def __init__(self, host: str = "http://localhost", default_layer_ports: dict = None):
        if default_layer_ports is None:
            self.layer_ports = {"routing": 9100, "knowledge": 9100, "code": 9200}
        else:
            self.layer_ports = default_layer_ports
        self.host = host.rstrip("/")

    async def embed(
        self, text: Union[str, List[str]], layer: str
    ) -> Union[List[float], List[List[float]]]:
        """Fetch embeddings from the dedicated microservice port based on the requested layer."""
        port = self.layer_ports.get(layer)
        if not port:
            raise ValueError(f"Unknown layer: {layer}")

        url = f"{self.host}:{port}/api/embed"

        # The Code specific port has a different route
        if layer == "code":
            url = f"{self.host}:{port}/api/embed/code"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"text": text, "layer": layer}, timeout=120.0)
            response.raise_for_status()
            data = response.json()
            return data["embeddings"]
