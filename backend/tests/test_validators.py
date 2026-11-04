from app.core.validators import format_abn, is_valid_abn, is_valid_acn


def test_abn_checksum() -> None:
    assert is_valid_abn("51 824 753 556")  # ATO example
    assert is_valid_abn("53004085616")
    assert not is_valid_abn("51 824 753 557")
    assert not is_valid_abn("1234")
    assert not is_valid_abn("")
    assert format_abn("51824753556") == "51 824 753 556"


def test_acn_check_digit() -> None:
    assert is_valid_acn("004 085 616")
    assert not is_valid_acn("004 085 617")


def test_breach_check_matches_the_hash_suffix(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import hashlib

    import httpx

    from app.auth import security
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "password_breach_check", True)
    suffix = hashlib.sha1(b"Correct-Horse-Battery-9", usedforsecurity=False).hexdigest().upper()[5:]

    class R:
        text = f"0000000000000000000000000000000000A:0\n{suffix}:42\n"

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    assert security.is_breached_password("Correct-Horse-Battery-9")
    assert security.password_policy_errors("Correct-Horse-Battery-9")

    def down(*a, **k):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", down)
    assert not security.is_breached_password("Correct-Horse-Battery-9")  # fails open


def test_terminology_is_replaced_in_one_pass() -> None:
    from app.domains import swap_words

    pairs = [("Contacts", "Contact People"), ("Accounts", "Clients"), ("Contact", "Contact Person")]
    assert swap_words("Contacts", pairs) == "Contact People"
    assert swap_words("My contacts and Contact roles", pairs) == "My contact People and Contact Person roles"
    assert swap_words("Accounts by Contact", pairs) == "Clients by Contact Person"
