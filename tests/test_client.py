from __future__ import annotations

import httpx
import pytest

from gbif_mcp.client import GbifClient, GbifError


def test_client_init() -> None:
    client = GbifClient(base_url="https://api.gbif.org/v1/")
    assert client.base_url == "https://api.gbif.org/v1"
    assert client.timeout == 30.0


def test_bbox_geometry() -> None:
    geom = GbifClient._bbox_geometry(45.0, -75.0, 50)
    assert geom.startswith("POLYGON((")
    assert "-75." in geom
    assert "45." in geom


def test_match_species() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/species/match"
        assert request.url.params["name"] == "Ursus arctos"
        return httpx.Response(
            200,
            json={
                "usageKey": 2433433,
                "scientificName": "Ursus arctos Linnaeus, 1758",
                "canonicalName": "Ursus arctos",
                "rank": "SPECIES",
                "status": "ACCEPTED",
                "confidence": 99,
                "matchType": "EXACT",
                "kingdom": "Animalia",
            },
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    res = client.match_species("Ursus arctos", kingdom="Animalia", strict=True)
    assert res["usageKey"] == 2433433
    assert res["scientificName"] == "Ursus arctos Linnaeus, 1758"


def test_search_species() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/species/suggest"
        return httpx.Response(
            200,
            json=[
                {
                    "key": 2433433,
                    "scientificName": "Ursus arctos Linnaeus, 1758",
                    "canonicalName": "Ursus arctos",
                    "rank": "SPECIES",
                    "status": "ACCEPTED",
                    "kingdom": "Animalia",
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    results = client.search_species("Ursus", limit=5)
    assert len(results) == 1
    assert results[0]["key"] == 2433433
    assert results[0]["scientific_name"] == "Ursus arctos Linnaeus, 1758"


def test_search_species_non_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "none"})

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    assert client.search_species("Ursus") == []


def test_get_species_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/species/2433433"
        return httpx.Response(
            200,
            json={
                "key": 2433433,
                "scientificName": "Ursus arctos Linnaeus, 1758",
                "rank": "SPECIES",
                "taxonomicStatus": "ACCEPTED",
            },
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    details = client.get_species_details(2433433)
    assert details["key"] == 2433433
    assert details["taxonomicStatus"] == "ACCEPTED"


def test_species_occurrences_nearby() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/occurrence/search"
        assert request.url.params["taxonKey"] == "2433433"
        return httpx.Response(
            200,
            json={
                "count": 1,
                "endOfRecords": True,
                "results": [
                    {
                        "key": 1001,
                        "species": "Ursus arctos",
                        "scientificName": "Ursus arctos Linnaeus, 1758",
                        "vernacularName": "Brown Bear",
                        "eventDate": "2024-06-15",
                        "year": 2024,
                        "month": 6,
                        "decimalLatitude": 45.1,
                        "decimalLongitude": -75.1,
                        "locality": "Algonquin Park",
                        "basisOfRecord": "HUMAN_OBSERVATION",
                        "institutionCode": "iNaturalist",
                        "datasetKey": "d-123",
                        "media": [
                            {"type": "StillImage", "identifier": "https://img.example/1.jpg"},
                            {"type": "StillImage"},
                            "non-dict-media",
                        ],
                        "issues": [],
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    res = client.species_occurrences_nearby(
        45.0,
        -75.0,
        radius_km=25,
        limit=10,
        species_name="Ursus arctos",
        taxon_key=2433433,
        basis_of_record="HUMAN_OBSERVATION",
        years_back=5,
    )
    assert res["count"] == 1
    record = res["records"][0]
    assert record["key"] == 1001
    assert record["species"] == "Ursus arctos"
    assert len(record["media"]) == 1
    assert record["media"][0]["url"] == "https://img.example/1.jpg"


def test_species_range_check_statuses() -> None:
    # 1. no local records
    def handler_empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"count": 0, "results": []})

    client = GbifClient(transport=httpx.MockTransport(handler_empty))
    res = client.species_range_check("Fictional species", 45.0, -75.0)
    assert res["assessment"]["status"] == "no-local-records"

    # 2. historic only
    def handler_historic(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("year") == "2021,2026":
            return httpx.Response(200, json={"count": 0, "results": []})
        return httpx.Response(
            200,
            json={"count": 1, "results": [{"species": "Bear", "eventDate": "2005-01-01"}]},
        )

    client = GbifClient(transport=httpx.MockTransport(handler_historic))
    res = client.species_range_check("Bear", 45.0, -75.0)
    assert res["assessment"]["status"] == "historic-only"

    # 3. expected (>3 recent)
    def handler_expected(request: httpx.Request) -> httpx.Response:
        results = [{"species": "Bear", "eventDate": "2024-01-01"}] * 5
        return httpx.Response(200, json={"count": 5, "results": results})

    client = GbifClient(transport=httpx.MockTransport(handler_expected))
    res = client.species_range_check("Bear", 45.0, -75.0)
    assert res["assessment"]["status"] == "expected"


def test_unusual_species_nearby() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"species": "Species A", "locality": "Loc 1", "eventDate": "2023-01-01"},
                    {"species": "Species B", "locality": "Loc 2", "eventDate": "2023-01-02"},
                    {"species": "Species A", "locality": "Loc 1", "eventDate": "2023-01-03"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    res = client.unusual_species_nearby(45.0, -75.0, limit=5)
    records = res["records"]
    assert len(records) == 2
    assert records[0]["species"] == "Species B"
    assert records[0]["occurrence_count"] == 1
    assert records[1]["species"] == "Species A"
    assert records[1]["occurrence_count"] == 2


def test_get_dataset_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/dataset/sample-key"
        return httpx.Response(
            200,
            json={
                "key": "sample-key",
                "title": "Biodiversity Research Dataset",
                "description": "A test dataset",
                "citation": {"text": "Smith et al. 2024"},
                "doi": "10.1234/gbif.test",
                "license": "CC-BY-4.0",
                "homepage": "https://example.org",
            },
        )

    transport = httpx.MockTransport(handler)
    client = GbifClient(transport=transport)
    meta = client.get_dataset_metadata("sample-key")
    assert meta["key"] == "sample-key"
    assert meta["citation"] == "Smith et al. 2024"
    assert meta["doi"] == "10.1234/gbif.test"


def test_error_handling() -> None:
    def handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = GbifClient(transport=httpx.MockTransport(handler_500))
    with pytest.raises(GbifError, match="GBIF API request failed"):
        client.get_species_details(1234)

    def handler_bad_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"invalid-json{")

    client2 = GbifClient(transport=httpx.MockTransport(handler_bad_json))
    with pytest.raises(GbifError, match="Invalid JSON"):
        client2.get_species_details(1234)
