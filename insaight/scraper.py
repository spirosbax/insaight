from apify_client import ApifyClient

# Post search (harvestapi/linkedin-post-search) needs searchQueries + authorUrls;
# profile/company feeds use targetUrls on linkedin-profile-posts instead.
ACTOR_ID = "harvestapi/linkedin-profile-posts"
# harvestapi/linkedin-company-employees caps free Apify plans at 10 runs in
# total; automly's employee scraper runs on the free plan's monthly credit.
PEOPLE_ACTOR_ID = "automly/linkedin-company-employees-scraper"
PROFILE_ACTOR_ID = "harvestapi/linkedin-profile-scraper"
POST_COMMENTS_ACTOR_ID = "harvestapi/linkedin-post-comments"

# Profile scraper mode strings — Apify expects these exact labels.
PROFILE_MODE_DETAILS = "Profile details no email ($4 per 1k)"
PROFILE_MODE_DETAILS_EMAIL = "Profile details + email search ($10 per 1k)"


class EmptyRun(RuntimeError):
    """
    A run that succeeded with no items but said why in its status message.

    For some actors that is a failure in disguise (harvestapi's free-plan cap:
    "free user run limit exceeded"), for others a normal summary (automly:
    "0 employees from 1/1 sources"), so callers choose how to word it.
    """


def _run_actor(client: ApifyClient, actor_id: str, run_input: dict) -> list[dict]:
    """
    Run an actor and return its dataset items.

    An empty dataset is only returned as [] when the run succeeded without a
    status message. A failed run raises RuntimeError and a succeeded one with
    a status message raises EmptyRun — [] would hide the actor's explanation
    and reach the user as a bare "nothing found".
    """
    run = client.actor(actor_id).call(run_input=run_input)
    # apify-client >= 3.0 returns a typed Run model (or None if the run
    # failed to start) instead of the old dict.
    if run is None:
        raise RuntimeError(f"{actor_id} run failed to start (call() returned None)")

    items = list(client.dataset(run.default_dataset_id).iterate_items())
    if not items and run.status != "SUCCEEDED":
        detail = f": {run.status_message}" if run.status_message else ""
        raise RuntimeError(f"{actor_id} run {run.id} ended {run.status} with no items{detail}")
    if not items and run.status_message:
        raise EmptyRun(f"{actor_id} run {run.id}: {run.status_message}")
    return items


def scrape_account(api_token: str, profile_url: str, max_posts: int = 50) -> list[dict]:
    """Run the Apify LinkedIn post scraper for a single profile or company URL."""
    client = ApifyClient(api_token)

    run_input = {
        "targetUrls": [profile_url],
        "maxPosts": max_posts,
    }

    return _run_actor(client, ACTOR_ID, run_input)


def scrape_people(
    api_token: str,
    company_url: str,
    job_titles: list[str] | None = None,
    max_items: int = 50,
    full_mode: bool = False,
) -> list[dict]:
    """
    Scrape company employees from LinkedIn via Apify.

    Returns name, headline, location, current company and profile URL ($1.50/1k).
    full_mode ($2.50/1k) also opens each profile for about, education and job
    history, but LinkedIn shows those only on fully public profiles — most come
    back with search details only. scrape_person_profile enriches one person fully.

    Pass job_titles (e.g. ["CEO", "Founder", "CTO"]) to keep only people whose
    headline shows one of them — otherwise returns all visible employees up to max_items.
    """
    client = ApifyClient(api_token)
    run_input: dict = {
        "companies": [company_url],
        "maxEmployeesPerCompany": max_items,
        "fullProfiles": full_mode,
    }
    if job_titles:
        run_input["jobTitles"] = job_titles

    items = _run_actor(client, PEOPLE_ACTOR_ID, run_input)
    # Person.from_apify_result reads the employer from harvestapi's currentPosition
    # list; automly has a flat currentCompany, and the title only in the headline.
    for item in items:
        if item.get("currentCompany") and not item.get("currentPosition"):
            item["currentPosition"] = [{"companyName": item["currentCompany"]}]
    return items


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
    items = _run_actor(client, PROFILE_ACTOR_ID, run_input)
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
    return _run_actor(client, POST_COMMENTS_ACTOR_ID, run_input)


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
