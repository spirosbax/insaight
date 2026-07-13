"""
Person model — normalises output from harvestapi/linkedin-company-employees
(Short and Full modes) and harvestapi/linkedin-profile-scraper (full profile).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Person:
    profile_id: str
    linkedin_url: str | None
    company_url: str
    name: str | None
    first_name: str | None
    last_name: str | None
    headline: str | None
    current_titles: str | None   # JSON list of title strings
    current_companies: str | None  # JSON list of company name strings
    location: str | None
    scraped_at: str
    raw_json: str

    # Extended fields (populated by Full mode or linkedin-profile-scraper).
    # All optional so existing Short-mode scrapes stay backward-compatible.
    about: str | None = None
    experience: str | None = None        # JSON list of {position, companyName, duration, ...}
    education: str | None = None         # JSON list of {schoolName, degree, field, ...}
    skills: str | None = None            # JSON list of skill names
    top_skills: str | None = None        # JSON list of top skill names
    certifications: str | None = None    # JSON list of {name, issuer, ...}
    languages: str | None = None         # JSON list of {name, proficiency}
    volunteer: str | None = None         # JSON list of {role, organization, ...}
    projects: str | None = None          # JSON list of {name, description, ...}
    recommendations: str | None = None   # JSON list of recommendations
    follower_count: int | None = None
    connections_count: int | None = None

    @classmethod
    def from_apify_result(cls, item: dict, company_url: str) -> "Person":
        profile_id = (
            item.get("id")
            or item.get("publicIdentifier")
            or item.get("profileId")
        )
        if not profile_id:
            # Fallback: hash the LinkedIn URL so we always have a dedup key
            import hashlib
            raw = item.get("linkedinUrl") or item.get("profileUrl") or str(item)
            profile_id = f"hash:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

        linkedin_url = item.get("linkedinUrl") or item.get("profileUrl")

        first_name = item.get("firstName") or ""
        last_name = item.get("lastName") or ""
        name = f"{first_name} {last_name}".strip() or item.get("name") or item.get("fullName")

        headline = item.get("headline") or item.get("summary")

        # Current positions — Short mode returns [{companyName}], Full adds {position}
        current_positions = item.get("currentPosition") or []
        current_titles = [
            p.get("position") or p.get("title") or ""
            for p in current_positions
            if p.get("position") or p.get("title")
        ]
        current_companies = [
            p.get("companyName") or ""
            for p in current_positions
            if p.get("companyName")
        ]

        # Fallback: parse titles from experience if currentPosition is bare
        if not current_titles and item.get("experience"):
            for exp in item["experience"]:
                if not exp.get("endDate") or exp.get("endDate", {}).get("text") == "Present":
                    title = exp.get("position") or exp.get("title")
                    if title:
                        current_titles.append(title)
                        break  # take only the most recent

        location_obj = item.get("location") or {}
        if isinstance(location_obj, dict):
            location = location_obj.get("linkedinText") or location_obj.get("text")
        else:
            location = str(location_obj) if location_obj else None

        # Extended fields — only populated when the actor returns them (Full mode).
        def _opt_json(key: str) -> str | None:
            val = item.get(key)
            if val is None or val == [] or val == {}:
                return None
            return json.dumps(val, default=str)

        about = item.get("about") or item.get("summary_long")

        top_skills_raw = item.get("topSkills")
        if isinstance(top_skills_raw, list) and top_skills_raw:
            top_skills = json.dumps(top_skills_raw)
        elif isinstance(top_skills_raw, str) and top_skills_raw.strip():
            # Some actors return a single comma-separated string
            top_skills = json.dumps([s.strip() for s in top_skills_raw.split(",") if s.strip()])
        else:
            top_skills = None

        follower_count = item.get("followerCount")
        connections_count = item.get("connectionsCount")

        return cls(
            profile_id=profile_id,
            linkedin_url=linkedin_url,
            company_url=company_url,
            name=name,
            first_name=first_name or None,
            last_name=last_name or None,
            headline=headline,
            current_titles=json.dumps(current_titles) if current_titles else None,
            current_companies=json.dumps(current_companies) if current_companies else None,
            location=location,
            scraped_at=datetime.now().isoformat(),
            raw_json=json.dumps(item, default=str),
            about=about,
            experience=_opt_json("experience"),
            education=_opt_json("education"),
            skills=_opt_json("skills"),
            top_skills=top_skills,
            certifications=_opt_json("certifications"),
            languages=_opt_json("languages"),
            volunteer=_opt_json("volunteer") or _opt_json("volunteering"),
            projects=_opt_json("projects"),
            recommendations=_opt_json("recommendations"),
            follower_count=follower_count if isinstance(follower_count, int) else None,
            connections_count=connections_count if isinstance(connections_count, int) else None,
        )
