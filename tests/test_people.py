"""
Tests for the people layer:
  - insaight/people.py  (Person model + from_apify_result)
  - insaight/db.py      (people CRUD)
  - insaight/mcp_server (scrape_people + list_people tools)
"""

import json
import sqlite3
import pytest
from datetime import datetime
from unittest.mock import patch

from insaight import db
from insaight.people import Person
from insaight.mcp_server import scrape_people, list_people, _slug


# ---------------------------------------------------------------------------
# Apify response fixtures
# ---------------------------------------------------------------------------

COMPANY_URL = "https://www.linkedin.com/company/acme-charging"
OTHER_URL   = "https://www.linkedin.com/company/other-corp"

SHORT_MODE_CEO = {
    "id": "ACoAAA111",
    "publicIdentifier": "jane-doe",
    "linkedinUrl": "https://www.linkedin.com/in/jane-doe",
    "firstName": "Jane",
    "lastName": "Doe",
    "headline": "CEO & Co-Founder at Acme Charging | Slimme Laadinfrastructuur",
    "location": {"linkedinText": "Hooglede, Flemish Region, Belgium"},
    "currentPosition": [{"companyName": "Acme Charging"}],
}

SHORT_MODE_EMPLOYEE = {
    "id": "ACoAAA222",
    "publicIdentifier": "john-smith",
    "linkedinUrl": "https://www.linkedin.com/in/john-smith",
    "firstName": "John",
    "lastName": "Smith",
    "headline": "Sales Manager at Acme Charging",
    "location": {"linkedinText": "Roeselare, Flemish Region, Belgium"},
    "currentPosition": [{"companyName": "Acme Charging"}],
}

FULL_MODE_WITH_EXPERIENCE = {
    "id": "ACoAAA333",
    "publicIdentifier": "alex-brown",
    "linkedinUrl": "https://www.linkedin.com/in/alex-brown",
    "firstName": "Alex",
    "lastName": "Brown",
    "headline": "Operations Director",
    "location": {"linkedinText": "Kortrijk, Belgium"},
    "currentPosition": [{"position": "Operations Director", "companyName": "Acme Charging"}],
    "experience": [
        {"position": "Operations Director", "companyName": "Acme Charging",
         "endDate": {"text": "Present"}},
        {"position": "Logistics Manager", "companyName": "OtherCo",
         "endDate": {"month": "Jan", "year": 2022, "text": "Jan 2022"}},
    ],
}

MINIMAL_PERSON = {
    # No id — should fall back to hash
    "firstName": "Unknown",
    "lastName": "Employee",
    "headline": "Staff member",
}

NO_NAME_PERSON = {
    "id": "ACoAAA999",
    "linkedinUrl": "https://www.linkedin.com/in/anonymous",
    # No firstName/lastName
    "headline": "Some role",
    "location": {"linkedinText": "Belgium"},
    "currentPosition": [],
}


# ---------------------------------------------------------------------------
# Person.from_apify_result
# ---------------------------------------------------------------------------

class TestPersonModel:
    def test_id_extracted(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert p.profile_id == "ACoAAA111"

    def test_fallback_hash_when_no_id(self):
        p = Person.from_apify_result(MINIMAL_PERSON, COMPANY_URL)
        assert p.profile_id.startswith("hash:")

    def test_hash_is_deterministic(self):
        p1 = Person.from_apify_result(MINIMAL_PERSON, COMPANY_URL)
        p2 = Person.from_apify_result(MINIMAL_PERSON, COMPANY_URL)
        assert p1.profile_id == p2.profile_id

    def test_name_assembled_from_first_last(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert p.name == "Jane Doe"
        assert p.first_name == "Jane"
        assert p.last_name == "Doe"

    def test_headline_extracted(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert "CEO" in p.headline
        assert "Acme Charging" in p.headline

    def test_linkedin_url(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert p.linkedin_url == "https://www.linkedin.com/in/jane-doe"

    def test_company_url_preserved(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert p.company_url == COMPANY_URL

    def test_location_from_nested_dict(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert "Hooglede" in p.location

    def test_current_companies_from_currentPosition(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        companies = json.loads(p.current_companies)
        assert "Acme Charging" in companies

    def test_current_titles_from_full_mode_position(self):
        p = Person.from_apify_result(FULL_MODE_WITH_EXPERIENCE, COMPANY_URL)
        titles = json.loads(p.current_titles)
        assert "Operations Director" in titles

    def test_current_titles_none_when_short_mode_bare(self):
        # Short mode currentPosition has no 'position' key
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        # current_titles may be None or empty — should not crash
        if p.current_titles is not None:
            titles = json.loads(p.current_titles)
            assert isinstance(titles, list)

    def test_experience_fallback_for_current_title(self):
        # Short mode with no 'position' in currentPosition uses experience
        item = {
            **SHORT_MODE_EMPLOYEE,
            "experience": [
                {"position": "Sales Manager", "companyName": "Acme Charging",
                 "endDate": {"text": "Present"}},
            ],
        }
        p = Person.from_apify_result(item, COMPANY_URL)
        # headline already contains title — experience fallback only used when currentPosition bare
        assert p.headline is not None

    def test_no_name_person_does_not_crash(self):
        p = Person.from_apify_result(NO_NAME_PERSON, COMPANY_URL)
        assert p.profile_id == "ACoAAA999"

    def test_raw_json_serialized(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        parsed = json.loads(p.raw_json)
        assert isinstance(parsed, dict)

    def test_scraped_at_is_iso_timestamp(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        dt = datetime.fromisoformat(p.scraped_at)
        assert dt.year >= 2026


# ---------------------------------------------------------------------------
# DB people CRUD
# ---------------------------------------------------------------------------

def make_person(profile_id="p001", company_url=COMPANY_URL, name="Test User",
                headline="CEO at TestCo", **kwargs):
    defaults = dict(
        profile_id=profile_id, linkedin_url=f"https://li.com/in/{profile_id}",
        company_url=company_url, name=name, first_name="Test", last_name="User",
        headline=headline, current_titles=json.dumps(["CEO"]),
        current_companies=json.dumps(["TestCo"]),
        location="Belgium", scraped_at=datetime.now().isoformat(), raw_json="{}",
    )
    defaults.update(kwargs)
    return Person(**defaults)


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class TestPeopleDB:
    def test_insert_person_returns_true(self):
        conn = fresh_conn()
        assert db.insert_person(conn, make_person()) is True

    def test_insert_duplicate_returns_false(self):
        conn = fresh_conn()
        p = make_person()
        db.insert_person(conn, p)
        assert db.insert_person(conn, p) is False

    def test_upsert_updates_existing(self):
        conn = fresh_conn()
        p = make_person(headline="Old headline")
        db.insert_person(conn, p)
        p2 = make_person(headline="New headline")  # same profile_id
        is_new = db.upsert_person(conn, p2)
        assert is_new is False
        row = conn.execute("SELECT headline FROM people WHERE profile_id='p001'").fetchone()
        assert row["headline"] == "New headline"

    def test_insert_people_counts(self):
        conn = fresh_conn()
        people = [make_person("a"), make_person("b"), make_person("c")]
        new, updated = db.insert_people(conn, people)
        assert new == 3
        assert updated == 0

    def test_insert_people_second_run_all_updated(self):
        conn = fresh_conn()
        people = [make_person("a"), make_person("b")]
        db.insert_people(conn, people)
        new, updated = db.insert_people(conn, people)
        assert new == 0
        assert updated == 2

    def test_get_people_returns_for_company(self):
        conn = fresh_conn()
        db.insert_person(conn, make_person("p1", company_url=COMPANY_URL))
        db.insert_person(conn, make_person("p2", company_url=OTHER_URL))
        rows = db.get_people(conn, COMPANY_URL)
        assert len(rows) == 1
        assert rows[0]["profile_id"] == "p1"

    def test_get_people_role_filter_headline(self):
        conn = fresh_conn()
        db.insert_person(conn, make_person("ceo1", headline="CEO & Founder",
                                           current_titles=json.dumps(["CEO"])))
        db.insert_person(conn, make_person("dev1", headline="Software Engineer",
                                           current_titles=json.dumps(["Engineer"])))
        rows = db.get_people(conn, COMPANY_URL, role_query="CEO")
        assert len(rows) == 1
        assert rows[0]["profile_id"] == "ceo1"

    def test_get_people_role_filter_titles_json(self):
        conn = fresh_conn()
        db.insert_person(conn, make_person("p1", current_titles=json.dumps(["Founder", "CEO"])))
        db.insert_person(conn, make_person("p2", current_titles=json.dumps(["Engineer"])))
        rows = db.get_people(conn, COMPANY_URL, role_query="Founder")
        assert len(rows) == 1

    def test_get_people_role_filter_name(self):
        conn = fresh_conn()
        db.insert_person(conn, make_person("p1", name="Alice Smith"))
        db.insert_person(conn, make_person("p2", name="Bob Jones"))
        rows = db.get_people(conn, COMPANY_URL, role_query="Alice")
        assert len(rows) == 1

    def test_get_people_respects_limit(self):
        conn = fresh_conn()
        for i in range(10):
            db.insert_person(conn, make_person(f"p{i}"))
        rows = db.get_people(conn, COMPANY_URL, limit=3)
        assert len(rows) == 3

    def test_get_people_stats(self):
        conn = fresh_conn()
        db.insert_person(conn, make_person("p1", company_url=COMPANY_URL))
        db.insert_person(conn, make_person("p2", company_url=OTHER_URL))
        stats = db.get_people_stats(conn)
        assert stats["total_people"] == 2
        assert stats["companies_with_people"] == 2
        assert stats["last_scraped"] is not None


# ---------------------------------------------------------------------------
# MCP tools — scrape_people + list_people
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = db.get_connection(str(path))
    db.init_db(conn)
    # Seed a post so list_accounts() / _resolve_account() can find the slug
    conn.execute(
        """INSERT INTO posts (post_urn, post_url, content, posted_timestamp, account_url,
           scraped_at, raw_json) VALUES (?,?,?,?,?,?,?)""",
        ("urn1", None, "post text", "2026-01-01T00:00:00", COMPANY_URL,
         datetime.now().isoformat(), "{}"),
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def patch_db(db_path):
    real = db.get_connection
    with patch("insaight.mcp_server.db.get_connection",
               side_effect=lambda *a, **kw: real(str(db_path))):
        yield


def fake_apify_items(n=2):
    items = []
    roles = ["CEO & Co-Founder", "Sales Manager", "CTO", "Operations Lead"]
    for i in range(n):
        items.append({
            "id": f"ACoFAKE{i:03d}",
            "firstName": f"Person{i}",
            "lastName": "Test",
            "linkedinUrl": f"https://www.linkedin.com/in/person{i}",
            "headline": f"{roles[i % len(roles)]} at Acme Charging",
            "location": {"linkedinText": "Belgium"},
            "currentPosition": [{"companyName": "Acme Charging"}],
        })
    return items


class TestScrapePeopleTool:
    def test_missing_token_returns_error(self, monkeypatch):
        monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
        result = scrape_people(url=COMPANY_URL)
        assert "APIFY_API_TOKEN" in result

    def test_invalid_url_returns_error(self):
        result = scrape_people(url="not-a-linkedin-url")
        assert "does not look like" in result

    def test_successful_scrape_stores_people(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        with patch("insaight.mcp_server.scraper.scrape_people", return_value=fake_apify_items(3)), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = json.loads(scrape_people(url=COMPANY_URL))

        assert result["new_people_stored"] == 3
        assert result["updated"] == 0
        assert result["account_slug"] == "acme-charging"
        assert "list_people" in result["message"]

    def test_second_scrape_updates_not_duplicates(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        with patch("insaight.mcp_server.scraper.scrape_people", return_value=fake_apify_items(2)), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_people(url=COMPANY_URL)
            result = json.loads(scrape_people(url=COMPANY_URL))

        assert result["new_people_stored"] == 0
        assert result["updated"] == 2

    def test_empty_response_returns_message(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        with patch("insaight.mcp_server.scraper.scrape_people", return_value=[]):
            result = scrape_people(url=COMPANY_URL)
        assert "No people returned" in result

    def test_apify_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        with patch("insaight.mcp_server.scraper.scrape_people",
                   side_effect=Exception("timeout")):
            result = scrape_people(url=COMPANY_URL)
        assert "timeout" in result

    def test_max_items_capped_at_200(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, url, job_titles, max_items, full_mode=False):
            captured["max_items"] = max_items
            return []

        with patch("insaight.mcp_server.scraper.scrape_people", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_people(url=COMPANY_URL, max_items=9999)

        assert captured["max_items"] == 200

    def test_job_titles_passed_to_scraper(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, url, job_titles, max_items, full_mode=False):
            captured["job_titles"] = job_titles
            return []

        with patch("insaight.mcp_server.scraper.scrape_people", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_people(url=COMPANY_URL, job_titles=["CEO", "Founder"])

        assert captured["job_titles"] == ["CEO", "Founder"]


class TestListPeopleTool:
    def _seed_people(self, db_path):
        real = db.get_connection
        conn = real(str(db_path))
        conn.execute(
            """INSERT INTO people (profile_id, linkedin_url, company_url, name,
               first_name, last_name, headline, current_titles, current_companies,
               location, scraped_at, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("id001", "https://li.com/in/jane", COMPANY_URL, "Jane Doe",
             "Jane", "Doe", "CEO & Co-Founder at Acme Charging",
             json.dumps(["CEO"]), json.dumps(["Acme Charging"]),
             "Belgium", datetime.now().isoformat(), "{}"),
        )
        conn.execute(
            """INSERT INTO people (profile_id, linkedin_url, company_url, name,
               first_name, last_name, headline, current_titles, current_companies,
               location, scraped_at, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("id002", "https://li.com/in/john", COMPANY_URL, "John Smith",
             "John", "Smith", "Sales Manager at Acme Charging",
             json.dumps(["Sales Manager"]), json.dumps(["Acme Charging"]),
             "Roeselare, Belgium", datetime.now().isoformat(), "{}"),
        )
        conn.commit()
        conn.close()

    def test_returns_people_by_slug(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging"))
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "Jane Doe" in names

    def test_role_filter_ceo(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging", role="CEO"))
        assert len(result) == 1
        assert result[0]["name"] == "Jane Doe"

    def test_role_filter_sales(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging", role="Sales"))
        assert len(result) == 1
        assert result[0]["name"] == "John Smith"

    def test_result_includes_linkedin_url(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging"))
        for r in result:
            assert "linkedin_url" in r

    def test_result_does_not_include_raw_json(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging"))
        for r in result:
            assert "raw_json" not in r

    def test_current_titles_decoded_to_list(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account="acme-charging", role="CEO"))
        assert result[0]["current_titles"] == ["CEO"]

    def test_empty_db_returns_helpful_message(self, db_path):
        result = list_people(account="acme-charging")
        assert "scrape_people" in result

    def test_unknown_account_returns_error(self):
        result = list_people(account="no-such-company")
        assert "No account matching" in result or "scrape_people" in result

    def test_full_url_accepted(self, db_path):
        self._seed_people(db_path)
        result = json.loads(list_people(account=COMPANY_URL))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Full-mode / linkedin-profile-scraper enrichment
# ---------------------------------------------------------------------------

FULL_PROFILE_APIFY = {
    "id": "ACoAAA555",
    "publicIdentifier": "jane-doe",
    "linkedinUrl": "https://www.linkedin.com/in/jane-doe",
    "firstName": "Jane",
    "lastName": "Doe",
    "headline": "VP Engineering",
    "about": "Built and led engineering at two startups. TU Delft alum.",
    "location": {"linkedinText": "Amsterdam, Netherlands"},
    "currentPosition": [
        {"position": "VP Engineering", "companyName": "Acme", "companyLinkedinUrl": "https://www.linkedin.com/company/acme"}
    ],
    "experience": [
        {"position": "VP Engineering", "companyName": "Acme", "endDate": {"text": "Present"}},
        {"position": "Senior Engineer", "companyName": "Stripe", "startDate": {"year": 2018}, "endDate": {"year": 2020}},
    ],
    "education": [
        {"schoolName": "TU Delft", "degree": "MSc", "fieldOfStudy": "Computer Science"},
    ],
    "skills": ["Python", "Distributed Systems", "Leadership"],
    "topSkills": ["Python", "Leadership"],
    "certifications": [{"name": "AWS Solutions Architect", "issuer": "Amazon"}],
    "languages": [{"name": "English", "proficiency": "Native"}, {"name": "Dutch", "proficiency": "Fluent"}],
    "volunteer": [{"role": "Mentor", "organization": "Code for NL"}],
    "projects": [{"name": "OpenMetrics"}],
    "recommendations": [{"text": "Excellent engineer"}],
    "followerCount": 4200,
    "connectionsCount": 500,
}


class TestFullModeEnrichment:
    def test_about_extracted(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        assert "TU Delft" in p.about

    def test_experience_stored_as_json(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        exp = json.loads(p.experience)
        assert len(exp) == 2
        assert exp[1]["companyName"] == "Stripe"

    def test_education_stored_as_json(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        edu = json.loads(p.education)
        assert edu[0]["schoolName"] == "TU Delft"

    def test_skills_and_top_skills(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        assert "Python" in json.loads(p.skills)
        assert "Python" in json.loads(p.top_skills)

    def test_languages_captured(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        langs = json.loads(p.languages)
        assert any(l["name"] == "Dutch" for l in langs)

    def test_volunteer_captured(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        vol = json.loads(p.volunteer)
        assert vol[0]["organization"] == "Code for NL"

    def test_follower_connection_counts(self):
        p = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        assert p.follower_count == 4200
        assert p.connections_count == 500

    def test_short_mode_leaves_extended_fields_none(self):
        p = Person.from_apify_result(SHORT_MODE_CEO, COMPANY_URL)
        assert p.about is None
        assert p.experience is None
        assert p.education is None
        assert p.languages is None
        assert p.follower_count is None

    def test_top_skills_comma_string(self):
        item = {**SHORT_MODE_CEO, "topSkills": "AI, Python, NLP"}
        p = Person.from_apify_result(item, COMPANY_URL)
        assert json.loads(p.top_skills) == ["AI", "Python", "NLP"]


# ---------------------------------------------------------------------------
# DB migration + partial upsert
# ---------------------------------------------------------------------------

class TestDBMigrationAndUpsert:
    def test_init_db_adds_extended_columns(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        # Simulate an old schema without extended columns
        conn = db.get_connection(str(db_path))
        conn.execute("DROP TABLE IF EXISTS people")
        conn.execute("""
            CREATE TABLE people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT UNIQUE NOT NULL,
                linkedin_url TEXT,
                company_url TEXT NOT NULL,
                name TEXT,
                first_name TEXT,
                last_name TEXT,
                headline TEXT,
                current_titles TEXT,
                current_companies TEXT,
                location TEXT,
                scraped_at TEXT NOT NULL,
                raw_json TEXT
            )
        """)
        conn.commit()

        db.init_db(conn)

        cols = {row[1] for row in conn.execute("PRAGMA table_info(people)").fetchall()}
        for col in ("about", "experience", "education", "skills", "top_skills",
                    "certifications", "languages", "volunteer", "projects",
                    "recommendations", "follower_count", "connections_count"):
            assert col in cols, f"migration missed column: {col}"
        conn.close()

    def test_partial_upsert_preserves_prior_enrichment(self, tmp_path):
        """A subsequent Short-mode scrape must not blank out Full-mode fields."""
        db_path = tmp_path / "upsert.db"
        conn = db.get_connection(str(db_path))
        db.init_db(conn)

        # First write: full enrichment
        full = Person.from_apify_result(FULL_PROFILE_APIFY, COMPANY_URL)
        assert db.insert_person(conn, full) is True

        # Second write: short-mode for the same profile_id
        short = Person.from_apify_result(
            {**SHORT_MODE_CEO, "id": "ACoAAA555"}, COMPANY_URL
        )
        assert db.upsert_person(conn, short) is False  # not new

        row = conn.execute(
            "SELECT * FROM people WHERE profile_id = ?", ("ACoAAA555",)
        ).fetchone()

        # Enrichment fields must still be present
        assert row["about"] is not None and "TU Delft" in row["about"]
        assert row["experience"] is not None
        assert row["education"] is not None
        assert row["languages"] is not None
        # Short-mode scalars should have been updated
        assert row["name"] == "Jane Doe"
        conn.close()


# ---------------------------------------------------------------------------
# scrape_person_profile MCP tool
# ---------------------------------------------------------------------------

from insaight.mcp_server import scrape_person_profile


class TestScrapePersonProfileTool:
    def test_missing_token_errors(self, monkeypatch):
        monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
        result = scrape_person_profile(url="https://www.linkedin.com/in/jane-doe")
        assert "APIFY_API_TOKEN" in result

    def test_invalid_url_rejected(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        result = scrape_person_profile(url="https://example.com/foo")
        assert "does not look like a LinkedIn URL" in result

    def test_enriches_and_stores(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        def fake_scrape(token, url, with_email=False):
            return FULL_PROFILE_APIFY

        with patch("insaight.mcp_server.scraper.scrape_person_profile", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = scrape_person_profile(url="https://www.linkedin.com/in/jane-doe")

        payload = json.loads(result)
        assert payload["name"] == "Jane Doe"
        assert payload["stored_as"] == "new"
        assert "experience" in payload["enriched_fields"]
        assert "education" in payload["enriched_fields"]
        assert "languages" in payload["enriched_fields"]

    def test_uses_company_url_from_currentposition_when_none_given(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        def fake_scrape(token, url, with_email=False):
            return FULL_PROFILE_APIFY

        with patch("insaight.mcp_server.scraper.scrape_person_profile", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = scrape_person_profile(url="https://www.linkedin.com/in/jane-doe")

        payload = json.loads(result)
        assert payload["company_url"] == "https://www.linkedin.com/company/acme"

    def test_no_result_returns_message(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        with patch("insaight.mcp_server.scraper.scrape_person_profile", return_value=None), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = scrape_person_profile(url="https://www.linkedin.com/in/missing-person")
        assert "No profile returned" in result


# ---------------------------------------------------------------------------
# scrape_people full_mode toggle
# ---------------------------------------------------------------------------

class TestScrapePeopleFullMode:
    def test_full_mode_flag_passed_through(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, url, job_titles, max_items, full_mode=False):
            captured["full_mode"] = full_mode
            return []

        with patch("insaight.mcp_server.scraper.scrape_people", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_people(url=COMPANY_URL, full_mode=True)

        assert captured["full_mode"] is True

    def test_default_mode_is_short(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, url, job_titles, max_items, full_mode=False):
            captured["full_mode"] = full_mode
            return []

        with patch("insaight.mcp_server.scraper.scrape_people", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_people(url=COMPANY_URL)

        assert captured["full_mode"] is False
