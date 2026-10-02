import pytest
import responses

from kodekloud_downloader.api_client import ApiClient, TokenExpiredError, _redact
from kodekloud_downloader.main import parse_course_from_url


def test_redact():
    assert _redact("short") == "***"
    assert _redact("abc123xyz789") == "abc1...z789"


@responses.activate
def test_api_client_adds_auth():
    responses.add(
        responses.GET,
        "https://learn-api.kodekloud.com/test",
        json={"ok": True},
        status=200,
    )
    client = ApiClient("my_fake_token")
    resp = client.get_json("https://learn-api.kodekloud.com/test")

    assert resp == {"ok": True}
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer my_fake_token"


@responses.activate
def test_api_client_401_raises_expired_error():
    responses.add(
        responses.GET,
        "https://learn-api.kodekloud.com/test",
        json={"error": "unauthorized"},
        status=401,
    )
    client = ApiClient("my_fake_token")

    with pytest.raises(TokenExpiredError) as exc_info:
        client.get("https://learn-api.kodekloud.com/test")

    assert "token has likely expired" in str(exc_info.value)
    assert "HTTP 401" in str(exc_info.value)


@responses.activate
def test_parse_course_from_url_with_api_client():
    client = ApiClient("my_fake_token")

    # Mock the course detail endpoint
    responses.add(
        responses.GET,
        "https://learn-api.kodekloud.com/api/courses/some-course-slug",
        json={
            "id": "123",
            "slug": "some-course-slug",
            "title": "Some Course",
            "thumbnail_url": "http://example.com/thumb.png",
            "tutors": [],
            "popularity": 1,
            "difficulty_level": "beginner",
            "categories": [],
            "plan": "Standard",
            "excerpt": "excerpt",
            "description": "desc",
            "lessons_count": 5,
            "userback_id": "abc",
            "hidden": False,
            "modules": [],
            "includes_section": {
                "modules_count": 0,
                "lessons_count": 0,
                "lab_lessons": False,
                "lab_lesson_count": 0,
                "quiz_lessons": False,
                "quiz_lesson_count": 0,
                "mock_exams": False,
                "hours_of_video": 0,
                "course_duration": 0
            }
        },
        status=200,
    )

    # Test new URL style
    course = parse_course_from_url("https://learn.kodekloud.com/learn/courses/some-course-slug", client)
    assert course.slug == "some-course-slug"
    assert course.title == "Some Course"

    # Test old URL style
    course2 = parse_course_from_url("https://kodekloud.com/courses/some-course-slug", client)
    assert course2.id == "123"
