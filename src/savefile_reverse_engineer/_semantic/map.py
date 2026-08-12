"""Convert private raw plots to public map models."""

from .._raw.map.models import CvPlot as RawCvPlot
from .._raw.map.models import ObjectReference as RawObjectReference
from ..models import (
    CvPlot,
    ObjectReference,
    PlotFlags,
    PlotType,
    PlotYields,
    RouteType,
    TerrainType,
)
from ._shared import game_type


def _object_reference(value: RawObjectReference) -> ObjectReference:
    return ObjectReference(
        owner_player_index=value.owner,
        object_id=value.object_id,
    )


def make_plot(plot: RawCvPlot) -> CvPlot:
    """Create the common semantic view of a plot."""
    flags = plot.flags
    return CvPlot(
        x=plot.x,
        y=plot.y,
        area_index=plot.area,
        owner_player_index=plot.owner,
        ownership_duration=plot.ownership_duration,
        plot_type=PlotType(plot.plot_type.value),
        terrain=TerrainType(plot.terrain.value),
        feature=game_type(plot.feature),
        resource=game_type(plot.resource),
        resource_quantity=plot.resource_quantity,
        improvement=game_type(plot.improvement),
        improvement_pillaged=flags.improvement_pillaged,
        route=RouteType(plot.route.value),
        route_pillaged=flags.route_pillaged,
        flags=PlotFlags(
            starting_plot=flags.starting_plot,
            hills=flags.hills,
            northeast_of_river=flags.northeast_of_river,
            west_of_river=flags.west_of_river,
            northwest_of_river=flags.northwest_of_river,
            potential_city_work=flags.potential_city_work,
            improvement_pillaged=flags.improvement_pillaged,
            route_pillaged=flags.route_pillaged,
            forced_fresh_water=flags.forced_fresh_water,
        ),
        plot_city=_object_reference(plot.plot_city),
        working_city=_object_reference(plot.working_city),
        purchase_city=_object_reference(plot.purchase_city),
        yields=PlotYields(
            food=plot.yields.food,
            production=plot.yields.production,
            gold=plot.yields.gold,
            science=plot.yields.science,
            culture=plot.yields.culture,
            faith=plot.yields.faith,
            golden_age_points=plot.yields.golden_age_points,
        ),
        unit_references=tuple(
            _object_reference(reference) for reference in plot.unit_references
        ),
        continent_index=plot.continent,
    )

__all__ = ("make_plot",)
