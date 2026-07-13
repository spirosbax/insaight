import json

import anthropic

CATEGORIES = [
    "Thought Leadership",
    "Industry News",
    "Product/Company Update",
    "Career Advice",
    "Hiring/Recruiting",
    "Personal Story",
    "How-To/Tutorial",
    "Event/Conference",
    "Case Study/Success Story",
    "Opinion/Commentary",
    "Promotion/Marketing",
    "Networking/Engagement Bait",
    "Other",
]

SYSTEM_PROMPT = f"""You are a LinkedIn post categorizer. Given a LinkedIn post, classify it into exactly one semantic category from the list below. Also provide a one-sentence reasoning.

Categories: {', '.join(CATEGORIES)}

Respond with valid JSON only: {{"category": "...", "reasoning": "..."}}"""


def categorize_post(api_key: str, content: str) -> tuple[str, str]:
    """Categorize a single post using Claude. Returns (category, reasoning)."""
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content[:2000]}],
    )
    text = message.content[0].text.strip()
    parsed = json.loads(text)
    return parsed["category"], parsed["reasoning"]


def categorize_posts_batch(api_key: str, posts: list[tuple[str, str]], verbose: bool = False) -> list[tuple[str, str, str]]:
    """Categorize multiple posts. Input: [(post_urn, content)]. Returns [(post_urn, category, reasoning)]."""
    results = []
    for post_urn, content in posts:
        if not content or not content.strip():
            continue
        try:
            category, reasoning = categorize_post(api_key, content)
            results.append((post_urn, category, reasoning))
            if verbose:
                print(f"  [{category}] {content[:60]}...")
        except Exception as e:
            if verbose:
                print(f"  ERROR categorizing {post_urn}: {e}")
            results.append((post_urn, "Other", f"Categorization failed: {e}"))
    return results
