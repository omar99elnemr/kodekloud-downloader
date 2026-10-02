import logging
import os
from pathlib import Path
from typing import Optional, Union

import click
import validators

from kodekloud_downloader.api_client import ApiClient, TokenExpiredError
from kodekloud_downloader.enums import Quality
from kodekloud_downloader.helpers import select_courses
from kodekloud_downloader.main import (
    download_course,
    download_quiz,
    parse_course_from_url,
)
from kodekloud_downloader.models.helper import fetch_enrolled_courses


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase log level verbosity")
def kodekloud(verbose):
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    if verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)


@kodekloud.command()
@click.argument("course_url", required=False)
@click.option(
    "--quality",
    "-q",
    default="1080p",
    type=click.Choice([quality.value for quality in Quality]),
    help="Quality of the video to be downloaded.",
)
@click.option(
    "--output-dir",
    "-o",
    default=Path.home() / "Downloads",
    help="Output directory where downloaded files will be stored.",
)
@click.option(
    "--token",
    "-t",
    default=None,
    envvar="KODEKLOUD_TOKEN",
    help=(
        "Firebase ID token (JWT) for API authentication. "
        "Can also be set via the KODEKLOUD_TOKEN environment variable. "
        "Tokens expire after ~1 hour — copy a fresh one from "
        "DevTools > Network > any learn-api request > Request Headers > authorization."
    ),
    show_envvar=True,
)
@click.option(
    "--cookie",
    "-c",
    default=None,
    help="(Legacy) Cookie file exported from browser. Prefer --token.",
)
@click.option(
    "--browser",
    is_flag=True,
    default=False,
    help="Automatically extract Bearer token from running Chrome (requires playwright).",
)
@click.option(
    "--max-duplicate-count",
    "-mdc",
    default=3,
    type=int,
    help="If the same video is downloaded this many times, stop (guards against expired tokens).",
)
def dl(
    course_url: Optional[str],
    quality: str,
    output_dir: Union[Path, str],
    token: Optional[str],
    cookie: Optional[str],
    browser: bool,
    max_duplicate_count: int,
) -> None:
    """Download a KodeKloud course.

    Provide a COURSE_URL (e.g. https://learn.kodekloud.com/learn/courses/<slug>)
    or omit it to choose interactively from your enrolled courses.
    """
    # ------------------------------------------------------------------
    # 1. Resolve the token — Bearer first, then legacy fallbacks.
    # ------------------------------------------------------------------
    # KODEKLOUD_TOKEN env var is already merged by Click via envvar=.
    # We also check os.environ directly so the env var takes precedence
    # over an explicit --token flag (consistent with the spec).
    env_token = os.environ.get("KODEKLOUD_TOKEN", "").strip() or None
    resolved_token: Optional[str] = env_token or token

    if resolved_token:
        api_client = ApiClient(resolved_token)
        logging.info("Using Bearer token auth (KODEKLOUD_TOKEN / --token)")
    elif browser:
        from kodekloud_downloader.browser import get_session_token_from_browser

        raw = get_session_token_from_browser(auto_launch=True)
        if not raw:
            logging.error(
                "Could not obtain bearer token from browser. "
                "Make sure Chrome is running with --remote-debugging-port=9222 "
                "and you are signed in to https://learn.kodekloud.com. "
                "Alternatively, set KODEKLOUD_TOKEN or use --token."
            )
            raise SystemExit(1)

        def refresher() -> Optional[str]:
            return get_session_token_from_browser(auto_launch=True, is_refresh=True)

        api_client = ApiClient(raw, token_refresher=refresher)
        logging.info("Bearer token extracted from browser successfully")
    elif cookie:
        from kodekloud_downloader.helpers import parse_token

        raw = parse_token(cookie)
        if not raw:
            logging.error(
                "No session token found in cookie file. "
                "Prefer KODEKLOUD_TOKEN=<token> or --token. "
                "See README for instructions."
            )
            raise SystemExit(1)
        api_client = ApiClient(raw)
    else:
        logging.error(
            "No authentication provided. "
            "Set KODEKLOUD_TOKEN=<token> or use --token, --browser, or --cookie. "
            "See README for instructions on obtaining a token."
        )
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # 2. Select course(s) and download.
    # ------------------------------------------------------------------
    from typing import List

    from kodekloud_downloader.main import CourseProgress
    results: List[CourseProgress] = []

    def print_summary():
        if not results:
            return
        print("\n" + "=" * 60)
        print(" DOWNLOAD SUMMARY ".center(60, "="))
        print("=" * 60)
        for r in results:
            status = "COMPLETE" if r.percentage >= 100.0 else "INCOMPLETE"
            downloadable = r.total_lessons - r.skipped
            print(f"• {r.title}")
            print(f"  Status:  {status} ({r.completed}/{downloadable} downloadable lessons)")
            if r.failed > 0:
                print(f"  Failed:  {r.failed}")
            if r.skipped > 0:
                print(f"  Skipped: {r.skipped} (Labs/Undownloadable)")
            print("-" * 60)

    try:
        if course_url is None:
            courses = fetch_enrolled_courses(api_client)
            selected_courses = select_courses(courses)
            for selected_course in selected_courses:
                progress = download_course(
                    course=selected_course,
                    quality=quality,
                    output_dir=output_dir,
                    max_duplicate_count=max_duplicate_count,
                    api_client=api_client,
                )
                results.append(progress)
        elif validators.url(course_url):
            course_detail = parse_course_from_url(course_url, api_client)
            progress = download_course(
                course=course_detail,
                quality=quality,
                output_dir=output_dir,
                max_duplicate_count=max_duplicate_count,
                api_client=api_client,
            )
            results.append(progress)
        else:
            logging.error("Please enter a valid URL")
            raise SystemExit(1)
    except KeyboardInterrupt:
        print("\n\n[!] Download interrupted by user.")
    except TokenExpiredError as exc:
        logging.error(str(exc))
    finally:
        print_summary()


@kodekloud.command()
@click.option(
    "--output-dir",
    "-o",
    default=Path.home() / "Downloads",
    help="Output directory where quiz markdown file will be saved.",
)
@click.option(
    "--sep",
    is_flag=True,
    show_default=True,
    default=False,
    help="Write in seperate markdown files.",
)
def dl_quiz(output_dir: Union[Path, str], sep: bool):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    download_quiz(output_dir, sep)


if __name__ == "__main__":
    kodekloud()
