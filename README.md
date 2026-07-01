# ✦ NeoTask — Minimalist Task Manager

A premium, distraction-free task manager built with a **Neo-Minimalist** design philosophy. Organize your work across custom Spaces, track due dates, and stay focused — all through a clean, modern interface.

---

## Features

- **Spaces** — Organize tasks into custom lists (Inbox, Work, Personal, etc.)
- **Quick Task Creation** — Inline form with optional due dates
- **Filtering** — View All, Active, or Completed tasks per space
- **Full CRUD** — Create, read, update, and delete both tasks and spaces
- **Responsive UI** — Clean sidebar + workspace layout with Inter typography
- **Security Hardened** — CORS restrictions, security headers, and global error handling

---

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | **FastAPI** (Python)                |
| Database  | **SQLite** via **SQLAlchemy** ORM   |
| Schemas   | **Pydantic v2**                     |
| Server    | **Uvicorn** (ASGI)                  |
| Frontend  | **Vanilla HTML / CSS / JavaScript** |
| Font      | [Inter](https://fonts.google.com/specimen/Inter) (Google Fonts) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- `pip` (or a virtual-environment manager of your choice)

### 1. Clone the repository

```bash
git clone <repo-url>
cd to-do
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the development server

```bash
uvicorn backend.main:app --reload
```

The app will be available at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

> **Note:** On first launch the database (`todo.db`) is created automatically and seeded with four default spaces: *Inbox*, *Work*, *Personal*, and *Exams*.

---

## API Reference

Base URL: `http://127.0.0.1:8000`

### Lists (Spaces)

| Method   | Endpoint              | Description                 |
|----------|-----------------------|-----------------------------|
| `GET`    | `/api/lists`          | Retrieve all spaces         |
| `POST`   | `/api/lists`          | Create a new space          |
| `PUT`    | `/api/lists/{list_id}`| Rename a space              |
| `DELETE` | `/api/lists/{list_id}`| Delete a space & its tasks  |

### Tasks

| Method   | Endpoint               | Description                          |
|----------|------------------------|--------------------------------------|
| `GET`    | `/api/tasks`           | Retrieve tasks (filterable)          |
| `POST`   | `/api/tasks`           | Create a new task                    |
| `PUT`    | `/api/tasks/{task_id}` | Update a task                        |
| `DELETE` | `/api/tasks/{task_id}` | Delete a task                        |

#### Query Parameters for `GET /api/tasks`

| Parameter      | Type    | Description                              |
|----------------|---------|------------------------------------------|
| `list_id`      | int     | Filter tasks by space                    |
| `is_completed` | bool    | Filter by completion status              |
| `skip`         | int     | Pagination offset (default `0`)          |
| `limit`        | int     | Max results, 1–200 (default `100`)       |

Interactive API docs are available at **[/docs](http://127.0.0.1:8000/docs)** (Swagger UI).

---

## Project Structure

```
to-do/
├── backend/
│   ├── __init__.py       # Package marker
│   ├── main.py           # FastAPI app, routes, middleware & lifespan
│   ├── models.py         # SQLAlchemy ORM models (List, Task)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── crud.py           # Database CRUD operations
│   └── database.py       # Engine, session & DB dependency
├── frontend/
│   ├── index.html        # Single-page app shell
│   ├── style.css         # Neo-Minimalist design system
│   └── app.js            # Client-side logic & API calls
├── requirements.txt      # Python dependencies
├── todo.db               # SQLite database (auto-generated)
└── README.md
```

---


