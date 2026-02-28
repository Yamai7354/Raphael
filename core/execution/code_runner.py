import logging
import subprocess
import tempfile
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SandboxedCodeRunner:
    """
    Executes Python logic directly from strings.
    Writes the logic to a secure temporary file, executes it as an isolated subprocess,
    and streams back stdout, stderr, and the return code.
    """

    def __init__(self):
        self.executables = {"python": "python3"}

    def execute_script(self, language: str, code_content: str, timeout: int = 15) -> Dict[str, Any]:
        """Runs the raw string logic and returns standard outputs."""
        if language not in self.executables:
            logger.error(f"CodeRunner lacks execution environment for language: {language}")
            return {"stdout": "", "stderr": f"Unsupported Language: {language}", "exit_code": 1}

        logger.info(
            f"CodeRunner preparing to execute {language} logic block (Length: {len(code_content)} chars)"
        )

        # Write to a transient tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as tmp:
                tmp.write(code_content)
                tmp_path = tmp.name
        except Exception as e:
            logger.error(f"Failed to provision temp script environment: {str(e)}")
            return {"stdout": "", "stderr": str(e), "exit_code": 1}

        try:
            # We strictly execute the file, NO shell injection
            result = subprocess.run(
                [self.executables[language], tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"Script runtime exceeded maximum {timeout}s allowance.")
            return {"stdout": "", "stderr": "TIMEOUT EXPIRED", "exit_code": 124}
        finally:
            # Clean up the artifact
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
