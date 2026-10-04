from datetime import timedelta
from typing import Any

import pytest
from flask.testing import FlaskClient

from app.dashboard import analytics
from app.extensions import socketio
from app.knowledge_vault import service as vault_service
from app.models import Activity, ItemStatus, KnowledgeItem, Notification, User
from app.services.notifications import notify
from app.utils.time import utcnow
from tests.conftest import make_item

pytestmark = pytest.mark.integration


class TestPages:
    def test_requires_login(self, client: FlaskClient) -> None:
        for path in ("/dashboard/", "/dashboard/notifications", "/dashboard/activity"):
            assert client.get(path).status_code == 302

    def test_user_dashboard(
        self, logged_in_client: FlaskClient, db: Any, user: User, public_item: KnowledgeItem
    ) -> None:
        notify(user, "Hello there", commit=True)
        html = logged_in_client.get("/dashboard/").get_data(as_text=True)
        assert "Welcome back" in html and public_item.title in html and "Hello there" in html
        assert (
            'id="nav-unread"' in html
            and "d-none" not in html.split('id="nav-unread"')[1].split(">")[0]
        )

    def test_analytics_admin_only(self, logged_in_client: FlaskClient) -> None:
        assert logged_in_client.get("/dashboard/analytics").status_code == 403

    def test_analytics_page_and_json(
        self, admin_client: FlaskClient, items: list[KnowledgeItem]
    ) -> None:
        assert admin_client.get("/dashboard/analytics").status_code == 200
        payload = admin_client.get("/dashboard/analytics.json").get_json()
        assert payload["overview"]["items"] == 5
        assert len(payload["items_per_day"]) == 30 and payload["items_per_day"][-1]["count"] == 5
        assert payload["status"]["published"] == 5 and payload["categories"][0]["count"] == 5
        assert payload["reading_time"]["count"] == 5

    def test_notifications_flow(
        self, logged_in_client: FlaskClient, db: Any, user: User, other_user: User
    ) -> None:
        first = notify(user, "First", link="/about", commit=True)
        notify(user, "Second", commit=True)
        foreign = notify(other_user, "Not yours", commit=True)
        html = logged_in_client.get("/dashboard/notifications?unread=1").get_data(as_text=True)
        assert "First" in html and "Second" in html and "Not yours" not in html
        response = logged_in_client.post(f"/dashboard/notifications/{first.id}/read")
        assert response.status_code == 302 and response.headers["Location"].endswith("/about")
        assert first.is_read
        as_json = logged_in_client.post(
            f"/dashboard/notifications/{first.id}/read", headers={"Accept": "application/json"}
        ).get_json()
        assert as_json == {"ok": True, "unread": 1}
        assert (
            logged_in_client.post(f"/dashboard/notifications/{foreign.id}/read").status_code == 404
        )
        logged_in_client.post("/dashboard/notifications/read-all")
        assert db.session.query(Notification).filter_by(user_id=user.id, is_read=False).count() == 0

    def test_activity_scoping(
        self, client: FlaskClient, db: Any, user: User, other_user: User, admin: User, login: Any
    ) -> None:
        db.session.add_all(
            [
                Activity(action="alpha.event", user=user),
                Activity(action="beta.event", user=other_user),
            ]
        )
        db.session.commit()
        login(user)
        html = client.get("/dashboard/activity").get_data(as_text=True)
        assert "alpha.event" in html and "beta.event" not in html
        login(admin)
        html = client.get("/dashboard/activity").get_data(as_text=True)
        assert "alpha.event" in html and "beta.event" in html and "Audit trail" in html


class TestAnalytics:
    def test_distributions_and_rankings(
        self, db: Any, user: User, other_user: User, category: Any
    ) -> None:
        a = make_item(db, user, "A", tags="x, y", category=category, view_count=10)
        make_item(db, user, "B", tags="x", difficulty="expert", view_count=0)
        make_item(db, other_user, "C", status=ItemStatus.DRAFT, is_public=False)
        overview = analytics.overview()
        assert overview["items"] == 3 and overview["public_items"] == 2 and overview["views"] == 10
        assert analytics.status_distribution() == {"draft": 1, "published": 2, "archived": 0}
        assert analytics.difficulty_distribution()["expert"] == 1
        assert analytics.items_by_category()[0] == {
            "name": "Fundamentals",
            "color": "#0d6efd",
            "count": 1,
        }
        assert analytics.top_tags()[0] == {"name": "x", "count": 2}
        assert analytics.top_authors()[0] == {"username": "alice", "items": 2, "views": 10}
        assert [i.id for i in analytics.most_viewed(1)] == [a.id]
        assert analytics.view_concentration() == 0.6667  # (n-1)/n rounded: one item owns every view

    def test_items_per_day_window(self, db: Any, user: User) -> None:
        old = make_item(db, user, "Old")
        old.created_at = utcnow() - timedelta(days=45)
        db.session.commit()
        make_item(db, user, "New")
        series = analytics.items_per_day(7)
        assert len(series) == 7 and sum(row["count"] for row in series) == 1

    def test_reading_time_and_gini_edge_cases(self, db: Any, user: User) -> None:
        assert analytics.reading_time_summary()["count"] == 0
        assert analytics.view_concentration() == 0.0
        make_item(db, user, "Short", content="tiny text here")
        make_item(db, user, "Long", content="word " * 1000)
        summary = analytics.reading_time_summary()
        assert summary["count"] == 2 and summary["max"] == 5.0 and summary["median"] == 3.0
        assert analytics.view_concentration() == 0.0  # no views at all

    def test_activity_breakdown_and_user_summary(
        self, db: Any, user: User, public_item: KnowledgeItem
    ) -> None:
        db.session.add_all(
            [Activity(action="a", user=user), Activity(action="a", user=user), Activity(action="b")]
        )
        db.session.commit()
        assert analytics.activity_breakdown()[0] == {"action": "a", "count": 2}
        summary = analytics.user_summary(user)
        assert (
            summary["items"] == 1
            and summary["public_items"] == 1
            and summary["unread_notifications"] == 0
        )
        assert len(analytics.recent_activity(5, user=user)) == 2


class TestSockets:
    def test_connect_rooms_and_events(
        self, app: Any, client: FlaskClient, db: Any, user: User, login: Any
    ) -> None:
        login(user)
        sio = socketio.test_client(app, flask_test_client=client)
        try:
            assert sio.is_connected()
            received = {event["name"]: event["args"] for event in sio.get_received()}
            assert received["connected"][0]["authenticated"] is True
            assert received["presence"][0]["connected"] >= 1
            sio.emit("subscribe", {"item": "some-slug"})
            sio.emit("ping_server")
            names = [event["name"] for event in sio.get_received()]
            assert names == ["subscribed", "pong_client"]
            # Domain events reach the public room and user room.
            with app.test_request_context():
                item = vault_service.create_item(
                    {"title": "Socket item", "content": "Broadcast me please.", "is_public": True},
                    author=user,
                )
                notify(user, "Socket note", commit=True)
            events = [event["name"] for event in sio.get_received()]
            assert "item:created" in events and "notification" in events
            sio.emit("unsubscribe", {"item": "some-slug"})
            with app.test_request_context():
                vault_service.delete_item(item, actor=user)
            assert any(e["name"] == "item:deleted" for e in sio.get_received())
        finally:
            sio.disconnect()
        assert not sio.is_connected()

    def test_anonymous_connection(self, app: Any, client: FlaskClient) -> None:
        sio = socketio.test_client(app, flask_test_client=client)
        received = {event["name"]: event["args"] for event in sio.get_received()}
        assert received["connected"][0]["authenticated"] is False
        sio.disconnect()
