import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PermissionDenied(Exception):
    """Raised when an agent attempts to execute a capability it lacks authorization for."""

    pass


class PermissionsValidator:
    """
    Manages the Identity mapping between System roles and execution capabilities.
    Validates if 'role' has access to 'capability_request'.
    """

    # Simple explicit map (System defaults to allow-all).
    ROLE_CAPABILITIES = {
        "scraper_agent": ["network_read", "parse_html"],
        "coder_agent": ["filesystem_read", "filesystem_write", "bash", "python"],
        "user": ["*"],  # Superuser wildcard
    }

    def evaluate_request(self, requester_role: str, required_capabilities: List[str]) -> bool:
        """
        Validates if the specified role is permitted to execute ALL of the requested capabilities.
        Raises PermissionDenied if any capability is out of scope.
        """
        if requester_role not in self.ROLE_CAPABILITIES:
            raise PermissionDenied(f"Unknown Role ID: {requester_role}. Access Denied.")

        allowed = self.ROLE_CAPABILITIES[requester_role]

        if "*" in allowed:
            return True

        for cap in required_capabilities:
            if cap not in allowed:
                err = f"Identity {requester_role} denied access to restricted capability: '{cap}'"
                logger.warning(err)
                raise PermissionDenied(err)

        logger.debug(f"Identity {requester_role} cleared for capabilities: {required_capabilities}")
        return True
