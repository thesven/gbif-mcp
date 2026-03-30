from gbif_mcp.client import GbifClient


def test_species_range_check_assesses_expected_status(monkeypatch) -> None:
    client = GbifClient()

    def fake_occurrences(lat, lon, radius_km=50, limit=25, species_name=None, years_back=None):
        if years_back == 5:
            return {"records": [{"species": species_name}] * 4}
        return {"records": [{"species": species_name}] * 9}

    monkeypatch.setattr(client, "species_occurrences_nearby", fake_occurrences)
    monkeypatch.setattr(client, "species_occurrence_history", lambda *args, **kwargs: {"records": [{"species": "owl"}] * 9})

    result = client.species_range_check("Snowy Owl", 43.7, -79.4)

    assert result["assessment"]["status"] == "expected"
