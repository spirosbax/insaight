"""
Tests for insaight/scraper.py — how an Apify run's outcome reaches the caller,
and the automly → harvestapi shape mapping in scrape_people.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from insaight import scraper
from insaight.mcp_server import scrape_people
from insaight.people import Person

COMPANY_URL = "https://www.linkedin.com/company/acme-charging"

# A short-mode row from automly/linkedin-company-employees-scraper
AUTOMLY_ROW = {
    "publicIdentifier": "jane-doe",
    "name": "Jane Doe",
    "headline": "CEO & Co-Founder at Acme Charging",
    "currentCompany": "Acme Charging",
    "company": {"name": "Acme Charging", "linkedinUrl": COMPANY_URL + "/"},
    "location": "Hooglede",
    "linkedinUrl": "https://www.linkedin.com/in/jane-doe",
}


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

    def test_capped_run_raises_empty_run_with_status_message(self):
        # harvestapi's free-plan cap: SUCCEEDED, no items, reason only in the status message
        client = fake_client(status_message="free user run limit exceeded")
        with pytest.raises(scraper.EmptyRun, match="free user run limit exceeded"):
            scraper._run_actor(client, "harvestapi/linkedin-company-employees", {})

    def test_failed_run_without_items_raises(self):
        with pytest.raises(RuntimeError, match="FAILED") as exc:
            scraper._run_actor(fake_client(status="FAILED"), "some/actor", {})
        assert not isinstance(exc.value, scraper.EmptyRun)

    def test_failed_run_keeps_partial_items(self):
        items = [{"id": "a"}]
        assert scraper._run_actor(fake_client(status="TIMED-OUT", items=items), "some/actor", {}) == items

    def test_run_that_never_started_raises(self):
        client = MagicMock()
        client.actor.return_value.call.return_value = None
        with pytest.raises(RuntimeError, match="failed to start"):
            scraper._run_actor(client, "some/actor", {})


class TestScrapePeople:
    def test_sends_automly_input(self):
        client = fake_client(items=[dict(AUTOMLY_ROW)])
        with patch("insaight.scraper.ApifyClient", return_value=client):
            scraper.scrape_people("token", COMPANY_URL, ["CEO", "Founder"], 10)
        client.actor.assert_called_with(scraper.PEOPLE_ACTOR_ID)
        client.actor.return_value.call.assert_called_with(run_input={
            "companies": [COMPANY_URL],
            "maxEmployeesPerCompany": 10,
            "fullProfiles": False,
            "jobTitles": ["CEO", "Founder"],
        })

    def test_maps_current_company_for_person_model(self):
        client = fake_client(items=[dict(AUTOMLY_ROW)])
        with patch("insaight.scraper.ApifyClient", return_value=client):
            items = scraper.scrape_people("token", COMPANY_URL)
        p = Person.from_apify_result(items[0], COMPANY_URL)
        assert p.profile_id == "jane-doe"
        assert p.name == "Jane Doe"
        assert p.location == "Hooglede"
        assert json.loads(p.current_companies) == ["Acme Charging"]
        assert p.current_titles is None  # automly has the title only inside the headline


class TestScrapePeopleToolRunStatus:
    def test_empty_run_says_no_people_with_actor_message(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        client = fake_client(status_message="0 employees from 1/1 sources")
        with patch("insaight.scraper.ApifyClient", return_value=client):
            result = scrape_people(url=COMPANY_URL, job_titles=["CEO"])
        assert result.startswith("No people returned")
        assert "0 employees from 1/1 sources" in result

    def test_failed_run_says_scrape_failed(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        client = fake_client(status="FAILED", status_message="Proxy error")
        with patch("insaight.scraper.ApifyClient", return_value=client):
            result = scrape_people(url=COMPANY_URL)
        assert result.startswith("Apify scrape failed")
        assert "Proxy error" in result
