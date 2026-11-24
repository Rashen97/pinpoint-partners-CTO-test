"""Discover and sample a public firm directory, producing a JSON draft."""

import argparse
import json
import os
import re
from pathlib import Path
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS
from pipeline.onboarding_model import propose_settings


DIRECTORY_LABELS = ("our team", "people", "lawyers", "attorneys", "professionals")
FILTER_LABELS = {
    "Partner": "position[]",
    "Corporate": "practice[]",
    "Mergers and Acquisitions": "practice[]",
}
STAFF_ENDPOINT = re.compile(r"""["']([^"'\s]*/wp-json/[^"'\s]*/staff-listing)["']""")
REQUEST_INTERVAL = 5


def fetch(session, url, host, **params):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password:
        raise ValueError("Discovery requires HTTPS URLs on the supplied homepage host.")
    if parsed.port not in (None, 443):
        raise ValueError("Discovery requires the standard HTTPS port.")
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS, allow_redirects=False)
    if response.is_redirect:
        raise ValueError("Use the firm's canonical HTTPS homepage URL. Redirects are not followed.")
    response.raise_for_status()
    return response


def directory_signals(page, directory):
    """Collect a bounded set of public markup hints for source review."""
    facets = []
    for facet in page.select("[data-grid][data-facet]", limit=20):
        controls = []
        for control in facet.select("input[name], select[name]", limit=5):
            controls.append(control["name"])
        facets.append({
            "grid": facet["data-grid"],
            "facet": facet["data-facet"],
            "label": facet.get_text(" ", strip=True)[:120],
            "control_names": list(dict.fromkeys(controls)),
        })
    scripts = []
    for script in page.select("script[src]"):
        source = urljoin(directory, script["src"])
        if urlsplit(source).hostname == urlsplit(directory).hostname:
            scripts.append(source)
    return {"facets": facets, "script_urls": list(dict.fromkeys(scripts))[:20]}


def inspect_draft(session, firm, homepage):
    hostname = urlsplit(homepage).hostname
    draft = {"name": firm, "refresh_enabled": False}
    report = {
        "status": "needs_review",
        "homepage": homepage,
        "draft_config": draft,
        "evidence": [],
        "unverified": ["Full pagination, unique partner count, and biography selectors"],
    }
    try:
        home = BeautifulSoup(fetch(session, homepage, hostname).content, "html.parser")
        directory = next(
            (
                urljoin(homepage, link["href"])
                for link in home.select("a[href]")
                if link.get_text(" ", strip=True).casefold() in DIRECTORY_LABELS
                and urlsplit(urljoin(homepage, link["href"])).hostname == hostname
            ),
            None,
        )
        if directory is None:
            raise ValueError("Could not identify a directory link on the homepage.")
        draft["directory_url"] = directory
        report["evidence"].append({"url": homepage, "finding": "Navigation links to the directory."})
        if directory != homepage:
            sleep(REQUEST_INTERVAL)
        page = BeautifulSoup(fetch(session, directory, hostname).content, "html.parser")
        filters = {}
        for label in page.find_all("label"):
            name = label.get_text(" ", strip=True).replace(" & ", " and ")
            if name not in FILTER_LABELS:
                continue
            control = label.find("input")
            if control is None and label.get("for"):
                control = page.find("input", id=label["for"])
            if control and control.get("name") == FILTER_LABELS[name] and control.get("value"):
                filters[name] = control["value"]
        report["evidence"].append({"url": directory, "discovered_filters": filters})
        missing = FILTER_LABELS.keys() - filters.keys()
        if missing:
            report["unverified"].append(f"Filter identifiers for {', '.join(sorted(missing))}")

        scripts = "\n".join(tag.string or "" for tag in page.find_all("script"))
        endpoint = STAFF_ENDPOINT.search(scripts.replace(r"\/", "/"))
        if endpoint is None:
            report["evidence"].append({"url": directory, **directory_signals(page, directory)})
            report["unverified"].append("Listing request method, endpoint, and pagination require review.")
            return report
        results_url = urljoin(directory, endpoint.group(1))
        draft.update(results_url=results_url, request_interval_seconds=REQUEST_INTERVAL)
        report["evidence"].append({"url": directory, "staff_listing_endpoint": results_url})
        if "Partner" not in filters:
            return report
        draft["partner_position_id"] = filters["Partner"]
        practices = [
            {"label": label, "id": filters[label]}
            for label in FILTER_LABELS
            if label != "Partner" and label in filters
        ]
        draft["practice_page_filters"] = practices
        for practice in practices:
            sample = []
            for page_number in (1, 2):
                sleep(REQUEST_INTERVAL)
                response = fetch(
                    session, results_url, hostname,
                    position=filters["Partner"], practice=practice["id"], paged=page_number,
                )
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("html"), str):
                    raise ValueError("The staff-listing response did not contain HTML cards.")
                counts = {
                    key: payload.get(key)
                    for key in ("total_posts", "current_posts", "start_post", "end_post")
                }
                if any(type(value) is not int for value in counts.values()):
                    raise ValueError("The staff-listing response did not expose integer pagination counts.")
                report["evidence"].append({"url": response.url, "practice": practice["label"], **counts})
                sample.append(counts)
                if page_number == 1 and counts["total_posts"] <= counts["current_posts"]:
                    break
            total = sample[0]["total_posts"]
            size = sample[0]["current_posts"]
            for index, counts in enumerate(sample):
                end = min((index + 1) * size, total)
                if (
                    size < 1 or counts["total_posts"] != total or counts["start_post"] != index * size + 1
                    or counts["end_post"] != end or counts["current_posts"] != end - index * size
                ):
                    raise ValueError(f"Inconsistent page counts for {practice['label']}.")
        if practices:
            draft.update(method="GET", type="json", page_parameter="paged")
    except (requests.RequestException, ValueError) as exc:
        report["unverified"].append(str(exc))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firm", help="Firm name")
    parser.add_argument("homepage", help="Official canonical HTTPS homepage")
    parser.add_argument("--capture", type=Path, help="Sanitised UTF-8 request and response summary to send to OpenAI")
    parser.add_argument("--model", help="OpenAI model for the optional proposal")
    args = parser.parse_args()
    if args.model and not args.capture:
        parser.error("--model requires --capture")
    if args.capture:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            parser.error("Set OPENAI_API_KEY to use --capture")
        try:
            with args.capture.open(encoding="utf-8-sig") as source:
                capture = source.read(12001)
        except (OSError, UnicodeError):
            parser.error("--capture must point to a readable UTF-8 file")
        if not capture.strip() or len(capture) > 12000:
            parser.error("--capture must contain 1 to 12000 characters")
        capture = capture.strip()
    with requests.Session() as session:
        report = inspect_draft(session, args.firm, args.homepage)
    if args.capture:
        model = args.model or "gpt-6.2-astra"
        try:
            proposal = propose_settings(api_key, model, args.firm, args.homepage, report["evidence"], capture)
        except (requests.RequestException, ValueError) as exc:
            report["model_proposal_error"] = str(exc) if type(exc) is ValueError else "Could not obtain a valid proposal from OpenAI."
            print(json.dumps(report, indent=2))
            return 1
        report["model_proposal"] = {"model": model, "status": "needs_review", "findings": proposal}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
