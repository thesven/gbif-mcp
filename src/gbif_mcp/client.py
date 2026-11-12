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

    def search_occurrences(
        self,
        taxon_key: int | None = None,
        species_name: str | None = None,
        country: str | None = None,
        year: int | None = None,
        basis_of_record: str | None = None,
        has_coordinate: bool = True,
        limit: int = 20,
        slim: bool = True,
    ) -> list[dict[str, Any]]:
        """Search GBIF occurrence records with Darwin Core filtering and slim LLM projection."""
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "hasCoordinate": "true" if has_coordinate else "false",
        }
        if taxon_key is not None:
            params["taxonKey"] = taxon_key
        elif species_name:
            matched = self.match_species(species_name)
            if matched.get("usageKey"):
                params["taxonKey"] = matched["usageKey"]
            else:
                params["scientificName"] = species_name

        if country:
            params["country"] = country.upper()
        if year:
            params["year"] = year
        if basis_of_record:
            params["basisOfRecord"] = basis_of_record.upper()

        data = self._request("/occurrence/search", params)
        records = data.get("results", []) if isinstance(data, dict) else []
        if slim:
            return self._normalize_records(records)
        return records

    def generate_citation(self, dataset_key: str) -> dict[str, Any]:
        """Generate academic research citation, DOI, and attribution for a GBIF dataset."""
        meta = self.get_dataset_metadata(dataset_key)
        title = meta.get("title") or "GBIF Occurrence Dataset"
        doi = meta.get("doi")
        doi_url = f"https://doi.org/{doi}" if doi and not doi.startswith("http") else (doi or "N/A")
        citation_text = meta.get("citation") or f"{title}. GBIF.org. Available from: {doi_url}"
        license_str = meta.get("license") or "CC BY 4.0"
        return {
            "dataset_key": dataset_key,
            "title": title,
            "doi": doi,
            "doi_url": doi_url,
            "citation": citation_text,
            "license": license_str,
            "attribution_statement": f"Data via GBIF.org: {citation_text} [License: {license_str}]",
        }

    def resolve_taxon_bridge(
        self,
        identifier: str,
        source: str = "auto",
    ) -> dict[str, Any]:
        """Bridge cross-platform IDs between iNaturalist, eBird, and the GBIF backbone."""
        clean_id = identifier.strip()
        sci_name: str | None = None
        common_name: str | None = None
        resolved_source = source
        inat_id: int | None = None
        ebird_code: str | None = None

        with httpx.Client(timeout=self.timeout, transport=self.transport) as http:
            # 1. Resolve from iNaturalist
            if source == "inaturalist" or (
                source == "auto" and clean_id.isdigit() and len(clean_id) <= 7
            ):
                try:
                    resp = http.get(f"https://api.inaturalist.org/v1/taxa/{clean_id}")
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        if results:
                            r = results[0]
                            sci_name = r.get("name")
                            common_name = r.get("preferred_common_name")
                            inat_id = r.get("id")
                            resolved_source = "inaturalist"
                except Exception:
                    pass

            # 2. Resolve from eBird
            if not sci_name and (
                source == "ebird"
                or (
                    source == "auto"
                    and clean_id.isalnum()
                    and len(clean_id) <= 8
                    and any(c.isdigit() for c in clean_id)
                )
            ):
                try:
                    resp = http.get(
                        "https://api.ebird.org/v2/ref/taxonomy/ebird",
                        params={"fmt": "json", "species": clean_id},
                    )
                    if resp.status_code == 200:
                        entries = resp.json()
                        if isinstance(entries, list) and entries:
                            e = entries[0]
                            sci_name = e.get("sciName")
                            common_name = e.get("comName")
                            ebird_code = e.get("speciesCode")
                            resolved_source = "ebird"
                except Exception:
                    pass

        # 3. Fallback to direct name query
        if not sci_name:
            sci_name = clean_id
            if resolved_source == "auto":
                resolved_source = "scientific_or_common_name"

        matched = self.match_species(sci_name)
        gbif_key = matched.get("usageKey") or matched.get("speciesKey")

        return {
            "query_identifier": clean_id,
            "resolved_source": resolved_source,
            "scientific_name": matched.get("scientificName") or sci_name,
            "canonical_name": matched.get("canonicalName") or sci_name,
            "common_name": common_name,
            "gbif_taxon_key": gbif_key,
            "rank": matched.get("rank"),
            "status": matched.get("status"),
            "match_type": matched.get("matchType", "NONE"),
            "confidence": matched.get("confidence", 0),
            "kingdom": matched.get("kingdom"),
            "phylum": matched.get("phylum"),
            "class": matched.get("class"),
            "order": matched.get("order"),
            "family": matched.get("family"),
            "genus": matched.get("genus"),
            "inaturalist_taxon_id": inat_id,
            "ebird_species_code": ebird_code,
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
