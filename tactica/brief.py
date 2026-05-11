"""TeamBrief: what one side produces per round.

The shape the LLM will eventually fill in. Hardcoded sides fake it for now
so the observer UI can render real-looking content end-to-end.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TeamBrief:
    round: int
    team: str            # 'red' | 'blue'
    model: str           # 'hardcoded:rush' or 'qwen-coder-32b' once wired
    reasoning: str       # free-form LLM thinking for this round
    composition: Dict[str, int]   # {'mbt': 3, ...} — string keys for JSON
    tactics: Dict[str, str]       # {'mbt': '<python source>', ...}
    scratchpad: str      # free-form notes the LLM writes to its future self

    def to_dict(self):
        return {
            "round": self.round,
            "team": self.team,
            "model": self.model,
            "reasoning": self.reasoning,
            "composition": dict(self.composition),
            "tactics": dict(self.tactics),
            "scratchpad": self.scratchpad,
        }
