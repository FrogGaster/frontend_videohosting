from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: int
    telegram_id: int
    created_at: str


@dataclass
class Profile:
    id: int
    user_id: int
    nickname: str
    world_level: int
    main_dps: str
    server: str
    description: Optional[str]
    photo_file_id: Optional[str]


@dataclass
class Interaction:
    id: int
    from_user_id: int
    to_user_id: int
    action: str  # "like" | "dislike"
    created_at: str
