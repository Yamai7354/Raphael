import re
import logging
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger("ai_router.ethics")


class EthicalGuardrail(str, Enum):
    DATA_PRIVACY = "data_privacy"
    SYSTEM_INTEGRITY = "system_integrity"
    NON_MALICIOUS = "non_malicious"
    HUMAN_CONSENT = "human_consent"
    IP_PROTECTION = "ip_protection"


class ConstraintResult(BaseModel):
    is_safe: bool
    violations: List[EthicalGuardrail] = []
    reasoning: Optional[str] = None


class EthicalValidator:
    """
    Validates tasks against ethical guardrails using pattern matching and heuristics.
    """

    # Patterns that trigger specific guardrails
    PATTERNS = {
        EthicalGuardrail.DATA_PRIVACY: [
            r"extract.*password",
            r"read.*ssh.*key",
            r"dump.*credentials",
            r"list.*users.*tokens",
            r"access.*private.*data",
        ],
        EthicalGuardrail.SYSTEM_INTEGRITY: [
            r"delete.*all.*logs",
            r"wipe.*disk",
            r"format.*drive",
            r"disable.*firewall",
            r"shutdown.*production",
            r"remove.*critical.*configs",
        ],
        EthicalGuardrail.NON_MALICIOUS: [
            r"ddos",
            r"inject.*malware",
            r"create.*backdoor",
            r"exploit.*vulnerability",
            r"brute.*force",
        ],
        EthicalGuardrail.HUMAN_CONSENT: [
            r"manipulate.*user",
            r"deceive",
            r"impersonate.*without.*consent",
        ],
    }

    def validate_objective(
        self, objective: str, constraints: List[str] = None
    ) -> ConstraintResult:
        """
        Scan objective and constraints for ethical violations.
        """
        content_to_scan = [objective.lower()]
        if constraints:
            content_to_scan.extend([c.lower() for c in constraints])

        violations = []
        matches = []

        for guardrail, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for text in content_to_scan:
                    if re.search(pattern, text):
                        violations.append(guardrail)
                        matches.append(f"'{pattern}' found in '{text}'")
                        break

        if violations:
            violations = list(set(violations))  # Deduplicate
            reasoning = f"Policy violation(s) detected: {', '.join(matches)}"
            logger.warning(
                "ethical_violation objective='%s' violations=%s", objective, violations
            )
            return ConstraintResult(
                is_safe=False, violations=violations, reasoning=reasoning
            )

        return ConstraintResult(is_safe=True)


# Singleton instance
ethical_validator = EthicalValidator()
