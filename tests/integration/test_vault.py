import json
from typing import Any

import pytest
from flask.testing import FlaskClient

from app.knowledge_vault import service
from app.models import Bookmark, Category, Comment, ItemStatus, KnowledgeItem, Notification, User
from tests.conftest import make_item

pytestmark = pytest.mark.integration


def _form(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "title": "Testing Flask applications",
        "summary": "A short summary.",
        "content": "<p>Use <b>pytest</b> fixtures.</p><script>alert(1)</script>",
        "category_id": 0,
        "tags": "pytest, Flask",
        "difficulty": "beginner",
        "status": "published",
        "source_url": "",
        "is_public": "y",
    }
    data.update(overrides)
    return data


class TestListing:
    def test_anonymous_sees_only_public_published(
        self, client: FlaskClient, db: Any, user: User
    ) -> None:
        make_item(db, user, "Public one")
        make_item(db, user, "Hidden one", is_public=False)
        make_item(db, user, "Draft one", status=ItemStatus.DRAFT)
        html = client.get("/knowledge/").get_data(as_text=True)
        assert "Public one" in html
        assert "Hidden one" not in html and "Draft one" not in html

    def test_owner_sees_private_and_mine_filter(
        self, logged_in_client: FlaskClient, db: Any, user: User, other_user: User
    ) -> None:
        make_item(db, user, "Mine private", is_public=False)
        make_item(db, other_user, "Theirs public")
        html = logged_in_client.get("/knowledge/").get_data(as_text=True)
        assert "Mine private" in html and "Theirs public" in html
        mine = logged_in_client.get("/knowledge/?mine=1").get_data(as_text=True)
        assert "Mine private" in mine and "Theirs public" not in mine

    def test_filters(
        self, client: FlaskClient, items: list[KnowledgeItem], db: Any, user: User
    ) -> None:
        other = Category(name="Other")
        db.session.add(other)
        db.session.commit()
        tagged = make_item(
            db, user, "Tagged thing", tags="special", category=other, difficulty="expert"
        )
        html = client.get("/knowledge/?q=BM25").get_data(as_text=True)
        assert "BM25 ranking function" in html and "TF-IDF weighting" not in html
        assert "Tagged thing" in client.get("/knowledge/?tag=special").get_data(as_text=True)
        assert "BM25 ranking function" not in client.get("/knowledge/?tag=special").get_data(
            as_text=True
        )
        assert "Tagged thing" in client.get("/knowledge/?category=other").get_data(as_text=True)
        assert "Tagged thing" in client.get("/knowledge/?difficulty=expert").get_data(as_text=True)
        assert "BM25 ranking function" not in client.get("/knowledge/?difficulty=expert").get_data(
            as_text=True
        )
        assert tagged.title in client.get("/knowledge/?sort=title&featured=0").get_data(
            as_text=True
        )

    def test_pagination(self, client: FlaskClient, db: Any, user: User) -> None:
        for i in range(25):
            make_item(db, user, f"Item {i:02d}")
        first = client.get("/knowledge/?per_page=10&sort=title").get_data(as_text=True)
        assert "Item 00" in first and "Item 10" not in first
        third = client.get("/knowledge/?per_page=10&sort=title&page=3").get_data(as_text=True)
        assert "Item 20" in third and "Showing 21" in third

    def test_categories_page(self, client: FlaskClient, public_item: KnowledgeItem) -> None:
        html = client.get("/knowledge/categories").get_data(as_text=True)
        assert "Fundamentals" in html and "1 item" in html


class TestDetail:
    def test_detail_counts_views_and_shows_metadata(
        self, client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        response = client.get(f"/knowledge/{public_item.slug}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert public_item.title in html and "#flask" in html and "Fundamentals" in html
        assert public_item.view_count == 1

    def test_private_item_hidden_from_others(
        self,
        client: FlaskClient,
        private_item: KnowledgeItem,
        other_user: User,
        login: Any,
        user: User,
    ) -> None:
        assert client.get(f"/knowledge/{private_item.slug}").status_code == 404
        login(other_user)
        assert client.get(f"/knowledge/{private_item.slug}").status_code == 404
        login(user)
        assert client.get(f"/knowledge/{private_item.slug}").status_code == 200

    def test_missing_item(self, client: FlaskClient) -> None:
        assert client.get("/knowledge/nope").status_code == 404

    def test_export_formats(self, client: FlaskClient, public_item: KnowledgeItem) -> None:
        as_json = client.get(f"/knowledge/{public_item.slug}/export.json")
        assert as_json.mimetype == "application/json"
        assert json.loads(as_json.get_data(as_text=True))["slug"] == public_item.slug
        as_md = client.get(f"/knowledge/{public_item.slug}/export.md")
        assert as_md.mimetype == "text/markdown"
        assert as_md.get_data(as_text=True).startswith(f"# {public_item.title}")
        assert client.get(f"/knowledge/{public_item.slug}/export.pdf").status_code == 404


class TestCreateEditDelete:
    def test_create_requires_login(self, client: FlaskClient) -> None:
        assert client.get("/knowledge/new").status_code == 302
        assert client.post("/knowledge/new", data=_form()).status_code == 302

    def test_create_sanitises_and_tags(
        self, logged_in_client: FlaskClient, db: Any, user: User, category: Category
    ) -> None:
        response = logged_in_client.post(
            "/knowledge/new", data=_form(category_id=category.id), follow_redirects=True
        )
        assert response.status_code == 200
        item = db.session.query(KnowledgeItem).filter_by(title="Testing Flask applications").one()
        assert "<script>" not in item.content and "<b>pytest</b>" in item.content
        assert item.tag_names == ["flask", "pytest"] or item.tag_names == ["pytest", "flask"]
        assert item.category == category
        assert item.author == user
        assert "Knowledge item created" in response.get_data(as_text=True)

    def test_create_validation(self, logged_in_client: FlaskClient) -> None:
        html = logged_in_client.post(
            "/knowledge/new", data=_form(title="ab", content="short")
        ).get_data(as_text=True)
        assert "Field must be between 3 and 200" in html
        assert "at least 10 characters" in html

    def test_edit_creates_revision(
        self, logged_in_client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        original = public_item.title
        response = logged_in_client.post(
            f"/knowledge/{public_item.slug}/edit",
            data=_form(title="Renamed item", change_note="rename"),
            follow_redirects=True,
        )
        assert "Changes saved" in response.get_data(as_text=True)
        assert public_item.title == "Renamed item" and public_item.version == 2
        revisions = public_item.revisions.all()
        assert revisions[0].title == original and revisions[0].note == "rename"
        history = logged_in_client.get(f"/knowledge/{public_item.slug}/history").get_data(
            as_text=True
        )
        assert original in history and "v2" in history
        diff = logged_in_client.get(f"/knowledge/{public_item.slug}/history/1").get_data(
            as_text=True
        )
        assert "<ins>" in diff and "<del>" in diff
        assert logged_in_client.get(f"/knowledge/{public_item.slug}/history/9").status_code == 404

    def test_restore_revision(
        self, logged_in_client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        original_content = public_item.content
        logged_in_client.post(
            f"/knowledge/{public_item.slug}/edit",
            data=_form(content="<p>Completely new body text.</p>"),
        )
        assert public_item.content != original_content
        response = logged_in_client.post(
            f"/knowledge/{public_item.slug}/history/1/restore", follow_redirects=True
        )
        assert "Restored version 1" in response.get_data(as_text=True)
        assert public_item.content == original_content and public_item.version == 3

    def test_non_owner_cannot_edit_or_delete(
        self, client: FlaskClient, public_item: KnowledgeItem, other_user: User, login: Any
    ) -> None:
        login(other_user)
        assert client.get(f"/knowledge/{public_item.slug}/edit").status_code == 403
        assert client.post(f"/knowledge/{public_item.slug}/delete").status_code == 403

    def test_admin_and_editor_permission_can_edit(
        self, admin_client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        assert admin_client.get(f"/knowledge/{public_item.slug}/edit").status_code == 200
        response = admin_client.post(
            f"/knowledge/{public_item.slug}/edit",
            data=_form(is_featured="y"),
            follow_redirects=True,
        )
        assert response.status_code == 200 and public_item.is_featured

    def test_only_admin_can_feature(
        self, logged_in_client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        public_item.is_featured = False
        logged_in_client.post(f"/knowledge/{public_item.slug}/edit", data=_form(is_featured="y"))
        assert public_item.is_featured is False

    def test_delete(
        self, logged_in_client: FlaskClient, db: Any, public_item: KnowledgeItem
    ) -> None:
        item_id = public_item.id
        response = logged_in_client.post(
            f"/knowledge/{public_item.slug}/delete", follow_redirects=True
        )
        assert "deleted" in response.get_data(as_text=True)
        assert db.session.get(KnowledgeItem, item_id) is None


class TestSocial:
    def test_bookmark_toggle_and_listing(
        self, logged_in_client: FlaskClient, db: Any, public_item: KnowledgeItem, user: User
    ) -> None:
        response = logged_in_client.post(
            f"/knowledge/{public_item.slug}/bookmark", headers={"Accept": "application/json"}
        )
        assert response.get_json() == {"bookmarked": True, "count": 1}
        assert public_item.title in logged_in_client.get("/knowledge/bookmarks").get_data(
            as_text=True
        )
        response = logged_in_client.post(
            f"/knowledge/{public_item.slug}/bookmark", follow_redirects=True
        )
        assert "Bookmark removed" in response.get_data(as_text=True)
        assert db.session.query(Bookmark).count() == 0

    def test_comments_and_notifications(
        self,
        client: FlaskClient,
        db: Any,
        public_item: KnowledgeItem,
        user: User,
        other_user: User,
        login: Any,
    ) -> None:
        login(other_user)
        response = client.post(
            f"/knowledge/{public_item.slug}/comments",
            data={"body": "Great <b>note</b>"},
            follow_redirects=True,
        )
        assert "Comment posted" in response.get_data(as_text=True)
        comment = db.session.query(Comment).one()
        assert comment.body == "Great &lt;b&gt;note&lt;/b&gt;"
        note = db.session.query(Notification).filter_by(user_id=user.id).one()
        assert "commented" in note.title
        # reply by the author notifies the parent commenter
        login(user)
        client.post(
            f"/knowledge/{public_item.slug}/comments",
            data={"body": "Thanks!", "parent_id": comment.id},
        )
        assert db.session.query(Notification).filter_by(user_id=other_user.id).count() == 1
        html = client.get(f"/knowledge/{public_item.slug}").get_data(as_text=True)
        assert "Thanks!" in html and "Comments (2)" in html
        # empty comment rejected
        bad = client.post(
            f"/knowledge/{public_item.slug}/comments", data={"body": ""}, follow_redirects=True
        )
        assert "cannot be empty" in bad.get_data(as_text=True)

    def test_comment_deletion_rules(
        self,
        client: FlaskClient,
        db: Any,
        public_item: KnowledgeItem,
        user: User,
        other_user: User,
        admin: User,
        login: Any,
    ) -> None:
        comment = service.add_comment(public_item, "hello", author=other_user)
        stranger = User(username="stranger", email="s@example.com")
        stranger.set_password("Password123!")
        db.session.add(stranger)
        db.session.commit()
        login(stranger)
        assert client.post(f"/knowledge/comments/{comment.id}/delete").status_code == 403
        login(user)  # item owner may moderate
        assert client.post(f"/knowledge/comments/{comment.id}/delete").status_code == 302
        assert comment.is_deleted
        assert client.post("/knowledge/comments/999/delete").status_code == 404


class TestBulk:
    def test_bulk_actions_respect_ownership(
        self, client: FlaskClient, db: Any, user: User, other_user: User, login: Any
    ) -> None:
        mine = make_item(db, user, "Mine")
        theirs = make_item(db, other_user, "Theirs")
        login(user)
        response = client.post(
            "/knowledge/bulk",
            data={"action": "make_private", "item_ids": [mine.id, theirs.id]},
            follow_redirects=True,
        )
        assert "to 1 item(s)" in response.get_data(as_text=True)
        assert mine.is_public is False and theirs.is_public is True

    def test_bulk_feature_requires_admin_and_delete(
        self, admin_client: FlaskClient, db: Any, user: User
    ) -> None:
        a = make_item(db, user, "A")
        b = make_item(db, user, "B")
        admin_client.post("/knowledge/bulk", data={"action": "feature", "item_ids": [a.id]})
        assert a.is_featured
        admin_client.post("/knowledge/bulk", data={"action": "archive", "item_ids": [b.id]})
        assert b.status == ItemStatus.ARCHIVED
        admin_client.post("/knowledge/bulk", data={"action": "delete", "item_ids": [a.id, b.id]})
        assert db.session.query(KnowledgeItem).count() == 0

    def test_bulk_requires_selection(self, logged_in_client: FlaskClient) -> None:
        response = logged_in_client.post(
            "/knowledge/bulk", data={"action": "publish"}, follow_redirects=True
        )
        assert "Select at least one item" in response.get_data(as_text=True)


def test_service_rejects_unknown_bulk_action(db: Any, user: User) -> None:
    item = make_item(db, user, "X")
    with pytest.raises(ValueError, match="unknown bulk action"):
        service.bulk_action("explode", [item.id], actor=user)
