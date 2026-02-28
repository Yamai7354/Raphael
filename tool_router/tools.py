import os
import subprocess
from typing import Protocol, runtime_checkable
from duckduckgo_search import DDGS

@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    
    def run(self, **kwargs) -> str: ...

class FileTool:
    name = "file_tool"
    description = "Read, write, list files. Actions: read, write, list, delete. Args: path, content (for write)."

    def run(self, action: str, path: str, content: str = "") -> str:
        try:
            if action == "read":
                with open(path, "r") as f:
                    return f.read()
            elif action == "write":
                with open(path, "w") as f:
                    f.write(content)
                return f"Successfully wrote to {path}"
            elif action == "list":
                return "\n".join(os.listdir(path)) if os.path.exists(path) else "Path not found"
            elif action == "delete":
                os.remove(path)
                return f"Deleted {path}"
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Error: {e}"

class ShellTool:
    name = "shell_tool"
    description = "Execute shell commands. Args: command."

    def run(self, command: str) -> str:
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return f"Stdout: {result.stdout}\nStderr: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {e}"

class WebTool:
    name = "web_tool"
    description = "Search the internet using DuckDuckGo. Args: query."

    def run(self, query: str) -> str:
        try:
            results = DDGS().text(query, max_results=5)
            return "\n".join([f"{r['title']}: {r['href']}\n{r['body']}" for r in results])
        except Exception as e:
            return f"Search error: {e}"
