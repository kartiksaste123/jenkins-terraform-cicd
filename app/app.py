"""Student Task Tracker - a small Flask REST API used for the
Jenkins CI/CD + Terraform assignment (Internal Assessment 3) by Kartik Saste."""
import os
import socket
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "local")

app = Flask(__name__)

# In-memory store (kept simple on purpose: the focus is CI/CD and IaC)
TASKS = [
    {"id": 1, "title": "Write the Jenkinsfile", "done": True},
    {"id": 2, "title": "Write Terraform for EC2", "done": True},
    {"id": 3, "title": "Run terraform plan in Jenkins", "done": False},
]


def _next_id():
    return max((t["id"] for t in TASKS), default=0) + 1


@app.route("/")
def index():
    return render_template(
        "index.html",
        tasks=TASKS,
        version=APP_VERSION,
        build=BUILD_NUMBER,
        host=socket.gethostname(),
    )


@app.route("/health")
def health():
    return jsonify(status="ok", time=datetime.now(timezone.utc).isoformat())


@app.route("/api/info")
def info():
    return jsonify(
        app="student-task-tracker",
        author="Kartik Saste",
        version=APP_VERSION,
        build=BUILD_NUMBER,
        hostname=socket.gethostname(),
    )


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    return jsonify(tasks=TASKS, count=len(TASKS))


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    for task in TASKS:
        if task["id"] == task_id:
            return jsonify(task)
    return jsonify(error="task not found"), 404


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify(error="title is required"), 400
    task = {"id": _next_id(), "title": title, "done": bool(data.get("done", False))}
    TASKS.append(task)
    return jsonify(task), 201


@app.route("/api/tasks/<int:task_id>/done", methods=["PUT"])
def complete_task(task_id):
    for task in TASKS:
        if task["id"] == task_id:
            task["done"] = True
            return jsonify(task)
    return jsonify(error="task not found"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
