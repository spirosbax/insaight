from apify_client import ApifyClient

# Post search (harvestapi/linkedin-post-search) needs searchQueries + authorUrls;
# profile/company feeds use targetUrls on linkedin-profile-posts instead.
ACTOR_ID = "harvestapi/linkedin-profile-posts"
PEOPLE_ACTOR_ID = "harvestapi/linkedin-company-employees"
PROFILE_ACTOR_ID = "harvestapi/linkedin-profile-scraper"
POST_COMMENTS_ACTOR_ID = "harvestapi/linkedin-post-comments"

# Profile scraper mode strings — Apify expects these exact labels.
PEOPLE_MODE_SHORT = "Short ($4 per 1k)"
PEOPLE_MODE_FULL = "Full ($8 per 1k)"
PROFILE_MODE_DETAILS = "Profile details no email ($4 per 1k)"
PROFILE_MODE_DETAILS_EMAIL = "Profile details + email search ($10 per 1k)"


def _dataset_id(run) -> str:
    # apify-client >= 3.0 returns a typed Run model (or None if the run
    # failed to start) instead of the old dict.
    if run is None:
        raise RuntimeError("Apify actor run failed to start (call() returned None)")
    return run.default_dataset_id


def scrape_account(api_token: str, profile_url: str, max_posts: int = 50) -> list[dict]:
    """Run the Apify LinkedIn post scraper for a single profile or company URL."""
    client = ApifyClient(api_token)

    run_input = {
        "targetUrls": [profile_url],
        "maxPosts": max_posts,
    }

    run = client.actor(ACTOR_ID).call(run_input=run_input)
    items = list(client.dataset(_dataset_id(run)).iterate_items())
    return items


def scrape_people(
    api_token: str,
    company_url: str,
    job_titles: list[str] | None = None,
    max_items: int = 50,
    full_mode: bool = False,
) -> list[dict]:
    """
    Scrape company employees from LinkedIn via Apify.

    Short mode ($4/1k) returns: name, headline, location, current position.
    Full mode ($8/1k) adds: about, experience[], education[], skills, certifications,
    languages, volunteer, projects, recommendations, follower/connection counts.

    Pass job_titles (e.g. ["CEO", "Founder", "CTO"]) to narrow results — otherwise
    returns all visible employees up to max_items.
    """
    client = ApifyClient(api_token)
    run_input: dict = {
        "companies": [company_url],
        "profileScraperMode": PEOPLE_MODE_FULL if full_mode else PEOPLE_MODE_SHORT,
        "maxItems": max_items,
        "companiesScrapingMode": "All at once",
    }
    if job_titles:
        run_input["jobTitles"] = job_titles

    run = client.actor(PEOPLE_ACTOR_ID).call(run_input=run_input)
    return list(client.dataset(_dataset_id(run)).iterate_items())


def scrape_person_profile(
    api_token: str,
    profile_url: str,
    with_email: bool = False,
) -> dict | None:
    """
    Enrich a single LinkedIn profile URL with full data via
    harvestapi/linkedin-profile-scraper.

    Returns: dict with experience, education, skills, certifications, languages,
    volunteer, projects, recommendations, about, top_skills, etc.
    — or None if the actor returned no results.

    Pricing: $4/1k without email, $10/1k with email search.
    """
    client = ApifyClient(api_token)
    run_input = {
        "queries": [profile_url],
        "profileScraperMode": PROFILE_MODE_DETAILS_EMAIL if with_email else PROFILE_MODE_DETAILS,
    }
    run = client.actor(PROFILE_ACTOR_ID).call(run_input=run_input)
    items = list(client.dataset(_dataset_id(run)).iterate_items())
    return items[0] if items else None


def scrape_post_comments(
    api_token: str,
    post_urls: list[str],
    max_items: int = 50,
    scrape_replies: bool = True,
    posted_limit: str = "any",
    profile_mode: str = "short",
) -> list[dict]:
    """
    Scrape comments on one or more LinkedIn posts via
    harvestapi/linkedin-post-comments.

    post_urls: LinkedIn post URLs (permalink or /feed/update/urn:li:activity:... form).
    profile_mode: "short" (free profile data) or "main" ($0.002/profile, more detail).
    """
    client = ApifyClient(api_token)
    run_input = {
        "posts": post_urls,
        "maxItems": max_items,
        "scrapeReplies": scrape_replies,
        "postedLimit": posted_limit,
        "profileScraperMode": profile_mode,
    }
    run = client.actor(POST_COMMENTS_ACTOR_ID).call(run_input=run_input)
    return list(client.dataset(_dataset_id(run)).iterate_items())


def scrape_accounts(api_token: str, profile_urls: list[str], max_posts: int = 50, verbose: bool = False) -> dict[str, list[dict]]:
    """Scrape multiple accounts sequentially. Returns {url: [items]}."""
    results = {}
    for url in profile_urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        if verbose:
            print(f"  Scraping: {url}")
        try:
            items = scrape_account(api_token, url, max_posts)
            results[url] = items
            if verbose:
                print(f"  -> Got {len(items)} posts")
        except Exception as e:
            print(f"  ERROR scraping {url}: {e}")
            results[url] = []
    return results
