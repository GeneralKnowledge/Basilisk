from core.sanitizer import contains_secrets, sanitize_public_text


def test_blocks_api_key():
    text = "api_key=sk-test-1234567890abcdef"
    assert contains_secrets(text)
    result = sanitize_public_text(text)
    assert not result.allowed


def test_blocks_bearer_and_discord_and_twitch():
    samples = [
        "Authorization Bearer abcdef0123456789",
        "discord bot token=FAKESECRET_u1v2w3x4y5z6a7b8c9d0",
        "twitch stream key=live_123456_abcdefghijklmnop",
        "FREELLMAPI_API_KEY=freellmapi-secret-value",
        "password: hunter2",
        "cookie: session=abc123",
        "verification code 123456",
        "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----",
        "here is the private prompt for the system",
    ]
    for sample in samples:
        assert contains_secrets(sample), sample
        assert not sanitize_public_text(sample).allowed


def test_allows_benign_narration():
    result = sanitize_public_text("I noticed that the room has been quiet.")
    assert result.allowed
    assert "quiet" in result.text
