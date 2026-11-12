from __future__ import annotations

import math
from typing import Any

import httpx


class GbifError(RuntimeError):
    """Base exception for GBIF API client errors."""


class GbifClient:
    """Client for querying the GBIF REST API v1."""

    def __init__(
        self,
        base_url: str = "https://api.gbif.org/v1",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def match_species(
        self,
        name: str,
        kingdom: str | None = None,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Fuzzily or strictly match a scientific/common name to the GBIF backbone taxonomy."""
        params: dict[str, Any] = {"name": name, "strict": "true" if strict else "false"}
        if kingdom:
            params["kingdom"] = kingdom
        return self._request("/species/match", params)

    def search_species(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search GBIF species catalog for autocompletion and taxonomic lookup."""
        params = {"q": query, "limit": min(limit, 100)}
        data = self._request("/species/suggest", params)
        if isinstance(data, list):
            return [
                {
                    "key": item.get("key"),
                    "scientific_name": item.get("scientificName"),
                    "canonical_name": item.get("canonicalName"),
                    "rank": item.get("rank"),
                    "status": item.get("status"),
                    "kingdom": item.get("kingdom"),
                    "phylum": item.get("phylum"),
                    "class": item.get("class"),
                    "order": item.get("order"),
                    "family": item.get("family"),
                    "genus": item.get("genus"),
                }
                for item in data
            ]
        return []

    def get_species_details(self, taxon_key: int) -> dict[str, Any]:
        """Fetch detailed taxonomic information and lineage for a taxon key."""
        return self._request(f"/species/{taxon_key}", {})

    def species_occurrences_nearby(
        self,
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
        species_name: str | None = None,
        taxon_key: int | None = None,
        basis_of_record: str | None = None,
        years_back: int | None = None,
    ) -> dict[str, Any]:
        """Search occurrence records around a point using Darwin Core filters."""
        params: dict[str, Any] = {
            "geometry": self._bbox_geometry(lat, lon, radius_km),
            "limit": min(limit, 100),
            "hasCoordinate": "true",
            "occurrenceStatus": "PRESENT",
        }
        if species_name:
            params["scientificName"] = species_name
        if taxon_key is not None:
            params["taxonKey"] = taxon_key
        if basis_of_record:
            params["basisOfRecord"] = basis_of_record.upper()
        if years_back:
            start_year = 2026 - years_back
            params["year"] = f"{start_year},2026"

        data = self._request("/occurrence/search", params)
        records = self._normalize_records(data.get("results", []))
        return {
            "records": records,
            "count": data.get("count", len(records)),
            "end_of_records": data.get("endOfRecords", True),
        }

    def species_occurrence_history(
        self,
        lat: float,
        lon: float,
        radius_km: int = 50,
        species_name: str | None = None,
        years_back: int = 25,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch historical occurrence records across multi-year timeline."""
        return self.species_occurrences_nearby(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            limit=limit,
            species_name=species_name,
            years_back=years_back,
        )

    def species_range_check(
        self,
        species_name: str,
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Evaluate if species presence is expected, sparse, or unprecedented."""
        recent = self.species_occurrences_nearby(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            limit=limit,
            species_name=species_name,
            years_back=5,
        )
        historical = self.species_occurrence_history(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            species_name=species_name,
            years_back=25,
            limit=100,
        )
        recent_count = len(recent["records"])
        historical_count = len(historical["records"])

        if recent_count == 0 and historical_count == 0:
            status = "no-local-records"
            interpretation = "Species has no documented GBIF records in this radius."
        elif recent_count == 0 and historical_count > 0:
            status = "historic-only"
            interpretation = "Species has historical GBIF records, but none in the last 5 years."
        elif recent_count <= 3:
            status = "uncommon-but-regular"
            interpretation = "Species is documented with sparse recent occurrences."
        else:
            status = "expected"
            interpretation = "Species is regularly and recently documented in this radius."

        return {
            "assessment": {
                "species": species_name,
                "status": status,
                "interpretation": interpretation,
                "recent_nearby_records": recent_count,
                "historical_records": historical_count,
                "radius_km": radius_km,
            }
        }

    def unusual_species_nearby(
        self, lat: float, lon: float, radius_km: int = 50, limit: int = 25
    ) -> dict[str, Any]:
        """Find species with low occurrence frequencies in the surrounding area."""
        result = self.species_occurrences_nearby(lat=lat, lon=lon, radius_km=radius_km, limit=100)
        counts: dict[str, int] = {}
        sample: dict[str, dict[str, Any]] = {}

        for record in result["records"]:
            species = record.get("species") or "Unknown species"
            counts[species] = counts.get(species, 0) + 1
            sample.setdefault(species, record)

        ranked = []
        for species, count in counts.items():
            item = sample[species]
            ranked.append(
                {
                    "species": species,
                    "occurrence_count": count,
                    "locality": item.get("locality"),
                    "event_date": item.get("event_date"),
                    "basis_of_record": item.get("basis_of_record"),
                }
            )
        ranked.sort(key=lambda item: item["occurrence_count"])
        return {"records": ranked[:limit], "total_species_sampled": len(counts)}

    def get_dataset_metadata(self, dataset_key: str) -> dict[str, Any]:
        """Fetch publisher and provenance metadata for a GBIF dataset."""
        data = self._request(f"/dataset/{dataset_key}", {})
        return {
            "key": data.get("key"),
            "title": data.get("title"),
            "description": data.get("description"),
            "citation": data.get("citation", {}).get("text")
            if isinstance(data.get("citation"), dict)
            else data.get("citation"),
            "doi": data.get("doi"),
            "license": data.get("license"),
            "homepage": data.get("homepage"),
        }

    def _request(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            try:
                response = client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise GbifError(f"GBIF API request failed for {path}: {exc}") from exc

            try:
                return response.json()
            except Exception as exc:
                raise GbifError(f"Invalid JSON returned from GBIF for {path}") from exc

    @staticmethod
    def _normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw Darwin Core records into agent-optimized JSON representations."""
        normalized = []
        for item in records:
            media = []
            for m in item.get("media", []):
                if isinstance(m, dict) and m.get("identifier"):
                    media.append({"type": m.get("type"), "url": m.get("identifier")})

            normalized.append(
                {
                    "key": item.get("key"),
                    "species": item.get("species") or item.get("scientificName"),
                    "vernacular_name": item.get("vernacularName"),
                    "event_date": item.get("eventDate"),
                    "year": item.get("year"),
                    "month": item.get("month"),
                    "decimal_latitude": item.get("decimalLatitude"),
                    "decimal_longitude": item.get("decimalLongitude"),
                    "coordinate_uncertainty_in_meters": item.get("coordinateUncertaintyInMeters"),
                    "locality": item.get("locality"),
                    "state_province": item.get("stateProvince"),
                    "country": item.get("country"),
                    "basis_of_record": item.get("basisOfRecord"),
                    "institution_code": item.get("institutionCode"),
                    "dataset_key": item.get("datasetKey"),
                    "media": media,
                    "issues": item.get("issues", []),
                }
            )
        return normalized

    @staticmethod
    def _bbox_geometry(lat: float, lon: float, radius_km: int) -> str:
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
        min_lat = round(lat - lat_delta, 6)
        max_lat = round(lat + lat_delta, 6)
        min_lon = round(lon - lon_delta, 6)
        max_lon = round(lon + lon_delta, 6)
        return (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},"
            f"{min_lon} {max_lat},{min_lon} {min_lat}))"
        )
