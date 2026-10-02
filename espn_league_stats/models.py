"""Serializable data models representing one team's season."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class WeeklyResult:
    week: int
    opponent_team_id: int
    points_for: float
    points_against: float
    result: str  # "W" | "L" | "T"
    is_playoff: bool


@dataclass
class TeamSeasonStats:
    year: int
    team_id: int
    team_name: str
    owner_ids: list[str]
    owner_names: list[str]
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    standing: int
    final_standing: int
    made_playoffs: bool
    streak_length: int
    streak_type: str
    acquisitions: int
    drops: int
    trades: int
    reg_season_weeks: int
    playoff_team_count: int
    weekly: list[WeeklyResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "TeamSeasonStats":
        weekly = [WeeklyResult(**w) for w in data.pop("weekly", [])]
        return TeamSeasonStats(weekly=weekly, **data)
