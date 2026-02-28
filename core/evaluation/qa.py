import logging
from typing import Dict, Any, List
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class QualityAssessor:
    """
    Programmatic evaluator that enforces exact schema structures
    and rubrics before Outputs are allowed to pass up the OS architecture.
    """

    def __init__(self):
        pass

    def evaluate_output_schema(
        self, output: Dict[str, Any], required_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Validates that an arbitrary dictionary conforms to a required baseline shape.
        """
        missing_keys = [k for k in required_keys if k not in output]

        if missing_keys:
            logger.warning(f"QA REJECTED payload: Missing required keys -> {missing_keys}")
            return {
                "passed": False,
                "reason": f"Missing required keys: {', '.join(missing_keys)}",
                "output": output,
            }

        logger.debug("QA APPROVED payload shape.")
        return {
            "passed": True,
            "reason": "Payload meets baseline validation schema.",
            "output": output,
        }
