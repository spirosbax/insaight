import csv
import io
import json
from pathlib import Path

import click
from dotenv import load_dotenv

from . import db, categorizer, models, scraper

load_dotenv()


@click.group()
def cli():
    """insaight — Scrape and categorize LinkedIn posts via Apify."""
    pass


@cli.command()
@click.option("--accounts", default="config/accounts.txt", type=click.Path(exists=True), help="File with LinkedIn profile URLs")
@click.option("--token", envvar="APIFY_API_TOKEN", required=True, help="Apify API token")
@click.option("--anthropic-key", envvar="ANTHROPIC_API_KEY", default=None, help="Anthropic API key for categorization")
@click.option("--max-posts", default=50, help="Max posts per account")
@click.option("--db-path", default=None, help="SQLite DB path")
@click.option("--categorize/--no-categorize", default=True, help="Run LLM categorization")
@click.option("-v", "--verbose", is_flag=True)
def scrape(accounts, token, anthropic_key, max_posts, db_path, categorize, verbose):
    """Scrape LinkedIn posts from accounts and store in SQLite."""
    # Read account URLs
    urls = Path(accounts).read_text().strip().splitlines()
    urls = [u.strip() for u in urls if u.strip() and not u.strip().startswith("#")]

    if not urls:
        click.echo("No account URLs found in " + accounts)
        return

    click.echo(f"Scraping {len(urls)} account(s), max {max_posts} posts each...")

    # Init DB
    conn = db.get_connection(db_path)
    db.init_db(conn)

    # Scrape
    all_results = scraper.scrape_accounts(token, urls, max_posts, verbose)

    total_new = 0
    total_dups = 0

    for account_url, items in all_results.items():
        posts = [models.Post.from_apify_result(item, account_url) for item in items]
        new, dups = db.insert_posts(conn, posts)
        total_new += new
        total_dups += dups
        click.echo(f"  {account_url}: {new} new, {dups} duplicates")

    click.echo(f"\nTotal: {total_new} new posts, {total_dups} duplicates skipped")

    # Categorize with LLM
    if categorize and anthropic_key:
        uncategorized = db.get_uncategorized_posts(conn)
        if uncategorized:
            click.echo(f"\nCategorizing {len(uncategorized)} posts with Claude...")
            post_tuples = [(row["post_urn"], row["content"]) for row in uncategorized]
            results = categorizer.categorize_posts_batch(anthropic_key, post_tuples, verbose)
            for post_urn, category, reasoning in results:
                db.update_category(conn, post_urn, category, reasoning)
            click.echo(f"Categorized {len(results)} posts")
        else:
            click.echo("All posts already categorized.")
    elif categorize and not anthropic_key:
        click.echo("\nSkipping categorization — set ANTHROPIC_API_KEY in .env to enable")

    conn.close()


@cli.command()
@click.option("--db-path", default=None, help="SQLite DB path")
def stats(db_path):
    """Show database statistics."""
    conn = db.get_connection(db_path)
    db.init_db(conn)
    s = db.get_stats(conn)
    conn.close()

    click.echo(f"Total posts:    {s['total_posts']}")
    click.echo(f"Accounts:       {s['accounts']}")
    click.echo(f"Categorized:    {s['categorized']}")
    click.echo(f"Categories:     {s['categories']}")
    click.echo(f"Date range:     {s['earliest'] or 'N/A'} → {s['latest'] or 'N/A'}")


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv")
@click.option("--output", "-o", default=None, help="Output file path")
@click.option("--db-path", default=None, help="SQLite DB path")
def export(fmt, output, db_path):
    """Export posts to CSV or JSON."""
    conn = db.get_connection(db_path)
    db.init_db(conn)
    rows = db.get_all_posts(conn)
    conn.close()

    if not rows:
        click.echo("No posts to export.")
        return

    columns = rows[0].keys()

    if fmt == "json":
        data = [dict(row) for row in rows]
        content = json.dumps(data, indent=2, default=str)
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
        content = buf.getvalue()

    if output:
        Path(output).write_text(content)
        click.echo(f"Exported {len(rows)} posts to {output}")
    else:
        click.echo(content)


if __name__ == "__main__":
    cli()
