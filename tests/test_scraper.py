"""
Tests for insaight/scraper.py — how an Apify run's outcome reaches the caller.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from insaight import scraper
from insaight.mcp_server import scrape_people

COMPANY_URL = "https://www.linkedin.com/company/acme-charging"


def fake_client(status="SUCCEEDED", status_message=None, items=()):
    """An ApifyClient stand-in whose actor run ends as described."""
    client = MagicMock()
    client.actor.return_value.call.return_value = SimpleNamespace(
        id="RUN123", status=status, status_message=status_message, default_dataset_id="DS123",
    )
    client.dataset.return_value.iterate_items.return_value = iter(items)
    return client


class TestRunActor:
    def test_returns_items(self):
        items = [{"id": "a"}, {"id": "b"}]
        assert scraper._run_actor(fake_client(items=items), "some/actor", {}) == items

    def test_clean_empty_run_returns_empty_list(self):
        assert scraper._run_actor(fake_client(), "some/actor", {}) == []

    def test_capped_run_raises_with_status_message(self):
        # harvestapi's free-plan cap: SUCCEEDED, no items, reason only in the status message
        client = fake_client(status_message="free user run limit exceeded")
        with pytest.raises(RuntimeError, match="free user run limit exceeded"):
            scraper._run_actor(client, "harvestapi/linkedin-company-employees", {})

    def test_failed_run_without_items_raises(self):
        with pytest.raises(RuntimeError, match="FAILED"):
            scraper._run_actor(fake_client(status="FAILED"), "some/actor", {})

    def test_failed_run_keeps_partial_items(self):
        items = [{"id": "a"}]
        assert scraper._run_actor(fake_client(status="TIMED-OUT", items=items), "some/actor", {}) == items

    def test_run_that_never_started_raises(self):
        client = MagicMock()
        client.actor.return_value.call.return_value = None
        with pytest.raises(RuntimeError, match="failed to start"):
            scraper._run_actor(client, "some/actor", {})


class TestScrapePeopleSurfacesRunStatus:
    def test_capped_run_reaches_tool_response(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        client = fake_client(status_message="free user run limit exceeded")
        with patch("insaight.scraper.ApifyClient", return_value=client):
            result = scrape_people(url=COMPANY_URL, job_titles=["CEO"])
        assert "free user run limit exceeded" in result
        assert "No people returned" not in result
