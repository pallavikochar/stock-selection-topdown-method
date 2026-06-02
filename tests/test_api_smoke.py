"""Smoke tests: API endpoints respond correctly when output files exist."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_demo_data(tmp_path):
    """Create a test client with fake agent output files."""
    output_dir = tmp_path / "agents"
    output_dir.mkdir()

    # Write minimal fake agent outputs
    for name in ["economy", "cycle", "scenario", "sector", "style", "screen",
                 "fundamental", "valuation", "risk_correlation", "recommendations"]:
        fake = {
            "agent_name": name,
            "run_id": "test123",
            "as_of_date": "2026-06-02",
            "confidence": 70.0,
            "confidence_label": "Medium",
            "rationale": "Demo rationale",
            "data": {},
            "warnings": [],
            "provenance": {},
        }
        (output_dir / f"{name}.json").write_text(json.dumps(fake))

    # Recommendations needs real-ish data
    recs_data = {
        "agent_name": "recommendations",
        "run_id": "test123",
        "as_of_date": "2026-06-02",
        "confidence": 72.0,
        "confidence_label": "Medium",
        "rationale": "Top: XOM, CVX",
        "data": {
            "ranked": [],
            "correlation_regime": "High",
            "recommended_position_count_rationale": "Demo guidance",
            "as_of_date": "2026-06-02",
        },
        "warnings": [],
        "provenance": {},
    }
    (output_dir / "recommendations.json").write_text(json.dumps(recs_data))

    with patch("api.main.OUTPUT_DIR", output_dir):
        from api.main import app
        yield TestClient(app)


def test_list_agents(client_with_demo_data):
    r = client_with_demo_data.get("/api/agents")
    assert r.status_code == 200
    data = r.json()
    assert "agents" in data


def test_get_economy_agent(client_with_demo_data):
    r = client_with_demo_data.get("/api/agents/economy")
    assert r.status_code == 200
    assert r.json()["agent_name"] == "economy"


def test_get_unknown_agent_returns_400(client_with_demo_data):
    r = client_with_demo_data.get("/api/agents/nonexistent_agent")
    assert r.status_code == 400


def test_get_recommendations(client_with_demo_data):
    r = client_with_demo_data.get("/api/recommendations")
    assert r.status_code == 200


def test_funnel_endpoint(client_with_demo_data):
    r = client_with_demo_data.get("/api/funnel")
    assert r.status_code == 200
    data = r.json()
    assert "funnel" in data
