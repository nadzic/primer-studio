import pytest

from app.main import _allowed_origins


@pytest.mark.unit
def test_allowed_origins_splits_and_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://a.example.com, http://localhost:3000,   ,https://b.example.com ",
    )

    assert _allowed_origins() == [
        "https://a.example.com",
        "http://localhost:3000",
        "https://b.example.com",
    ]
