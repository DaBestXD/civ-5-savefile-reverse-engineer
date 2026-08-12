"""Convert private raw teams to public team models."""

from .._raw.team.models import CvTeam as RawCvTeam
from ..models import CvTeam, RouteType, TeamTechnology
from ._shared import game_type


def make_team(team: RawCvTeam) -> CvTeam:
    """Create the common semantic view of a team."""
    return CvTeam(
        team_index=team.team_index,
        member_count=team.member_count,
        alive_member_count=team.alive_member_count,
        ever_alive_member_count=team.ever_alive_member_count,
        city_count=team.city_count,
        total_population=team.total_population,
        total_land=team.total_land,
        victory_points=team.victory_points,
        natural_wonders_discovered=team.natural_wonders_discovered,
        best_possible_route=RouteType(team.best_possible_route.value),
        current_era_index=team.current_era,
        has_met=team.has_met,
        at_war=team.at_war,
        has_embassy=team.has_embassy,
        has_open_borders=team.has_open_borders,
        technologies=tuple(
            TeamTechnology(
                technology=game_type(technology.technology),
                unlocked=technology.has_technology,
                obtained_by_human=technology.obtained_by_human,
                obtained_for_league=technology.obtained_for_league,
                cannot_trade=technology.cannot_trade,
                research_progress=technology.research_progress,
                acquisition_count=technology.acquisition_count,
            )
            for technology in team.technologies
        ),
    )

__all__ = ("make_team",)
