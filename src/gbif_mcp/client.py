from __future__ import annotations

import math
from typing import Any

import httpx


class GbifClient:
    def __init__(self, base_url: str = "https://api.gbif.org/v1") -> None:
        self.base_url = base_url.rstrip("/")

    def species_occurrences_nearby(
        self,
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
        species_name: str | None = None,
        years_back: int | None = None,
    ) -> dict[str, Any]:
        params = {
            "geometry": self._bbox_geometry(lat, lon, radius_km),
            "limit": limit,
            "hasCoordinate": "true",
            "occurrenceStatus": "PRESENT",
        }
        if species_name:
            params["scientificName"] = species_name
        if years_back:
            params["year"] = f"{2026 - years_back},2026"
        data = self._request("/occurrence/search", params)
        return {"records": self._normalize_records(data.get("results", [])), "count": data.get("count", 0)}

    def species_occurrence_history(
        self,
        lat: float,
        lon: float,
        radius_km: int = 50,
        species_name: str | None = None,
        years_back: int = 25,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self.species_occurrences_nearby(lat, lon, radius_km, limit, species_name, years_back)

    def species_range_check(
        self,
        species_name: str,
        lat: float,
        lon: float,
        radius_km: int = 50,
        limit: int = 25,
    ) -> dict[str, Any]:
        recent = self.species_occurrences_nearby(lat, lon, radius_km, limit, species_name, years_back=5)
        historical = self.species_occurrence_history(lat, lon, radius_km, species_name, years_back=25, limit=100)
        recent_count = len(recent["records"])
        historical_count = len(historical["records"])
        if recent_count == 0 and historical_count == 0:
            status = "no-local-records"
        elif recent_count <= 3:
            status = "uncommon-but-regular"
        else:
            status = "expected"
        return {
            "assessment": {
                "species": species_name,
                "status": status,
                "recent_nearby_records": recent_count,
                "historical_records": historical_count,
            }
        }

    def unusual_species_nearby(self, lat: float, lon: float, radius_km: int = 50, limit: int = 25) -> dict[str, Any]:
        result = self.species_occurrences_nearby(lat, lon, radius_km, limit=100)
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
                }
            )
        ranked.sort(key=lambda item: item["occurrence_count"])
        return {"records": ranked[:limit]}

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = httpx.get(self.base_url + path, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected GBIF response shape for {path}")
        return data

    @staticmethod
    def _normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for item in records:
            normalized.append(
                {
                    "species": item.get("species") or item.get("scientificName"),
                    "event_date": item.get("eventDate"),
                    "locality": item.get("locality"),
                    "basis_of_record": item.get("basisOfRecord"),
                }
            )
        return normalized

    @staticmethod
    def _bbox_geometry(lat: float, lon: float, radius_km: int) -> str:
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
        min_lat = lat - lat_delta
        max_lat = lat + lat_delta
        min_lon = lon - lon_delta
        max_lon = lon + lon_delta
        return (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},"
            f"{min_lon} {max_lat},{min_lon} {min_lat}))"
        )
