"""
Dynamically updates the "Currently Working On" section in README.md
based on the repos with the most commits in the past 7 days.

Runs via GitHub Actions on a schedule.
"""

import os
import re
import requests
from datetime import datetime, timedelta, timezone

# ─── Configuration ───────────────────────────────────────────────
GITHUB_USERNAME = "Pranav-0440"
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
README_PATH = "README.md"
TOP_N = 5  # Number of repos to show
WEEK_DAYS = 7  # Look back 7 days

# ─── GitHub API helpers ──────────────────────────────────────────
HEADERS = {
    "Accept": "application/vnd.github+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

API_BASE = "https://api.github.com"


def get_user_repos():
    """Fetch all public (and private if token has scope) repos for the user."""
    repos = []
    page = 1
    while True:
        url = f"{API_BASE}/users/{GITHUB_USERNAME}/repos"
        params = {
            "per_page": 100,
            "page": page,
            "sort": "pushed",
            "direction": "desc",
            "type": "owner",
        }
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def get_weekly_commits(repo_full_name):
    """
    Get the number of commits in the last WEEK_DAYS days for a repo.
    Uses the commits endpoint with 'since' parameter.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=WEEK_DAYS)).isoformat()
    url = f"{API_BASE}/repos/{repo_full_name}/commits"
    params = {
        "since": since,
        "per_page": 1,  # We only need the count from headers
        "author": GITHUB_USERNAME,
    }

    # First request to check if there are commits and get total
    resp = requests.get(url, headers=HEADERS, params={**params, "per_page": 100})
    if resp.status_code == 409:
        # Empty repository
        return 0
    resp.raise_for_status()
    commits = resp.json()
    return len(commits)


def get_language_color(language):
    """Map languages to badge colors."""
    colors = {
        "Python": "3776AB",
        "Java": "ED8B00",
        "JavaScript": "F7DF1E",
        "TypeScript": "3178C6",
        "C": "00599C",
        "C++": "00599C",
        "HTML": "E34F26",
        "CSS": "1572B6",
        "Jupyter Notebook": "F37626",
        "Shell": "89E051",
        "Rust": "DEA584",
        "Go": "00ADD8",
        "Ruby": "CC342D",
        "Kotlin": "7F52FF",
        "Swift": "F05138",
        "Dart": "0175C2",
        "R": "276DC3",
    }
    return colors.get(language, "6C63FF")


def get_activity_badge(commits):
    """Generate a visual activity level badge based on commit count."""
    if commits >= 15:
        return "🔥_On_Fire-FF4444", "🔥"
    elif commits >= 8:
        return "⚡_Very_Active-FF6B6B", "⚡"
    elif commits >= 4:
        return "✅_Active-4ECDC4", "✅"
    elif commits >= 2:
        return "🔨_Building-FFE66D", "🔨"
    else:
        return "🌱_Growing-95E1D3", "🌱"


def build_table(active_repos):
    """Build the markdown table for the Currently Working On section."""
    if not active_repos:
        return (
            "| 🎯 | 📝 | 🗓️ | 📊 |\n"
            "|:---:|:---|:---:|:---:|\n"
            "| — | _No commit activity this week_ | — | — |\n"
        )

    lines = []
    lines.append(
        "| # | 🎯 Repository | 💻 Language | 🗓️ Commits (7d) | 📊 Activity |"
    )
    lines.append("|:---:|:---|:---:|:---:|:---:|")

    for idx, repo in enumerate(active_repos, 1):
        name = repo["name"]
        full_name = repo["full_name"]
        url = repo["html_url"]
        language = repo.get("language") or "—"
        description = repo.get("description") or ""
        commits = repo["_weekly_commits"]
        stars = repo.get("stargazers_count", 0)

        # Truncate description
        if len(description) > 50:
            description = description[:47] + "..."

        # Language badge
        if language != "—":
            lang_color = get_language_color(language)
            lang_badge = f"![{language}](https://img.shields.io/badge/{language}-{lang_color}?style=flat-square&logo={language.lower()}&logoColor=white)"
        else:
            lang_badge = "—"

        # Activity badge
        activity_label, activity_emoji = get_activity_badge(commits)
        activity_badge = f"![Activity](https://img.shields.io/badge/{activity_label}?style=flat-square)"

        # Commit count badge
        commit_badge = f"![Commits](https://img.shields.io/badge/{commits}_commits-6C63FF?style=flat-square)"

        # Build row
        repo_link = f"[**{name}**]({url})"
        if description:
            repo_cell = f"{repo_link}<br><sub>{description}</sub>"
        else:
            repo_cell = repo_link

        lines.append(
            f"| {idx} | {repo_cell} | {lang_badge} | {commit_badge} | {activity_badge} |"
        )

    return "\n".join(lines)


def update_readme(table_content):
    """Replace content between marker comments in README.md."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Markers in the README
    start_marker = "<!-- WORKING_ON_START -->"
    end_marker = "<!-- WORKING_ON_END -->"

    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )

    # Build the replacement block
    now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    replacement = (
        f"{start_marker}\n\n"
        f"{table_content}\n\n"
        f"<p align=\"right\"><sub>🔄 Auto-updated: {now}</sub></p>\n\n"
        f"{end_marker}"
    )

    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
    else:
        print("⚠️  Markers not found in README.md — skipping update.")
        return

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ README.md updated with {len(table_content.splitlines())} lines.")


def main():
    print(f"📡 Fetching repos for {GITHUB_USERNAME}...")
    repos = get_user_repos()
    print(f"   Found {len(repos)} repos.")

    # Filter out forked repos and the profile repo itself
    repos = [
        r for r in repos
        if not r.get("fork")
        and r["name"] != GITHUB_USERNAME  # skip profile README repo
    ]

    print(f"🔍 Checking weekly commit activity for {len(repos)} repos...")
    for repo in repos:
        commits = get_weekly_commits(repo["full_name"])
        repo["_weekly_commits"] = commits
        if commits > 0:
            print(f"   📦 {repo['name']}: {commits} commits")

    # Sort by weekly commits (descending), then by push date
    active_repos = [r for r in repos if r["_weekly_commits"] > 0]
    active_repos.sort(key=lambda r: r["_weekly_commits"], reverse=True)

    # Take top N
    top_repos = active_repos[:TOP_N]

    print(f"\n🏆 Top {len(top_repos)} active repos this week:")
    for r in top_repos:
        print(f"   {r['name']}: {r['_weekly_commits']} commits")

    # Build table and update README
    table = build_table(top_repos)
    update_readme(table)


if __name__ == "__main__":
    main()
