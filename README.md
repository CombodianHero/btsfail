# Bridge to Success — No-Login Extractor (Web Service)

A Flask wrapper around the original CLI extractor
(`bridgetosuccess_nologin_extractor.py`). All original extraction
logic (course list, subjects, free videos/PDFs, full report builder)
is preserved — it's just exposed over HTTP instead of an interactive
terminal menu, so it can run as a long-lived web service on Koyeb.

## Files

- `main.py` — Flask app + all extraction functions
- `requirements.txt` — Python dependencies
- `Dockerfile` — container build (recommended for Koyeb)
- `Procfile` — fallback for buildpack-based deploys

## Run locally

```bash
pip install -r requirements.txt
python main.py
# -> http://localhost:8000
```

Or with Docker:

```bash
docker build -t bts-extractor .
docker run -p 8000:8000 bts-extractor
```

## Deploy on Koyeb

1. Push this folder to a GitHub repository.
2. In the Koyeb dashboard: **Create Service → GitHub → select repo**.
3. Koyeb detects the `Dockerfile` automatically and builds it.
   (If you'd rather use the Python buildpack, delete the Dockerfile —
   Koyeb will then use the `Procfile`.)
4. Leave the port blank / default — Koyeb sets the `PORT` env var and
   the app reads it automatically (`os.environ.get("PORT", 8000)`,
   and `gunicorn -b 0.0.0.0:${PORT}` in the Dockerfile/Procfile).
5. Deploy. Koyeb will give you a public URL like
   `https://your-app.koyeb.app`.

## Endpoints

| Method & Path | Description |
|---|---|
| `GET /` | API index / list of endpoints |
| `GET /health` | Health check |
| `GET /api/courses` | All courses (allCourses + topCourses, merged & deduped) |
| `GET /api/courses/all` | Raw `allCourses` |
| `GET /api/courses/top` | Raw `topCourses` |
| `GET /api/course/<course_id>/info` | Course info (description, faculty, etc.) |
| `GET /api/course/<course_id>/subjects` | Subjects/categories for a course |
| `GET /api/free-content` | Free videos & PDFs (no login) |
| `GET /api/configuration` | App configuration |
| `GET /api/banners` | Home banners |
| `GET /api/course/<course_id>/report` | Full text report for one course. Add `?download=1` for a `.txt` file |
| `GET /api/report/all` | Full text report for **all** courses. Add `?download=1` for a `.txt` file (slow — many requests) |
| `GET /api/report/list` | Info-only listing of all courses. Add `?download=1` for a `.txt` file |

## Notes

- `/api/report/all` walks every course/subject and can take a while
  (it sleeps briefly between requests to be polite to the upstream
  API). Gunicorn's timeout is set to 120s in the Dockerfile — increase
  it (and Koyeb's request timeout) if you have many courses, or call
  it asynchronously from your client.
- All headers/constants (`ktx`, `ktxx`, API base URLs, etc.) are
  unchanged from the original script.
