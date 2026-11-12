from __future__ import annotations

import argparse
import sys
from typing import Any

from mcp.server import MCPServer

from . import __version__
from .client import GbifClient, GbifError

DEFAULT_INSTRUCTIONS = """
GBIF MCP Server: Access global biodiversity occurrence records, authoritative taxonomic
backbone matching, cross-platform taxon ID resolution, and historical species distribution data.

Key Best Practices:
1. When checking a species by common or ambiguous name, call `match_species` or `search_species`
   first to obtain its accepted scientific name, taxonomic rank, and GBIF `taxon_key`.
2. To bridge IDs across citizen science and ecological tools, call `resolve_taxon_bridge` with
   an iNaturalist taxon ID, an eBird species code, or a scientific name for a unified profile.
3. Call `search_occurrences` for flexible Darwin Core occurrence filtering (by country, year,
   basis of record) with token-optimized slim projections.
4. To explore occurrence records around a location, call `species_occurrences_nearby` with
   `lat`, `lon`, and `radius_km`.
5. Use `species_range_check` to systematically evaluate whether a species is expected,
   uncommon, historic-only, or undocumented in a local area.
6. Use `generate_citation` to generate formal academic citations and attribution statements.
""".strip()


def _format_records_summary(records: list[dict[str, Any]]) -> str:
    if not records:
        return "No records found."
    lines = []
    for r in records[:10]:
        species = r.get("species") or "Unknown species"
        date = r.get("event_date") or "Date unknown"
        locality = r.get("locality")
        basis = r.get("basis_of_record") or "RECORD"
        loc_str = f" in {locality}" if locality else ""
        lines.append(f"- [{basis}] {species} on {date}{loc_str}")
    return "\n".join(lines)


def create_server(client: GbifClient | None = None) -> MCPServer:
    """Create and configure the GBIF MCPServer instance."""
    api = client or GbifClient()

    server = MCPServer(
        "gbif",
        version=__version__,
        instructions=DEFAULT_INSTRUCTIONS,
    )

    @server.tool()
    def match_species(
        name: str,
        kingdom: str | None = None,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Match a scientific or vernacular species name against the GBIF taxonomic backbone."""
        try:
            result = api.match_species(name=name, kingdom=kingdom, strict=strict)
            match_type = result.get("matchType", "NONE")
            scientific = result.get("scientificName", "No match")
            status = result.get("status", "UNKNOWN")
            confidence = result.get("confidence", 0)
            summary = (
                f"Match: {scientific} (type={match_type}, "
                f"status={status}, confidence={confidence}%)"
            )
            return {"match": result, "summary": summary}
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Species match failed: {exc}"}

    @server.tool()
    def search_species(query: str, limit: int = 15) -> dict[str, Any]:
        """Search GBIF species backbone for auto-suggest and taxonomy autocompletion."""
        try:
            results = api.search_species(query=query, limit=limit)
            lines = [
                f"- {item.get('scientific_name')} ({item.get('rank')}, {item.get('kingdom')}) "
                f"[key: {item.get('key')}]"
                for item in results[:10]
            ]
            summary = "\n".join(lines) if lines else "No matching taxa found."
            return {"results": results, "count": len(results), "summary": summary}
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Species search failed: {exc}"}

    @server.tool()
    def get_species_details(taxon_key: int) -> dict[str, Any]:
        """Retrieve complete taxonomic classification and lineage for a GBIF taxon key."""
        try:
            details = api.get_species_details(taxon_key=taxon_key)
            name = details.get("scientificName") or details.get("canonicalName", "Taxon")
            rank = details.get("rank", "Unknown rank")
            summary = f"{name} ({rank}) - Status: {details.get('taxonomicStatus', 'N/A')}"
            return {"details": details, "summary": summary}
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Failed to get species details: {exc}"}

    @server.tool()
    def species_occurrences_nearby(
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
        species_name: str | None = None,
        taxon_key: int | None = None,
        basis_of_record: str | None = None,
        years_back: int | None = None,
    ) -> dict[str, Any]:
        """Fetch GBIF occurrence records within a geographic radius in kilometers."""
        try:
            result = api.species_occurrences_nearby(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=limit,
                species_name=species_name,
                taxon_key=taxon_key,
                basis_of_record=basis_of_record,
                years_back=years_back,
            )
            result["summary"] = _format_records_summary(result["records"])
            return result
        except GbifError as exc:
            return {"error": str(exc), "records": [], "count": 0, "summary": f"Query failed: {exc}"}

    @server.tool()
    def species_occurrence_history(
        lat: float,
        lon: float,
        radius_km: int = 50,
        species_name: str | None = None,
        years_back: int = 25,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch historical GBIF occurrence records spanning several decades."""
        try:
            result = api.species_occurrence_history(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                species_name=species_name,
                years_back=years_back,
                limit=limit,
            )
            result["summary"] = _format_records_summary(result["records"])
            return result
        except GbifError as exc:
            return {"error": str(exc), "records": [], "count": 0, "summary": f"Query failed: {exc}"}

    @server.tool()
    def species_range_check(
        species_name: str,
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Assess whether a species is expected, historic-only, or undocumented near coordinates."""
        try:
            result = api.species_range_check(
                species_name=species_name,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=limit,
            )
            assessment = result["assessment"]
            status_upper = assessment["status"].upper()
            interp = assessment["interpretation"]
            recent_cnt = assessment["recent_nearby_records"]
            hist_cnt = assessment["historical_records"]
            result["summary"] = (
                f"{assessment['species']}: {status_upper} — {interp} "
                f"({recent_cnt} recent, {hist_cnt} historical records)"
            )
            return result
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Range check failed: {exc}"}

    @server.tool()
    def unusual_species_nearby(
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Identify species with low occurrence frequencies near a point."""
        try:
            result = api.unusual_species_nearby(lat=lat, lon=lon, radius_km=radius_km, limit=limit)
            lines = []
            for item in result["records"][:10]:
                loc = item.get("locality") or "unknown"
                lines.append(
                    f"- {item['species']}: {item['occurrence_count']} records (last at {loc})"
                )
            result["summary"] = "\n".join(lines) if lines else "No species records found."
            return result
        except GbifError as exc:
            return {"error": str(exc), "records": [], "summary": f"Query failed: {exc}"}

    @server.tool()
    def get_dataset_metadata(dataset_key: str) -> dict[str, Any]:
        """Fetch title, publisher, license, and citation information for a GBIF dataset."""
        try:
            meta = api.get_dataset_metadata(dataset_key=dataset_key)
            title = meta.get("title", "Untitled dataset")
            citation = meta.get("citation") or meta.get("doi") or "No citation recorded"
            summary = f"Dataset: {title} | Citation: {citation}"
            return {"dataset": meta, "summary": summary}
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Failed to get dataset metadata: {exc}"}

    @server.tool()
    def search_occurrences(
        taxon_key: int | None = None,
        species_name: str | None = None,
        country: str | None = None,
        year: int | None = None,
        basis_of_record: str | None = None,
        has_coordinate: bool = True,
        limit: int = 20,
        slim: bool = True,
    ) -> dict[str, Any]:
        """Search GBIF occurrences with Darwin Core filtering and token-optimized projections."""
        try:
            records = api.search_occurrences(
                taxon_key=taxon_key,
                species_name=species_name,
                country=country,
                year=year,
                basis_of_record=basis_of_record,
                has_coordinate=has_coordinate,
                limit=limit,
                slim=slim,
            )
            summary = _format_records_summary(records)
            return {"records": records, "count": len(records), "summary": summary}
        except GbifError as exc:
            return {
                "error": str(exc),
                "records": [],
                "count": 0,
                "summary": f"Search failed: {exc}",
            }

    @server.tool()
    def generate_citation(dataset_key: str) -> dict[str, Any]:
        """Generate academic research citation, DOI link, and attribution statement."""
        try:
            citation_info = api.generate_citation(dataset_key=dataset_key)
            return {
                "citation": citation_info,
                "summary": citation_info["attribution_statement"],
            }
        except GbifError as exc:
            return {"error": str(exc), "summary": f"Failed to generate citation: {exc}"}

    @server.tool()
    def resolve_taxon_bridge(
        identifier: str,
        source: str = "auto",
    ) -> dict[str, Any]:
        """Bridge cross-platform IDs between iNaturalist, eBird, and the GBIF taxonomic backbone."""
        try:
            profile = api.resolve_taxon_bridge(identifier=identifier, source=source)
            name = profile.get("scientific_name") or identifier
            key = profile.get("gbif_taxon_key") or "unmapped"
            src = profile.get("resolved_source")
            summary = (
                f"Taxon Bridge ({src}): {name} -> GBIF Key {key} (Rank: {profile.get('rank')})"
            )
            return {"profile": profile, "summary": summary}
        except Exception as exc:
            return {"error": str(exc), "summary": f"Taxon bridge resolution failed: {exc}"}

    @server.tool()
    def get_species_children(taxon_key: int, limit: int = 50) -> dict[str, Any]:
        """Traverse taxonomic tree downward to retrieve immediate child taxa."""
        try:
            children = api.get_species_children(taxon_key=taxon_key, limit=limit)
            lines = [
                f"- [{c.get('rank')}] {c.get('scientific_name')} (Key: {c.get('key')})"
                for c in children[:10]
            ]
            summary = (
                f"Found {len(children)} child taxa for key {taxon_key}:\n" + "\n".join(lines)
                if children
                else f"No child taxa found for key {taxon_key}."
            )
            return {"children": children, "count": len(children), "summary": summary}
        except GbifError as exc:
            return {
                "error": str(exc),
                "children": [],
                "count": 0,
                "summary": f"Lookup failed: {exc}",
            }

    @server.tool()
    def search_literature(query: str, limit: int = 15) -> dict[str, Any]:
        """Search peer-reviewed academic literature referencing GBIF biodiversity records."""
        try:
            lit = api.search_literature(query=query, limit=limit)
            docs = lit.get("literature", [])
            lines = [
                f"- {d.get('title')} ({d.get('year')}) in {d.get('journal') or 'N/A'}"
                for d in docs[:5]
            ]
            summary = (
                f"Literature for '{query}' ({lit.get('total_citations')} citations):\n"
                + "\n".join(lines)
                if docs
                else f"No literature citations found for '{query}'."
            )
            return {"results": lit, "summary": summary}
        except GbifError as exc:
            return {"error": str(exc), "results": {}, "summary": f"Literature search failed: {exc}"}

    @server.tool()
    def get_species_media(taxon_key: int, limit: int = 15) -> dict[str, Any]:
        """Retrieve images and specimen photographs deposited for a taxon in GBIF."""
        try:
            media = api.get_species_media(taxon_key=taxon_key, limit=limit)
            lines = [f"- [{m.get('type')}] {m.get('identifier')}" for m in media[:5]]
            summary = (
                f"Media for taxon {taxon_key} ({len(media)} items):\n" + "\n".join(lines)
                if media
                else f"No media found for taxon {taxon_key}."
            )
            return {"media": media, "count": len(media), "summary": summary}
        except GbifError as exc:
            return {
                "error": str(exc),
                "media": [],
                "count": 0,
                "summary": f"Media lookup failed: {exc}",
            }

    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gbif-mcp",
        description="Model Context Protocol (MCP) server for GBIF occurrences and taxonomy",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for SSE transport (default: 8000)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server = create_server()
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="sse", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
