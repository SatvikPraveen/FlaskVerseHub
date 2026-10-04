from typing import Any

import pytest
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    ApiKey,
    Bookmark,
    Category,
    Comment,
    ItemStatus,
    KnowledgeItem,
    Notification,
    Role,
    Setting,
    Tag,
    User,
)
from app.utils.time import from_now
from tests.conftest import make_item, make_user

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("db")]


class TestUser:
    def test_password_hashing(self, user: User) -> None:
        assert user.password_hash != "Password123!"
        assert user.check_password("Password123!")
        assert not user.check_password("wrong")

    def test_full_name_falls_back_to_username(self, db: Any) -> None:
        bare = make_user(db, "bare")
        assert bare.full_name == "bare"
        named = make_user(db, "named", first_name="Ada", last_name="Lovelace")
        assert named.full_name == "Ada Lovelace"

    def test_unique_constraints(self, db: Any, user: User) -> None:
        duplicate = User(username=user.username, email="other@example.com")
        duplicate.set_password("x")
        db.session.add(duplicate)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    @freeze_time("2026-03-01 10:00:00")
    def test_lockout_after_repeated_failures(self, db: Any, user: User) -> None:
        for _ in range(User.MAX_FAILED_LOGINS):
            user.register_failed_login()
        db.session.commit()
        assert user.is_locked
        assert user.locked_until is not None
        assert user.locked_until.tzinfo is not None
        user.register_successful_login()
        db.session.commit()
        assert not user.is_locked
        assert user.login_count == 1
        assert user.failed_login_attempts == 0

    def test_roles_and_permissions(self, db: Any, user: User, admin: User) -> None:
        editor = Role(name="editor", permissions=["items:edit_any"])
        user.roles.append(editor)
        db.session.commit()
        assert user.has_role("editor")
        assert not user.has_role("admin")
        assert user.has_permission("items:edit_any")
        assert not user.has_permission("users:delete")
        assert admin.has_role("anything")
        assert admin.has_permission("anything")
        assert "admin" in admin.role_names

    def test_default_role_assigned_on_create(self, db: Any, member_role: Role) -> None:
        newcomer = make_user(db, "newbie")
        assert [r.name for r in newcomer.roles] == [member_role.name]

    def test_to_dict_hides_email_by_default(self, user: User) -> None:
        assert "email" not in user.to_dict()
        assert user.to_dict(include_email=True)["email"] == user.email

    def test_deleting_user_cascades_to_items(
        self, db: Any, user: User, public_item: KnowledgeItem
    ) -> None:
        item_id = public_item.id
        db.session.delete(user)
        db.session.commit()
        assert db.session.get(KnowledgeItem, item_id) is None


class TestKnowledgeItem:
    def test_slug_is_generated_and_unique(self, db: Any, user: User) -> None:
        first = make_item(db, user, "Same Title")
        second = make_item(db, user, "Same  Title")
        assert first.slug == "same-title"
        assert second.slug == "same-title-2"
        assert second.title == "Same Title"  # whitespace normalised

    def test_empty_title_rejected(self, user: User) -> None:
        with pytest.raises(ValueError, match="title"):
            KnowledgeItem(title="   ", content="x", author=user)

    def test_published_at_set_for_published_only(self, db: Any, user: User) -> None:
        published = make_item(db, user, "Published")
        draft = make_item(db, user, "Draft", status=ItemStatus.DRAFT)
        assert published.published_at is not None
        assert draft.published_at is None
        draft.publish()
        db.session.commit()
        assert draft.published_at is not None

    def test_content_statistics(self, user: User) -> None:
        item = KnowledgeItem(title="t", content="<p>" + "word " * 400 + "</p>", author=user)
        assert item.word_count == 400
        assert item.reading_time == 2

    def test_tags_are_normalised_and_shared(self, db: Any, user: User) -> None:
        first = make_item(db, user, "A", tags="Flask, PYTHON, flask")
        second = make_item(db, user, "B", tags=["python"])
        assert first.tag_names == ["flask", "python"]
        python = db.session.scalar(select(Tag).where(Tag.name == "python"))
        assert python is not None
        assert python.usage_count == 2
        second.set_tags("")
        db.session.commit()
        assert second.tag_names == []

    def test_revision_history(
        self, db: Any, user: User, other_user: User, public_item: KnowledgeItem
    ) -> None:
        original_title = public_item.title
        public_item.bump_version(other_user, note="typo fix")
        public_item.title = "Edited title"
        db.session.commit()
        revisions = public_item.revisions.all()
        assert public_item.version == 2
        assert len(revisions) == 1
        assert revisions[0].title == original_title
        assert revisions[0].editor == other_user
        assert public_item.updated_by == other_user

    def test_visibility_policy(self, db: Any, user: User, other_user: User, admin: User) -> None:
        public = make_item(db, user, "Public")
        private = make_item(db, user, "Private", is_public=False)
        draft = make_item(db, user, "Draft", status=ItemStatus.DRAFT)

        def visible(viewer: User | None) -> set[int]:
            return {i.id for i in db.session.scalars(KnowledgeItem.visible_to(viewer)).all()}

        assert visible(None) == {public.id}
        assert visible(other_user) == {public.id}
        assert visible(user) == {public.id, private.id, draft.id}
        assert visible(admin) == {public.id, private.id, draft.id}
        assert private.is_visible_to(user) and not private.is_visible_to(other_user)
        assert draft.is_visible_to(admin) and not draft.is_visible_to(None)

    def test_to_dict_shape(self, public_item: KnowledgeItem) -> None:
        data = public_item.to_dict(include_content=False)
        assert "content" not in data
        assert data["tags"] == ["architecture", "flask"] or data["tags"] == [
            "flask",
            "architecture",
        ]
        assert data["category"]["name"] == "Fundamentals"
        assert data["author"]["username"] == "alice"
        assert data["status"] == "published"

    def test_cascade_deletes_children(
        self, db: Any, user: User, public_item: KnowledgeItem
    ) -> None:
        comment = Comment(body="Nice", item=public_item, author=user)
        bookmark = Bookmark(user=user, item=public_item)
        db.session.add_all([comment, bookmark])
        db.session.commit()
        db.session.delete(public_item)
        db.session.commit()
        assert db.session.scalar(select(Comment)) is None
        assert db.session.scalar(select(Bookmark)) is None


class TestCategoryAndMisc:
    def test_category_slug_and_count(
        self, db: Any, category: Category, public_item: KnowledgeItem
    ) -> None:
        assert category.slug == "fundamentals"
        assert category.item_count == 1
        child = Category(name="Blueprints", parent=category)
        db.session.add(child)
        db.session.commit()
        assert child in category.children

    def test_bookmark_uniqueness(self, db: Any, user: User, public_item: KnowledgeItem) -> None:
        db.session.add(Bookmark(user=user, item=public_item))
        db.session.commit()
        db.session.add(Bookmark(user=user, item=public_item))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_api_key_lifecycle(self, db: Any, user: User) -> None:
        record, raw = ApiKey.issue(user, "ci", scopes=["read", "write"])
        db.session.commit()
        assert raw.startswith("fvh_") and record.prefix == raw[:12]
        assert ApiKey.lookup(raw) is record
        assert ApiKey.lookup("fvh_nope") is None
        record.expires_at = from_now(days=-1)
        db.session.commit()
        assert record.is_expired
        assert ApiKey.lookup(raw) is None

    def test_notification_mark_read(self, db: Any, user: User) -> None:
        note = Notification(title="Hi", user=user)
        db.session.add(note)
        db.session.commit()
        assert not note.is_read
        note.mark_read()
        assert note.is_read and note.read_at is not None
        assert note.to_dict()["kind"] == "info"

    def test_setting_round_trip(self, db: Any) -> None:
        setting = Setting(key="items_per_page")
        setting.set_value(25)
        db.session.add(setting)
        flag = Setting(key="maintenance")
        flag.set_value(True)
        db.session.add(flag)
        db.session.commit()
        assert Setting.get("items_per_page") == 25
        assert Setting.get("maintenance") is True
        assert Setting.get("missing", "default") == "default"
