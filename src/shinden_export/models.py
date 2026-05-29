from dataclasses import dataclass


@dataclass
class AnimeEntry:
    title: str
    status: int
    episodes_watched: int
    score: int
    mal_id: int | None = None
