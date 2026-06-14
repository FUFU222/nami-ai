from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfSpot:
    key: str
    name: str
    lat: float
    lon: float
    offshore_dir: float
    swell_window: tuple[float, float]
    aliases: tuple[str, ...] = ()


SPOTS: dict[str, SurfSpot] = {
    "kugenuma": SurfSpot(
        key="kugenuma",
        name="鵠沼",
        lat=35.31,
        lon=139.47,
        offshore_dir=22.5,
        swell_window=(140.0, 220.0),
        aliases=("鵠沼", "くげぬま", "kugenuma"),
    ),
    "tsujido": SurfSpot(
        key="tsujido",
        name="辻堂",
        lat=35.32,
        lon=139.45,
        offshore_dir=22.5,
        swell_window=(140.0, 220.0),
        aliases=("辻堂", "つじどう", "tsujido"),
    ),
    "chigasaki": SurfSpot(
        key="chigasaki",
        name="茅ヶ崎",
        lat=35.32,
        lon=139.40,
        offshore_dir=0.0,
        swell_window=(150.0, 230.0),
        aliases=("茅ヶ崎", "茅ケ崎", "ちがさき", "chigasaki"),
    ),
    "shichirigahama": SurfSpot(
        key="shichirigahama",
        name="七里ガ浜",
        lat=35.30,
        lon=139.51,
        offshore_dir=22.5,
        swell_window=(130.0, 210.0),
        aliases=("七里ガ浜", "七里ヶ浜", "七里", "しちりがはま", "shichirigahama"),
    ),
    "yuigahama": SurfSpot(
        key="yuigahama",
        name="由比ガ浜",
        lat=35.31,
        lon=139.54,
        offshore_dir=22.5,
        swell_window=(130.0, 210.0),
        aliases=("由比ガ浜", "由比ヶ浜", "由比", "ゆいがはま", "yuigahama"),
    ),
}


def _normalize(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("　", "")


def get_spot(name: str) -> SurfSpot:
    normalized = _normalize(name)
    if normalized in SPOTS:
        return SPOTS[normalized]

    for spot in SPOTS.values():
        if any(_normalize(alias) == normalized for alias in spot.aliases):
            return spot

    available = ", ".join(spot.name for spot in SPOTS.values())
    raise ValueError(f"Unknown surf spot: {name}. Available spots: {available}")


def resolve_spot(text: str) -> SurfSpot:
    normalized_text = _normalize(text)
    for spot in SPOTS.values():
        if any(_normalize(alias) in normalized_text for alias in spot.aliases):
            return spot

    raise ValueError("ポイント名を解釈できませんでした。鵠沼、辻堂、茅ヶ崎、七里ガ浜、由比ガ浜のいずれかを含めてください。")
