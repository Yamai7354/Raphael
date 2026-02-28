"""
Context Enforcement & Guardrails for AI Router.

Provides token counting, context limit enforcement, and
truncation warnings to prevent exceeding limits.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("ai_router.context")


def estimate_token_count(text: str) -> int:
    """
    Estimate token count using simple heuristic.
    Roughly 4 characters per token for English text.
    More accurate would require tiktoken but this is fast.
    """
    return max(1, len(text) // 4)


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate tokens in a single message."""
    content = message.get("content", "")
    role_overhead = 4  # ~4 tokens for role/formatting
    return estimate_token_count(content) + role_overhead


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens in a list of messages."""
    return sum(estimate_message_tokens(m) for m in messages)


@dataclass
class ContextCheck:
    """Result of a context limit check."""

    is_valid: bool
    estimated_tokens: int
    max_allowed: int
    excess_tokens: int = 0
    truncation_needed: bool = False
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "is_valid": self.is_valid,
            "estimated_tokens": self.estimated_tokens,
            "max_allowed": self.max_allowed,
        }
        if self.excess_tokens > 0:
            result["excess_tokens"] = self.excess_tokens
        if self.truncation_needed:
            result["truncation_needed"] = True
        if self.warning:
            result["warning"] = self.warning
        return result


class ContextEnforcer:
    """
    Enforces context limits on requests.
    Can reject, warn, or truncate based on configuration.
    """

    def __init__(self, global_max_context: int = 32768):
        self.global_max_context = global_max_context

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        role_max_context: int,
        node_max_context: Optional[int] = None,
    ) -> ContextCheck:
        """
        Check if a request fits within context limits.
        Returns ContextCheck with details.
        """
        estimated = estimate_messages_tokens(messages)

        # Determine effective limit (minimum of all constraints)
        effective_limit = min(
            role_max_context,
            node_max_context or self.global_max_context,
            self.global_max_context,
        )

        # Leave room for response (reserve ~25% for output)
        input_limit = int(effective_limit * 0.75)

        if estimated <= input_limit:
            return ContextCheck(
                is_valid=True,
                estimated_tokens=estimated,
                max_allowed=effective_limit,
            )

        excess = estimated - input_limit

        # Check if we're just over (warning) or way over (reject)
        if estimated <= effective_limit:
            return ContextCheck(
                is_valid=True,
                estimated_tokens=estimated,
                max_allowed=effective_limit,
                warning=f"Request uses {estimated} of {effective_limit} tokens. "
                f"Limited response capacity.",
            )

        return ContextCheck(
            is_valid=False,
            estimated_tokens=estimated,
            max_allowed=effective_limit,
            excess_tokens=excess,
            truncation_needed=True,
            warning=f"Request exceeds limit by {excess} tokens.",
        )

    def truncate_messages(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        preserve_system: bool = True,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Truncate messages to fit within token limit.
        Preserves system message and most recent user message.
        Returns (truncated_messages, tokens_removed).

        Strategy:
        1. Always keep system message (if preserve_system=True)
        2. Always keep the last user message
        3. Remove oldest assistant/user pairs until under limit
        """
        if not messages:
            return messages, 0

        estimated = estimate_messages_tokens(messages)
        if estimated <= max_tokens:
            return messages, 0

        # Separate system message if present
        system_msg = None
        other_messages = []

        for msg in messages:
            if msg.get("role") == "system" and preserve_system:
                system_msg = msg
            else:
                other_messages.append(msg)

        # Always preserve the last message (typically user's new input)
        if other_messages:
            last_msg = other_messages[-1]
            middle_messages = other_messages[:-1]
        else:
            return messages, 0

        # Remove from the beginning until we fit
        tokens_removed = 0
        while middle_messages:
            current = [system_msg] if system_msg else []
            current.extend(middle_messages)
            current.append(last_msg)

            if estimate_messages_tokens(current) <= max_tokens:
                break

            removed = middle_messages.pop(0)
            tokens_removed += estimate_message_tokens(removed)

        # Build result
        result = []
        if system_msg:
            result.append(system_msg)
        result.extend(middle_messages)
        result.append(last_msg)

        logger.info(
            "messages_truncated tokens_removed=%d messages_remaining=%d",
            tokens_removed,
            len(result),
        )

        return result, tokens_removed


# Global singleton with default settings
context_enforcer = ContextEnforcer()


def enforce_context_limit(
    messages: List[Dict[str, Any]], role_max_context: int, strict: bool = False
) -> tuple[ContextCheck, List[Dict[str, Any]]]:
    """
    High-level function to enforce context limits.
    If strict=True, raises error on violation.
    Otherwise, truncates and returns warning.

    Returns (check_result, possibly_truncated_messages)
    """
    check = context_enforcer.check_request(messages, role_max_context)

    if check.is_valid:
        return check, messages

    if strict:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "error": "context_exceeded",
                "estimated_tokens": check.estimated_tokens,
                "max_allowed": check.max_allowed,
                "excess_tokens": check.excess_tokens,
            },
        )

    # Auto-truncate
    input_limit = int(role_max_context * 0.75)
    truncated, removed = context_enforcer.truncate_messages(messages, input_limit)

    return ContextCheck(
        is_valid=True,
        estimated_tokens=estimate_messages_tokens(truncated),
        max_allowed=role_max_context,
        truncation_needed=True,
        warning=f"Request truncated. Removed ~{removed} tokens.",
    ), truncated
