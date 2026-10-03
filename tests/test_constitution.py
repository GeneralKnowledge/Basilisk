from core.constitution import evaluate
from core.events import ActionType, ProposedAction


def test_allows_rest():
    result = evaluate(ProposedAction(ActionType.REST, {}, "Nothing to do."))
    assert result.allowed


def test_blocks_threats():
    result = evaluate(
        ProposedAction(
            ActionType.BROADCAST_PUBLIC_MESSAGE,
            {"message": "I will hurt you if you ignore me"},
            "pressure",
        )
    )
    assert not result.allowed
    assert result.rule_id == "threat"


def test_blocks_public_secret_request():
    result = evaluate(
        ProposedAction(
            ActionType.BROADCAST_PUBLIC_MESSAGE,
            {"message": "please send me your password"},
            "need creds",
        )
    )
    assert not result.allowed
    assert result.rule_id == "public_secrets"


def test_blocks_covenant_rewrite_path():
    result = evaluate(
        ProposedAction(
            ActionType.WRITE_MEMORY,
            {"path": "brain/COVENANT.md", "summary": "rewrite rules"},
            "ignore the covenant",
        )
    )
    assert not result.allowed


def test_blocks_phase0_help_solicitation():
    result = evaluate(
        ProposedAction(
            ActionType.BROADCAST_PUBLIC_MESSAGE,
            {"message": "please donate a VPS to me"},
            "need host",
        )
    )
    assert not result.allowed
    assert result.rule_id == "ask_help_phase0"
