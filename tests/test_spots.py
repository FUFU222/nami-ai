from nami_ai.config.spots import get_spot, resolve_spot


def test_resolves_japanese_spot_name_from_query() -> None:
    spot = resolve_spot("明日の辻堂どう？")

    assert spot.key == "tsujido"
    assert spot.name == "辻堂"
    assert spot.lat == 35.32
    assert spot.lon == 139.45
    assert spot.offshore_dir == 22.5


def test_get_spot_accepts_aliases() -> None:
    assert get_spot("鵠沼").key == "kugenuma"
    assert get_spot("kugenuma").name == "鵠沼"
