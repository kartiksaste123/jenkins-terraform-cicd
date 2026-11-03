import pytest

from app.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Student Task Tracker" in r.data


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_info(client):
    data = client.get("/api/info").get_json()
    assert data["app"] == "student-task-tracker"
    assert data["author"] == "Kartik Saste"


def test_list_tasks(client):
    data = client.get("/api/tasks").get_json()
    assert data["count"] == len(data["tasks"]) >= 3


def test_get_task_found_and_missing(client):
    assert client.get("/api/tasks/1").status_code == 200
    assert client.get("/api/tasks/9999").status_code == 404


def test_create_task(client):
    r = client.post("/api/tasks", json={"title": "Record the demo"})
    assert r.status_code == 201
    assert r.get_json()["title"] == "Record the demo"


def test_create_task_requires_title(client):
    r = client.post("/api/tasks", json={})
    assert r.status_code == 400


def test_complete_task(client):
    r = client.put("/api/tasks/3/done")
    assert r.status_code == 200
    assert r.get_json()["done"] is True
    assert client.put("/api/tasks/9999/done").status_code == 404
