"""
Integration tests for the NeoTask API.

Uses an in-memory SQLite database so tests are fully isolated and fast.
Run with: python -m pytest backend/tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

# ── Test Database Setup ───────────────────────────────────────────

SQLALCHEMY_TEST_URL = "sqlite:///file::memory:?cache=shared&uri=true"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Disable rate limiting during tests to avoid false failures
app.state.limiter.enabled = False


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app, raise_server_exceptions=False)


# ── Health Check ──────────────────────────────────────────────────


class TestHealthCheck:
    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ── Security Headers ─────────────────────────────────────────────


class TestSecurityHeaders:
    def test_x_content_type_options(self):
        response = client.get("/api/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self):
        response = client.get("/api/health")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self):
        response = client.get("/api/health")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        response = client.get("/api/health")
        assert (
            response.headers["Permissions-Policy"]
            == "camera=(), microphone=(), geolocation=()"
        )

    def test_server_header_overridden(self):
        response = client.get("/api/health")
        assert response.headers["Server"] == "NeoTask"

    def test_x_xss_protection(self):
        response = client.get("/api/health")
        assert response.headers["X-XSS-Protection"] == "1; mode=block"


# ── List CRUD ─────────────────────────────────────────────────────


class TestLists:
    def test_create_list(self):
        response = client.post("/api/lists", json={"name": "Work"})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Work"
        assert "id" in data

    def test_create_duplicate_list_fails(self):
        client.post("/api/lists", json={"name": "Work"})
        response = client.post("/api/lists", json={"name": "Work"})
        assert response.status_code == 409

    def test_create_duplicate_list_case_insensitive(self):
        """B4: 'Work' and 'work' should be treated as duplicates."""
        client.post("/api/lists", json={"name": "Work"})
        response = client.post("/api/lists", json={"name": "work"})
        assert response.status_code == 409

    def test_create_duplicate_list_mixed_case(self):
        """B4: 'INBOX' collides with 'Inbox'."""
        client.post("/api/lists", json={"name": "Inbox"})
        response = client.post("/api/lists", json={"name": "INBOX"})
        assert response.status_code == 409

    def test_read_lists(self):
        client.post("/api/lists", json={"name": "Inbox"})
        client.post("/api/lists", json={"name": "Personal"})
        response = client.get("/api/lists")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_rename_list(self):
        create_resp = client.post("/api/lists", json={"name": "Old Name"})
        list_id = create_resp.json()["id"]
        response = client.put(f"/api/lists/{list_id}", json={"name": "New Name"})
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_rename_to_existing_name_fails(self):
        client.post("/api/lists", json={"name": "Alpha"})
        resp_b = client.post("/api/lists", json={"name": "Beta"})
        list_b_id = resp_b.json()["id"]
        response = client.put(f"/api/lists/{list_b_id}", json={"name": "Alpha"})
        assert response.status_code == 409

    def test_rename_case_insensitive_collision(self):
        """B4: Renaming Beta to 'alpha' should collide with 'Alpha'."""
        client.post("/api/lists", json={"name": "Alpha"})
        resp_b = client.post("/api/lists", json={"name": "Beta"})
        list_b_id = resp_b.json()["id"]
        response = client.put(f"/api/lists/{list_b_id}", json={"name": "alpha"})
        assert response.status_code == 409

    def test_delete_list(self):
        create_resp = client.post("/api/lists", json={"name": "ToDelete"})
        list_id = create_resp.json()["id"]
        response = client.delete(f"/api/lists/{list_id}")
        assert response.status_code == 200
        # Verify it's gone
        lists = client.get("/api/lists").json()
        assert not any(lst["id"] == list_id for lst in lists)

    def test_delete_nonexistent_list(self):
        response = client.delete("/api/lists/9999")
        assert response.status_code == 404

    def test_create_list_empty_name_fails(self):
        response = client.post("/api/lists", json={"name": ""})
        assert response.status_code == 422

    def test_create_list_whitespace_only_name_fails(self):
        """
        Whitespace-only names should fail validation with a 422 Unprocessable Entity.
        """
        response = client.post("/api/lists", json={"name": "   "})
        assert response.status_code == 422

    def test_create_list_over_max_length_fails(self):
        """Names over 50 characters should be rejected."""
        long_name = "A" * 51
        response = client.post("/api/lists", json={"name": long_name})
        assert response.status_code == 422

    def test_read_lists_pagination(self):
        """Pagination with skip and limit should work."""
        for i in range(5):
            client.post("/api/lists", json={"name": f"Space {i}"})
        response = client.get("/api/lists?skip=2&limit=2")
        data = response.json()
        assert len(data) == 2

    def test_negative_list_id_rejected(self):
        """B5: Negative path IDs should be rejected."""
        response = client.delete("/api/lists/-1")
        assert response.status_code == 422

    def test_zero_list_id_rejected(self):
        """B5: Zero path ID should be rejected."""
        response = client.put("/api/lists/0", json={"name": "Test"})
        assert response.status_code == 422


# ── Task CRUD ─────────────────────────────────────────────────────


class TestTasks:
    def _create_list(self, name="Test List"):
        resp = client.post("/api/lists", json={"name": name})
        return resp.json()["id"]

    def test_create_task(self):
        list_id = self._create_list()
        response = client.post(
            "/api/tasks", json={"title": "Buy groceries", "list_id": list_id}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Buy groceries"
        assert data["is_completed"] is False

    def test_create_task_with_due_date(self):
        list_id = self._create_list()
        response = client.post(
            "/api/tasks",
            json={
                "title": "Meeting",
                "list_id": list_id,
                "due_date": "2026-12-25T10:00:00",
            },
        )
        assert response.status_code == 201
        assert response.json()["due_date"] is not None

    def test_create_task_invalid_list_fails(self):
        response = client.post(
            "/api/tasks", json={"title": "Orphan task", "list_id": 9999}
        )
        assert response.status_code == 404

    def test_create_task_empty_title_fails(self):
        list_id = self._create_list()
        response = client.post("/api/tasks", json={"title": "", "list_id": list_id})
        assert response.status_code == 422

    def test_create_task_over_max_title_fails(self):
        """Titles over 500 characters should be rejected."""
        list_id = self._create_list()
        response = client.post(
            "/api/tasks", json={"title": "X" * 501, "list_id": list_id}
        )
        assert response.status_code == 422

    def test_read_tasks_filtered_by_list(self):
        list_a = self._create_list("List A")
        list_b = self._create_list("List B")
        client.post("/api/tasks", json={"title": "Task A", "list_id": list_a})
        client.post("/api/tasks", json={"title": "Task B", "list_id": list_b})

        response = client.get(f"/api/tasks?list_id={list_a}")
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Task A"

    def test_read_tasks_filter_completed(self):
        """Filter by is_completed should work."""
        list_id = self._create_list()
        resp = client.post("/api/tasks", json={"title": "Done", "list_id": list_id})
        task_id = resp.json()["id"]
        client.put(f"/api/tasks/{task_id}", json={"is_completed": True})

        client.post("/api/tasks", json={"title": "Not done", "list_id": list_id})

        completed = client.get(f"/api/tasks?list_id={list_id}&is_completed=true").json()
        assert len(completed) == 1
        assert completed[0]["title"] == "Done"

        active = client.get(f"/api/tasks?list_id={list_id}&is_completed=false").json()
        assert len(active) == 1
        assert active[0]["title"] == "Not done"

    def test_toggle_task_complete(self):
        list_id = self._create_list()
        create_resp = client.post(
            "/api/tasks", json={"title": "Do laundry", "list_id": list_id}
        )
        task_id = create_resp.json()["id"]

        # Mark complete
        response = client.put(f"/api/tasks/{task_id}", json={"is_completed": True})
        assert response.status_code == 200
        assert response.json()["is_completed"] is True

        # Mark active again
        response = client.put(f"/api/tasks/{task_id}", json={"is_completed": False})
        assert response.json()["is_completed"] is False

    def test_update_task_details(self):
        list_id = self._create_list()
        create_resp = client.post(
            "/api/tasks", json={"title": "Original title", "list_id": list_id}
        )
        task_id = create_resp.json()["id"]

        response = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Updated title", "due_date": "2026-06-15T09:00:00"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"

    def test_move_task_to_another_list(self):
        list_a = self._create_list("Source")
        list_b = self._create_list("Destination")
        create_resp = client.post(
            "/api/tasks", json={"title": "Movable", "list_id": list_a}
        )
        task_id = create_resp.json()["id"]

        response = client.put(f"/api/tasks/{task_id}", json={"list_id": list_b})
        assert response.status_code == 200
        assert response.json()["list_id"] == list_b

    def test_move_task_to_invalid_list_fails(self):
        """Moving a task to a non-existent list should fail."""
        list_id = self._create_list()
        create_resp = client.post(
            "/api/tasks", json={"title": "Stuck", "list_id": list_id}
        )
        task_id = create_resp.json()["id"]
        response = client.put(f"/api/tasks/{task_id}", json={"list_id": 9999})
        assert response.status_code == 404

    def test_delete_task(self):
        list_id = self._create_list()
        create_resp = client.post(
            "/api/tasks", json={"title": "Ephemeral", "list_id": list_id}
        )
        task_id = create_resp.json()["id"]

        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200

    def test_delete_nonexistent_task(self):
        response = client.delete("/api/tasks/9999")
        assert response.status_code == 404

    def test_delete_list_cascades_tasks(self):
        list_id = self._create_list("Cascade Test")
        client.post("/api/tasks", json={"title": "Task 1", "list_id": list_id})
        client.post("/api/tasks", json={"title": "Task 2", "list_id": list_id})

        client.delete(f"/api/lists/{list_id}")

        # Tasks should be gone
        response = client.get(f"/api/tasks?list_id={list_id}")
        assert response.json() == []

    def test_negative_task_id_rejected(self):
        """B5: Negative path IDs should be rejected."""
        response = client.delete("/api/tasks/-1")
        assert response.status_code == 422

    def test_zero_task_id_rejected(self):
        """B5: Zero path ID should be rejected."""
        response = client.put("/api/tasks/0", json={"title": "nope"})
        assert response.status_code == 422

    def test_update_nonexistent_task(self):
        response = client.put("/api/tasks/9999", json={"title": "ghost"})
        assert response.status_code == 404

    def test_read_tasks_pagination(self):
        """Pagination with skip and limit should work."""
        list_id = self._create_list()
        for i in range(5):
            client.post("/api/tasks", json={"title": f"Task {i}", "list_id": list_id})
        response = client.get(f"/api/tasks?list_id={list_id}&skip=2&limit=2")
        data = response.json()
        assert len(data) == 2
