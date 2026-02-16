from communication.linking import TelegramLinkCodec, build_telegram_deep_link, consume_link_update, parse_link_start_update


def test_codec_roundtrip():
    codec = TelegramLinkCodec("secret-123")
    token, issued = codec.issue_token(tenant_id="t1", user_id="42", phone="+91 99999 12345", ttl_seconds=600)
    claims = codec.decode_token(token)
    assert claims.user_id == "42"
    assert claims.tenant_id == "t1"
    assert claims.phone == "919999912345"
    assert claims.jti == issued.jti


def test_parse_start_update():
    update = {
        "message": {
            "text": "/start link_abc.def",
            "chat": {"id": 123456},
        }
    }
    parsed = parse_link_start_update(update)
    assert parsed == ("abc.def", "123456")


def test_consume_link_update_not_link_command():
    payload = consume_link_update({"message": {"text": "/help", "chat": {"id": 12}}})
    assert payload["matched"] is False
    assert payload["reason"] == "not_link_start"


def test_deep_link():
    link = build_telegram_deep_link("@mybot", "token-1")
    assert link == "https://t.me/mybot?start=link_token-1"
