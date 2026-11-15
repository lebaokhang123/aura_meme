"""Mutation serialization precedes authenticated user and admin role locks."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import permissions, admin_users


@pytest.mark.parametrize("method,expected", [("GET", ["auth"]), ("HEAD", ["auth"]), ("POST", ["gate", "auth"]), ("PATCH", ["gate", "auth"]), ("PUT", ["gate", "auth"]), ("DELETE", ["gate", "auth"])])
def test_account_mutation_gate_precedes_auth(monkeypatch, method, expected):
    calls = []
    db = Mock()
    db.begin.return_value = nullcontext()
    request = SimpleNamespace(method=method, app=SimpleNamespace(state=SimpleNamespace(auth_session_factory=lambda: nullcontext(db))))
    monkeypatch.setattr(permissions, "lock_aura_mutation", lambda db: calls.append("gate"), raising=False)
    monkeypatch.setattr(permissions, "authenticated_account", lambda *args: calls.append("auth") or "account")
    dependency = permissions.require_authenticated_user(request, Mock(), "a" * 43)
    assert next(dependency) == "account"
    dependency.close()
    assert calls == expected


def test_admin_gate_precedes_role_and_auth(monkeypatch):
    calls = []
    db = Mock()
    db.begin.return_value = nullcontext()
    db.scalar.side_effect = lambda query: calls.append("role") or True
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth_session_factory=lambda: nullcontext(db))))
    monkeypatch.setattr(admin_users, "lock_aura_mutation", lambda db: calls.append("gate"), raising=False)
    monkeypatch.setattr(admin_users, "authenticated_account", lambda *args: calls.append("auth") or SimpleNamespace(user=SimpleNamespace(id=None)))
    monkeypatch.setattr(admin_users, "require_account_csrf", lambda *args: "account")
    dependency = admin_users.require_admin_mutation(request, Mock(), "a" * 43)
    assert next(dependency) == "account"
    dependency.close()
    assert calls == ["gate", "role", "auth", "role"]


@pytest.mark.parametrize("existing,expected_awards", [(None, 1), (SimpleNamespace(reaction_type="like"), 0)])
def test_reaction_creation_awards_but_replacement_does_not(monkeypatch, existing, expected_awards):
    import sys
    from app import interactions
    from uuid import uuid4
    awards = Mock()
    monkeypatch.setattr("app.meme_reactions.set_owned_reaction", Mock())
    monkeypatch.setitem(sys.modules, "app.aura_runtime", SimpleNamespace(award_reaction=awards))
    monkeypatch.setattr(interactions, "lock_public_post", Mock())
    account = SimpleNamespace(db=Mock(), user=SimpleNamespace(id=uuid4()))
    account.db.get.return_value = existing
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: None))))
    post_id = uuid4()
    result = interactions.set_reaction(post_id, interactions.ReactionInput(reaction_type="fire"), request, account)
    assert result.post_id == post_id
    assert awards.call_count == expected_awards
    if expected_awards:
        awards.assert_called_once_with(account.db, post_id, account.user.id, None)


def test_reaction_removal_reverses_in_existing_transaction(monkeypatch):
    import sys
    from app import interactions
    from uuid import uuid4
    reverse = Mock()
    monkeypatch.setitem(sys.modules, "app.aura_runtime", SimpleNamespace(reverse_reaction=reverse))
    monkeypatch.setattr(interactions, "lock_public_post", Mock())
    account = SimpleNamespace(db=Mock(), user=SimpleNamespace(id=uuid4()))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: "now"))))
    post_id = uuid4()
    interactions.remove_reaction(post_id, request, account)
    reverse.assert_called_once_with(account.db, post_id, account.user.id, "now")
    account.db.commit.assert_not_called()


@pytest.mark.parametrize("raw",[None,"invalid"])
def test_invalid_session_does_not_acquire_database_mutation_gate(monkeypatch,raw):
    from app.security import AuthError
    factory=Mock(side_effect=AssertionError("Invalid cookie must not open the database"))
    request=SimpleNamespace(method="POST",app=SimpleNamespace(state=SimpleNamespace(auth_session_factory=factory)))
    with pytest.raises(AuthError) as error:
        next(permissions.require_authenticated_user(request,Mock(),raw))
    assert error.value.status==401
    factory.assert_not_called()
