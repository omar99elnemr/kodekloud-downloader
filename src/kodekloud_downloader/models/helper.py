from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import requests

from kodekloud_downloader.models.course import CourseDetail
from kodekloud_downloader.models.courses import ApiResponse, Course, EnrolledCourse

if TYPE_CHECKING:
    from kodekloud_downloader.api_client import ApiClient

from kodekloud_downloader.api_client import LEARN_API_BASE


def fetch_enrolled_courses(api_client: ApiClient) -> List[EnrolledCourse]:
    """Return the list of courses the authenticated user is enrolled in.

    Uses ``GET /api/courses/enrolled`` with Bearer auth.
    """
    url = f"{LEARN_API_BASE}/api/courses/enrolled"
    data = api_client.get_json(url)
    courses = data.get("courses", data) if isinstance(data, dict) else data
    return [EnrolledCourse(**c) for c in courses]


def fetch_courses(page: int, limit: int) -> ApiResponse:
    """Public (unauthenticated) paginated course listing.

    .. deprecated::
        Use :func:`fetch_enrolled_courses` for authenticated access.
    """
    url = f"{LEARN_API_BASE}/api/courses?page={page}&limit={limit}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    return ApiResponse(**data)


def collect_all_courses(
    api_client: Optional[ApiClient] = None,
) -> List[Course]:
    """Collect all courses from the public paginated endpoint.

    .. deprecated::
        Use :func:`fetch_enrolled_courses` instead.
    """
    all_courses: List[Course] = []
    page = 1
    limit = 30
    while True:
        api_response = fetch_courses(page, limit)
        all_courses.extend(api_response.courses)
        if api_response.metadata.next_page is None:
            break
        page = api_response.metadata.next_page
    return all_courses


def fetch_course_detail(
    slug: str, api_client: Optional[ApiClient] = None
) -> CourseDetail:
    """Fetch full course detail (modules + lessons) for *slug*.

    Passes Bearer auth when *api_client* is given, falls back to an
    unauthenticated request otherwise (may fail on private courses).
    """
    url = f"{LEARN_API_BASE}/api/courses/{slug}"
    if api_client is not None:
        data = api_client.get_json(url)
    else:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

    return CourseDetail(**data)


# ---------------------------------------------------------------------------
# Example usage (run this module directly to test)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os

    token = os.environ.get("KODEKLOUD_TOKEN", "")
    if not token:
        print("Set KODEKLOUD_TOKEN before running this directly.")
    else:
        from kodekloud_downloader.api_client import ApiClient

        client = ApiClient(token)
        enrolled = fetch_enrolled_courses(client)
        for course in enrolled[:3]:
            print(course.title, "|", course.plan)
