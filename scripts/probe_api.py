import argparse
import json
import logging
import os
import sys
import time
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

LEARN_API_BASE = "https://learn-api.kodekloud.com"

def redact_string(s: str, max_len: int = 80) -> str:
    """Redact tokens from signed URLs or truncate long strings."""
    if s.startswith("http"):
        try:
            parsed = urlparse(s)
            query = parse_qsl(parsed.query)
            redacted_query = []
            for k, v in query:
                if k.lower() in ("token", "signature", "sig", "expires"):
                    redacted_query.append((k, "***"))
                else:
                    redacted_query.append((k, v))
            parsed = parsed._replace(query=urlencode(redacted_query))
            s = urlunparse(parsed)
        except Exception:
            pass
    
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

def skeletonize(obj):
    """Recursively build a skeleton of the JSON object, summarizing types and values."""
    if isinstance(obj, dict):
        return {k: skeletonize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        if not obj:
            return []
        # Return skeleton of the first element to show shape, indicate length
        return [f"<List of {len(obj)} items. First item shape:>", skeletonize(obj[0])]
    elif isinstance(obj, str):
        return f"<str: {redact_string(obj)}>"
    elif isinstance(obj, int):
        return f"<int: {obj}>"
    elif isinstance(obj, float):
        return f"<float: {obj}>"
    elif isinstance(obj, bool):
        return f"<bool: {obj}>"
    elif obj is None:
        return "<None>"
    else:
        return f"<{type(obj).__name__}>"

def probe_endpoint(session: requests.Session, name: str, url: str):
    logger.info(f"\n--- Probing: {name} ---")
    logger.info(f"GET {url}")
    try:
        resp = session.get(url, timeout=10)
        logger.info(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                skel = skeletonize(data)
                logger.info("Response Skeleton:")
                logger.info(json.dumps(skel, indent=2))
                return data
            except ValueError:
                logger.info(f"Response is not JSON. Text snippet: {resp.text[:100]}...")
        else:
            logger.info(f"Failed. Text snippet: {resp.text[:100]}...")
    except Exception as e:
        logger.error(f"Error: {e}")
    time.sleep(0.5)
    return None

def main():
    parser = argparse.ArgumentParser(description="Probe KodeKloud API for a course slug.")
    parser.add_argument("slug", help="Course slug (e.g., docker-for-the-absolute-beginner-hands-on)")
    args = parser.parse_args()

    token = os.environ.get("KODEKLOUD_TOKEN", "").strip()
    if not token:
        logger.error("KODEKLOUD_TOKEN environment variable is required.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    # Test 1: Course Detail
    detail_data = probe_endpoint(session, "Course Detail (Old style)", f"{LEARN_API_BASE}/api/courses/{args.slug}")
    
    # Check if we can find modules or lessons inside detail_data
    has_embedded_modules = False
    if detail_data and isinstance(detail_data, dict):
        if "modules" in detail_data:
            has_embedded_modules = True
            logger.info("=> Course detail has 'modules' embedded.")
            modules = detail_data["modules"]
            if modules and isinstance(modules, list):
                lessons = modules[0].get("lessons", [])
                if lessons and isinstance(lessons, list):
                    first_lesson = lessons[0]
                    lesson_id = first_lesson.get("id")
                    lesson_type = first_lesson.get("type")
                    logger.info(f"=> Found a lesson: id={lesson_id}, type={lesson_type}")
                    if lesson_id:
                        probe_endpoint(
                            session, 
                            "Lesson Info (using course_id param)", 
                            f"{LEARN_API_BASE}/api/lessons/{lesson_id}?course_id={detail_data.get('id', '')}"
                        )
                        probe_endpoint(
                            session, 
                            "Lesson Info (without course_id param)", 
                            f"{LEARN_API_BASE}/api/lessons/{lesson_id}"
                        )
                        probe_endpoint(
                            session, 
                            "Lesson Info (using course slug param)", 
                            f"{LEARN_API_BASE}/api/lessons/{lesson_id}?course={args.slug}"
                        )

    # Test 2: If modules were not embedded, try to find a curriculum endpoint
    if not has_embedded_modules:
        probe_endpoint(session, "Course Curriculum", f"{LEARN_API_BASE}/api/courses/{args.slug}/curriculum")
        probe_endpoint(session, "Course Modules", f"{LEARN_API_BASE}/api/courses/{args.slug}/modules")
        
        # If we can get course ID, try with ID as well
        course_id = detail_data.get("id") if (detail_data and isinstance(detail_data, dict)) else None
        if course_id:
             probe_endpoint(session, "Course Curriculum (by ID)", f"{LEARN_API_BASE}/api/courses/{course_id}/curriculum")
             probe_endpoint(session, "Course Modules (by ID)", f"{LEARN_API_BASE}/api/courses/{course_id}/modules")

    logger.info("\nProbe finished.")

if __name__ == "__main__":
    main()
