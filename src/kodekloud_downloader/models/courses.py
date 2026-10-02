from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class Category(BaseModel):
    id: str
    name: str


class Tutor(BaseModel):
    id: str
    name: str
    bio: str
    description: str
    avatar_url: HttpUrl


class Course(BaseModel):
    id: str
    slug: str
    title: str
    thumbnail_url: Optional[HttpUrl] = None
    tutors: List[Tutor] = []
    popularity: Optional[int] = None
    difficulty_level: Optional[str] = None
    categories: List[Category] = []
    plan: str


class EnrolledCourse(BaseModel):
    """Represents one item from ``GET /api/courses/enrolled``.

    The enrolled endpoint returns a slimmer payload than the public
    listing, so most secondary fields are optional.
    """

    id: str
    slug: str
    title: str
    plan: str
    enrolled: Optional[bool] = None
    progress: Optional[float] = None
    difficulty_level: Optional[str] = None
    tutors: List[Tutor] = []
    categories: List[Category] = []
    thumbnail_url: Optional[HttpUrl] = None
    popularity: Optional[int] = None


class Metadata(BaseModel):
    limit: int
    page: int
    total_count: int
    next_page: Optional[int]


class ApiResponse(BaseModel):
    courses: List[Course]
    metadata: Metadata

