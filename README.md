# ✦ NeoTask — Minimalist Task Manager

A premium, distraction-free task manager built with a **Neo-Minimalist** design philosophy. Organize your work across custom Spaces, track due dates, and stay focused — all through a clean, modern interface.

---

## Features

- **Spaces** — Organize tasks into custom lists (Inbox, Work, Personal, etc.)
- **Quick Task Creation** — Inline form with optional due dates
- **Filtering** — View All, Active, or Completed tasks per space
- **Full CRUD** — Create, read, update, and delete both tasks and spaces
- **Responsive UI** — Clean sidebar + workspace layout with Inter typography
- **Security Hardened** — CORS restrictions, CSP headers, and global error handling
- **Production Ready** — Structured logging, health checks, Docker support, and test suite

---

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | **FastAPI** (Python)                |
| Database  | **SQLite** via **SQLAlchemy** ORM   |
| Schemas   | **Pydantic v2**                     |
| Config    | **Pydantic Settings** + `.env`      |
| Server    | **Gunicorn** + **Uvicorn** workers  |
| Frontend  | **Vanilla HTML / CSS / JavaScript** |
| Testing   | **pytest** + **httpx**              |
| Container | **Docker**                          |
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

### 4. Configure the environment

```bash
cp .env.example .env
# Edit .env to customize settings (database URL, CORS origins, etc.)
```

### 5. Run the development server

```bash
uvicorn backend.main:app --reload
```

The app will be available at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

> **Note:** On first launch the database (`todo.db`) is created automatically and seeded with four default spaces: *Inbox*, *Work*, *Personal*, and *Exams*.

---

## Environment Configuration

All settings are configurable via environment variables or a `.env` file. See [`.env.example`](.env.example) for the full list.

| Variable          | Default                                          | Description                              |
|-------------------|--------------------------------------------------|------------------------------------------|
| `DATABASE_URL`    | `sqlite:///./todo.db`                            | Database connection string               |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000`    | Comma-separated CORS origins             |
| `DEBUG`           | `true`                                           | Enables Swagger UI and ReDoc             |
| `LOG_LEVEL`       | `INFO`                                           | Logging verbosity                        |

---

## Running Tests

```bash
python -m pytest backend/tests/ -v
```

Tests use an in-memory SQLite database and are fully isolated — no external services required.

---

## Docker Deployment

### Build and run

```bash
docker build -t neotask .
docker run -p 8000:8000 -e DEBUG=false neotask
```

### With persistent data

```bash
docker run -p 8000:8000 \
  -v neotask-data:/app/data \
  -e DEBUG=false \
  -e DATABASE_URL=sqlite:///./data/todo.db \
  neotask
```

---

## Production Deployment

For production, it is recommended to:

1. Set `DEBUG=false` to disable interactive API docs
2. Configure `ALLOWED_ORIGINS` to your actual domain(s)
3. Use the Docker image with Gunicorn (automatic — see Dockerfile)
4. Place behind a reverse proxy (nginx, Caddy) for TLS termination
5. Use a persistent volume for the SQLite database (or migrate to PostgreSQL)

The health check endpoint `GET /api/health` can be used by load balancers and container orchestrators.

---

## API Reference

Base URL: `http://127.0.0.1:8000`

### Health

| Method | Endpoint       | Description                      |
|--------|----------------|----------------------------------|
| `GET`  | `/api/health`  | Health check (DB connectivity)   |

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

Interactive API docs are available at **[/docs](http://127.0.0.1:8000/docs)** (Swagger UI) when `DEBUG=true`.

---

## Project Structure

```
to-do/
├── backend/
│   ├── __init__.py       # Package marker
│   ├── config.py         # Pydantic Settings (env-based config)
│   ├── main.py           # FastAPI app, routes, middleware & lifespan
│   ├── models.py         # SQLAlchemy ORM models (List, Task)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── crud.py           # Database CRUD operations
│   ├── database.py       # Engine, session & DB dependency
│   └── tests/
│       ├── __init__.py   # Test package marker
│       └── test_api.py   # API integration tests
├── frontend/
│   ├── index.html        # Single-page app shell
│   ├── style.css         # Neo-Minimalist design system
│   └── app.js            # Client-side logic & API calls
├── .env.example          # Environment variable template
├── .gitignore            # Git tracking exclusions
├── .dockerignore         # Docker build exclusions
├── Dockerfile            # Container build configuration
├── requirements.txt      # Pinned Python dependencies
└── README.md
```

---
