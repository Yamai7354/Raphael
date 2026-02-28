import os
import aiofiles
from core.environment.constraints import SandboxConfig


class SecureFileSystem:
    """
    Interacts with the local file system while strictly adhering to the SandboxConfig.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config

    def _validate_path(self, file_path: str) -> str:
        """Ensures the requested path is within the sandbox boundaries."""
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not self.config.is_path_allowed(abs_path):
            raise PermissionError(
                f"Access Denied: The path '{file_path}' is outside the allowed sandbox directories."
            )
        return abs_path

    async def read_file(self, file_path: str) -> str:
        """Reads a text file asynchronously if permitted."""
        valid_path = self._validate_path(file_path)
        if not os.path.exists(valid_path):
            raise FileNotFoundError(f"File not found: {valid_path}")

        async with aiofiles.open(valid_path, mode="r") as f:
            content = await f.read()
        return content

    async def write_file(self, file_path: str, content: str) -> str:
        """Writes to a text file asynchronously if permitted. Creates directories if needed."""
        valid_path = self._validate_path(file_path)

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(valid_path), exist_ok=True)

        async with aiofiles.open(valid_path, mode="w") as f:
            await f.write(content)

        return valid_path

    def list_directory(self, dir_path: str) -> list[str]:
        """Lists contents of a directory if permitted."""
        valid_path = self._validate_path(dir_path)
        if not os.path.isdir(valid_path):
            raise NotADirectoryError(f"Directory not found: {valid_path}")

        return os.listdir(valid_path)
