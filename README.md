# gbif-mcp

[![CI](https://github.com/thesven/gbif-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/thesven/gbif-mcp/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance, agent-optimized **Model Context Protocol (MCP)** server for querying global biodiversity occurrence records, taxonomic backbone classifications, and historical species distribution data from the [Global Biodiversity Information Facility (GBIF)](https://www.gbif.org/).

Built to work seamlessly with AI assistants (Claude Desktop, Cursor, Antigravity, and custom agent architectures) alongside `@thesven/inaturalist-mcp` and `@thesven/ebird-mcp`.

---

## Key Features

- **Cross-Platform Taxon Bridge**: Seamlessly bridges iNaturalist Taxon IDs, eBird Species Codes, and GBIF Backbone Keys into a single unified taxonomic identity.
- **Agent-Optimized Token Footprint**: Unlike standard Darwin Core exports that dump 150+ raw fields, `gbif-mcp` projects occurrences into concise, semantically clean records (coordinates, uncertainty, dates, basis of record, locality, and media).
- **Authoritative Taxonomic Backbone**: Fuzzily or strictly resolve species and vernacular names into canonical classifications, ranks, and accepted keys.
- **Geospatial Range & History Analysis**: Differentiate between expected, uncommon, historic-only, and undocumented occurrences within a user-defined radius.
- **Academic Attribution & Citation Generator**: Automatically generate official DOI research citations and attribution statements for GBIF datasets.
- **Specimen & Observation Filtering**: Filter by Darwin Core `basisOfRecord` (`HUMAN_OBSERVATION`, `PRESERVED_SPECIMEN`, `MACHINE_OBSERVATION`, `FOSSIL_SPECIMEN`).
- **Zero-Credential Read Access**: Connects to GBIF's open REST API v1 without mandatory API keys.

---

## Available Tools

| Tool | Description |
| :--- | :--- |
| `resolve_taxon_bridge` | Bridge cross-platform IDs between iNaturalist, eBird, and GBIF taxonomic backbone. |
| `search_occurrences` | Search GBIF occurrences with Darwin Core filtering and token-optimized slim projections. |
| `generate_citation` | Generate academic research citation, DOI link, and attribution statement for a dataset. |
| `match_species` | Match a scientific or common species name against the GBIF backbone taxonomy. |
| `search_species` | Search and auto-complete taxa by query string. |
| `get_species_details` | Retrieve full taxonomic classification and lineage for a taxon key. |
| `species_occurrences_nearby` | Search occurrence records around GPS coordinates with radius, year, and basis filters. |
| `species_occurrence_history` | Fetch multi-decade historical occurrence records to evaluate population timelines. |
| `species_range_check` | Evaluate whether a species presence is expected, sparse, historic-only, or anomalous. |
| `unusual_species_nearby` | Identify species with low local observation frequencies in a target radius. |
| `get_dataset_metadata` | Fetch provenance, publisher title, license, and citation DOI for research datasets. |

---

## Installation & Usage

### Running with `uvx` (Recommended)

```bash
uvx --from git+https://github.com/thesven/gbif-mcp.git gbif-mcp
```

### Running with Python virtual environment

```bash
git clone https://github.com/thesven/gbif-mcp.git
cd gbif-mcp
uv sync
uv run gbif-mcp --transport stdio
```

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gbif": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/thesven/gbif-mcp.git", "gbif-mcp"]
    }
  }
}
```

---

## Development & Quality Gate

```bash
# Run code formatting check
uv run ruff format --check src tests scripts

# Run linting
uv run ruff check src tests scripts

# Run test suite with strict coverage floor (>90%)
uv run pytest --cov=gbif_mcp --cov-branch --cov-report=term-missing

# Build wheel and sdist
uv build

# Run package distribution check & smoke test
uv run python scripts/check_dist.py
uv run python scripts/smoke.py
```

## License

MIT License. See [LICENSE](LICENSE) for details.
