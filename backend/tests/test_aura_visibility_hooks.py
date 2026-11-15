"""Visibility withdrawal reverses source rewards without rewards on restoration."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import blog, admin_posts


@pytest.mark.parametrize("before,patch,expected", [("active", {"status": "hidden"}, 2), ("active", {"name": "Renamed"}, 0), ("hidden", {"status": "active"}, 0)])
def test_category_patch_reverses_only_active_to_hidden(monkeypatch, before, patch, expected):
    reverse = Mock()
    monkeypatch.setitem(sys.modules, "app.aura_runtime", SimpleNamespace(reverse_post=reverse))
    category = SimpleNamespace(id=uuid4(), name="Original", status=before)
    posts = [uuid4(), uuid4()]
    account = SimpleNamespace(db=Mock())
    account.db.scalars.return_value = posts
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: "now"))))
    monkeypatch.setattr(blog, "locked_category", lambda *args: category)
    monkeypatch.setattr(blog, "category_snapshot", lambda item: {"status": item.status})
    monkeypatch.setattr(blog, "audit_category", Mock())
    monkeypatch.setattr(blog, "category_dto", lambda item: item)
    blog.admin_update_category(category.id, blog.CategoryPatch(**patch), request, account)
    assert reverse.call_count == expected
    if expected:
        assert [call.args for call in reverse.call_args_list] == [(account.db, post, "now") for post in posts]


def test_category_delete_reverses_source_rewards(monkeypatch):
    reverse = Mock()
    monkeypatch.setitem(sys.modules, "app.aura_runtime", SimpleNamespace(reverse_post=reverse))
    category = SimpleNamespace(id=uuid4(), status="active")
    post_id = uuid4()
    account = SimpleNamespace(db=Mock())
    account.db.scalars.return_value = [post_id]
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: "now"))))
    monkeypatch.setattr(blog, "locked_category", lambda *args: category)
    monkeypatch.setattr(blog, "category_snapshot", lambda item: {"status": item.status})
    monkeypatch.setattr(blog, "audit_category", Mock())
    blog.admin_delete_category(category.id, request, account)
    reverse.assert_called_once_with(account.db, post_id, "now")


@pytest.mark.parametrize("initial_status,target_status,target_category_status,moved,expected", [("published", "published", "hidden", True, 1), ("published", "published", "active", True, 0), ("published", "draft", "active", False, 1), ("hidden", "published", "active", False, 0), ("published", "published", "active", False, 0)])
def test_admin_post_visibility_withdrawal(monkeypatch, initial_status, target_status, target_category_status, moved, expected):
    reverse = Mock()
    monkeypatch.setitem(sys.modules, "app.aura_runtime", SimpleNamespace(reverse_post=reverse))
    post = SimpleNamespace(id=uuid4(), author_id=uuid4(), category_id=uuid4(), media_id=None, status=initial_status, content="content", title="Title")
    target = SimpleNamespace(id=uuid4() if moved else post.category_id, status=target_category_status)
    monkeypatch.setattr(admin_posts, "locked_post", lambda *args: post)
    monkeypatch.setattr(admin_posts, "validate_post", lambda *args, **kwargs: target)
    monkeypatch.setattr(admin_posts, "audit_post", Mock())
    monkeypatch.setattr(admin_posts, "post_dto", lambda *args: post)
    account = SimpleNamespace(db=Mock())
    account.db.get.return_value = target
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: "now"))))
    payload = admin_posts.AdminPostPatch(status=target_status, category_id=target.id) if moved else admin_posts.AdminPostPatch(status=target_status)
    admin_posts.moderate_post(post.id, payload, request, account)
    assert reverse.call_count == expected
    if expected:
        reverse.assert_called_once_with(account.db, post.id, "now")
