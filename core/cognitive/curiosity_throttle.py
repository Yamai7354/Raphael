"""
COG-207 — Curiosity Throttle.

Prevents excessive question generation and research loops.
Dynamically adjusts curiosity level based on system load.
"""

import logging
import time

logger = logging.getLogger("core.cognitive.curiosity_throttle")


class CuriosityThrottle:
    """
    Limits the rate of question/mission generation to prevent
    the swarm from spiraling into infinite research loops.
    """

    def __init__(
        self,
        max_active_missions: int = 10,
        max_questions_per_cycle: int = 5,
        cooldown_seconds: float = 60.0,
    ):
        self.max_active_missions = max_active_missions
        self.max_questions_per_cycle = max_questions_per_cycle
        self.cooldown_seconds = cooldown_seconds

        self._active_missions: int = 0
        self._questions_this_cycle: int = 0
        self._last_cycle_reset: float = time.time()
        self._curiosity_level: float = 1.0  # 0=suppressed, 1=full
        self._overload_events: int = 0

    def can_generate_question(self) -> bool:
        """Check if a new question can be generated."""
        self._maybe_reset_cycle()

        if self._questions_this_cycle >= self.max_questions_per_cycle:
            logger.debug("curiosity_throttled reason=cycle_limit")
            return False
        if self._active_missions >= self.max_active_missions:
            logger.debug("curiosity_throttled reason=mission_cap")
            return False
        return True

    def record_question(self) -> None:
        self._questions_this_cycle += 1

    def record_mission_start(self) -> None:
        self._active_missions += 1

    def record_mission_end(self) -> None:
        self._active_missions = max(0, self._active_missions - 1)

    def adjust_for_load(self, system_load: float) -> None:
        """
        Adjust curiosity level based on system load (0-1).
        High load → suppress curiosity. Low load → encourage it.
        """
        if system_load > 0.8:
            self._curiosity_level = max(0.1, self._curiosity_level - 0.2)
            self._overload_events += 1
            logger.info(
                "curiosity_reduced load=%.2f level=%.2f",
                system_load,
                self._curiosity_level,
            )
        elif system_load < 0.3:
            self._curiosity_level = min(1.0, self._curiosity_level + 0.1)

    def get_effective_limit(self) -> int:
        """Return the effective question limit adjusted by curiosity level."""
        return max(1, int(self.max_questions_per_cycle * self._curiosity_level))

    def _maybe_reset_cycle(self) -> None:
        now = time.time()
        if now - self._last_cycle_reset >= self.cooldown_seconds:
            self._questions_this_cycle = 0
            self._last_cycle_reset = now

    def get_status(self) -> dict:
        return {
            "curiosity_level": round(self._curiosity_level, 2),
            "active_missions": self._active_missions,
            "max_missions": self.max_active_missions,
            "questions_this_cycle": self._questions_this_cycle,
            "effective_limit": self.get_effective_limit(),
            "overload_events": self._overload_events,
        }
