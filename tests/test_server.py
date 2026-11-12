from __future__ import annotations

import httpx
import pytest

from gbif_mcp.client import GbifClient
from gbif_mcp.server import create_server


@pytest.fixture
def mock_client() -> GbifClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/species/match" in path:
            return httpx.Response(
                200,
                json={
                    "usageKey": 2433433,
                    "scientificName": "Ursus arctos",
                    "matchType": "EXACT",
                    "status": "ACCEPTED",
                    "confidence": 98,
                },
            )
        if "/species/suggest" in path:
            return httpx.Response(
                200,
                json=[
                    {
                        "key": 2433433,
                        "scientificName": "Ursus arctos",
                        "rank": "SPECIES",
                        "kingdom": "Animalia",
                    }
                ],
            )
        if "/media" in path:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"identifier": "https://example.com/bear.jpg", "type": "StillImage"}
                    ]
                },
            )
        if "/children" in path:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"key": 2, "scientificName": "Ursus horribilis", "rank": "SUBSPECIES"}
                    ]
                },
            )
        if "/species/2433433" in path:
            return httpx.Response(
                200,
                json={
                    "key": 2433433,
                    "scientificName": "Ursus arctos",
                    "rank": "SPECIES",
                    "taxonomicStatus": "ACCEPTED",
                },
            )
        if "/occurrence/search" in path:
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "results": [
                        {
                            "key": 101,
                            "species": "Ursus arctos",
                            "eventDate": "2024-05-10",
                            "locality": "Yellowstone",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                        }
                    ],
                },
            )
        if "/dataset/" in path:
            return httpx.Response(
                200,
                json={
                    "key": "d1",
                    "title": "Park Survey",
                    "citation": {"text": "Park Survey 2024"},
                },
            )
        if "/media" in path:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"identifier": "https://example.com/bear.jpg", "type": "StillImage"}
                    ]
                },
            )
        if "/children" in path:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"key": 2, "scientificName": "Ursus horribilis", "rank": "SUBSPECIES"}
                    ]
                },
            )
        if "/literature/search" in path:
            return httpx.Response(
                200,
                json={"count": 1, "results": [{"title": "Bear Ecology", "year": 2023}]},
            )
        return httpx.Response(404, text="Not Found")

    return GbifClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def failing_client() -> GbifClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    return GbifClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_server_tools(mock_client: GbifClient) -> None:
    server = create_server(mock_client)

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert "match_species" in tool_names
    assert "search_species" in tool_names
    assert "get_species_details" in tool_names
    assert "species_occurrences_nearby" in tool_names
    assert "species_occurrence_history" in tool_names
    assert "species_range_check" in tool_names
    assert "unusual_species_nearby" in tool_names
    assert "get_dataset_metadata" in tool_names
    assert "search_occurrences" in tool_names
    assert "generate_citation" in tool_names
    assert "resolve_taxon_bridge" in tool_names
    assert "get_species_children" in tool_names
    assert "search_literature" in tool_names
    assert "get_species_media" in tool_names

    res = await server.call_tool("match_species", {"name": "Ursus arctos"})
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool("search_species", {"query": "Ursus"})
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool("get_species_details", {"taxon_key": 2433433})
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool(
        "species_occurrences_nearby", {"lat": 44.5, "lon": -110.5, "radius_km": 50}
    )
    assert "Yellowstone" in res.content[0].text

    res = await server.call_tool(
        "species_occurrence_history", {"lat": 44.5, "lon": -110.5, "radius_km": 50}
    )
    assert "Yellowstone" in res.content[0].text

    res = await server.call_tool(
        "species_range_check",
        {"species_name": "Ursus arctos", "lat": 44.5, "lon": -110.5, "radius_km": 50},
    )
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool(
        "unusual_species_nearby", {"lat": 44.5, "lon": -110.5, "radius_km": 50}
    )
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool("get_dataset_metadata", {"dataset_key": "d1"})
    assert "Park Survey" in res.content[0].text

    res = await server.call_tool("search_occurrences", {"species_name": "Ursus arctos"})
    assert "records" in res.content[0].text

    res = await server.call_tool("generate_citation", {"dataset_key": "d1"})
    assert "Park Survey" in res.content[0].text

    res = await server.call_tool("resolve_taxon_bridge", {"identifier": "Ursus arctos"})
    assert "Ursus arctos" in res.content[0].text

    res = await server.call_tool("get_species_children", {"taxon_key": 2433433})
    assert "child taxa" in res.content[0].text or "Ursus" in res.content[0].text

    res = await server.call_tool("search_literature", {"query": "Ursus arctos"})
    assert "Literature" in res.content[0].text

    res = await server.call_tool("get_species_media", {"taxon_key": 2433433})
    assert "Media" in res.content[0].text


@pytest.mark.asyncio
async def test_server_tool_errors(failing_client: GbifClient) -> None:
    server = create_server(failing_client)

    res = await server.call_tool("match_species", {"name": "Ursus"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("search_species", {"query": "Ursus"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("get_species_details", {"taxon_key": 1})
    assert "failed" in res.content[0].text

    res = await server.call_tool("species_occurrences_nearby", {"lat": 0, "lon": 0})
    assert "failed" in res.content[0].text

    res = await server.call_tool("species_occurrence_history", {"lat": 0, "lon": 0})
    assert "failed" in res.content[0].text

    res = await server.call_tool(
        "species_range_check", {"species_name": "Ursus", "lat": 0, "lon": 0}
    )
    assert "failed" in res.content[0].text

    res = await server.call_tool("unusual_species_nearby", {"lat": 0, "lon": 0})
    assert "failed" in res.content[0].text

    res = await server.call_tool("get_dataset_metadata", {"dataset_key": "bad"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("search_occurrences", {"species_name": "Ursus"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("generate_citation", {"dataset_key": "bad"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("get_species_children", {"taxon_key": 999999})
    assert "failed" in res.content[0].text

    res = await server.call_tool("search_literature", {"query": "bad"})
    assert "failed" in res.content[0].text

    res = await server.call_tool("get_species_media", {"taxon_key": 999999})
    assert "failed" in res.content[0].text
