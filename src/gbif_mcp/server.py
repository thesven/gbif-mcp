from __future__ import annotations

from mcp.server import FastMCP

from .client import GbifClient


mcp = FastMCP("gbif-mcp")
client = GbifClient()


@mcp.tool()
def species_occurrences_nearby(
    lat: float,
    lon: float,
    radius_km: int = 50,
    limit: int = 25,
    species_name: str | None = None,
) -> dict:
    """Fetch GBIF occurrences near a point."""
    result = client.species_occurrences_nearby(lat, lon, radius_km, limit, species_name)
    result["summary"] = "\n".join(
        f"{item.get('species', 'Unknown species')} at {item.get('locality', 'n/a')} on {item.get('event_date', 'n/a')}"
        for item in result["records"][:10]
    )
    return result


@mcp.tool()
def species_occurrence_history(
    lat: float,
    lon: float,
    radius_km: int = 50,
    species_name: str | None = None,
    years_back: int = 25,
    limit: int = 50,
) -> dict:
    """Fetch historical GBIF occurrences near a point."""
    result = client.species_occurrence_history(lat, lon, radius_km, species_name, years_back, limit)
    result["summary"] = "\n".join(
        f"{item.get('species', 'Unknown species')} on {item.get('event_date', 'n/a')}" for item in result["records"][:10]
    )
    return result


@mcp.tool()
def species_range_check(
    species_name: str,
    lat: float,
    lon: float,
    radius_km: int = 50,
    limit: int = 25,
) -> dict:
    """Assess whether a species looks expected or unusual near a point."""
    result = client.species_range_check(species_name, lat, lon, radius_km, limit)
    assessment = result["assessment"]
    result["summary"] = (
        f"{assessment['species']}: {assessment['status']} with "
        f"{assessment['recent_nearby_records']} recent and {assessment['historical_records']} historical records"
    )
    return result


@mcp.tool()
def unusual_species_nearby(lat: float, lon: float, radius_km: int = 50, limit: int = 25) -> dict:
    """Rank nearby species with sparse GBIF occurrence counts."""
    result = client.unusual_species_nearby(lat, lon, radius_km, limit)
    result["summary"] = "\n".join(
        f"{item['species']}: {item['occurrence_count']} nearby GBIF records" for item in result["records"]
    )
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
