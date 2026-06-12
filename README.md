# Bridge to Success — No-Login Extractor (API + Telegram Bot)

This project exposes the original CLI extractor
(`bridgetosuccess_nologin_extractor.py`) two ways, sharing the exact
same extraction logic via `extractor.py`:

1. **Flask HTTP API** (`main.py`) — JSON/text endpoints
2. **Telegram bot** (`bot.py`) — slash commands

`app.py` runs both together in one process, which is what you deploy
to Koyeb as a single Web Service.

## Files

- `extractor.py` — all original extraction functions (unchanged logic)
- `main.py` — Flask API
- `bot.py` — Telegram bot commands
- `app.py` — combined entrypoint (Flask in background thread + bot polling)
- `requirements.txt`
- `Dockerfile`
- `Procfile`

## 1. Create your Telegram bot

1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, follow the prompts, pick a name and username.
3. BotFather gives you a token like `123456789:ABCdefGhIJKlmNoPQRstuVWxyz`.
4. Keep this token secret.

## 2. Run locally

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRstuVWxyz"
python app.py
```

This starts:
- Flask API on `http://localhost:8000`
- The Telegram bot (polling) — message your bot on Telegram to test it.

## 3. Deploy on Koyeb

1. Push this folder to a GitHub repository.
2. In the Koyeb dashboard: **Create Service → GitHub → select repo**.
3. Koyeb detects the `Dockerfile` automatically.
4. Add an environment variable:
   - `TELEGRAM_BOT_TOKEN` = your bot token from BotFather
5. Leave `PORT` alone — Koyeb sets it automatically and `app.py` reads it.
6. Deploy. The Flask health endpoint (`/health`) keeps Koyeb happy,
   while the bot runs polling in the same container.

## Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` or `/help` | Welcome message + command list |
| `/courses` | List all available courses with their IDs |
| `/free` | Free videos & PDFs (no login required) |
| `/info <course_id>` | Course info (description, faculty, etc.) |
| `/subjects <course_id>` | Subjects/categories inside a course |
| `/report <course_id>` | Full extraction report for one course (.txt file) |
| `/courselist` | Info-only listing of all courses (.txt file) |
| `/reportall` | Full extraction report for ALL courses (.txt file) — **slow!** |

Get course IDs from `/courses` first, then use them with `/info`,
`/subjects`, and `/report`.

## Flask API Endpoints

| Method & Path | Description |
|---|---|
| `GET /` | API index / list of endpoints |
| `GET /health` | Health check |
| `GET /api/courses` | All courses (allCourses + topCourses, merged & deduped) |
| `GET /api/courses/all` | Raw `allCourses` |
| `GET /api/courses/top` | Raw `topCourses` |
| `GET /api/course/<course_id>/info` | Course info |
| `GET /api/course/<course_id>/subjects` | Subjects/categories for a course |
| `GET /api/free-content` | Free videos & PDFs |
| `GET /api/configuration` | App configuration |
| `GET /api/banners` | Home banners |
| `GET /api/course/<course_id>/report` | Full text report for one course. `?download=1` for `.txt` |
| `GET /api/report/all` | Full text report for ALL courses. `?download=1` for `.txt` (slow) |
| `GET /api/report/list` | Info-only listing of all courses. `?download=1` for `.txt` |

## Notes

- `/reportall` and `/api/report/all` walk every course and subject —
  this can take several minutes for large catalogs. The bot will
  reply once the file is ready; be patient with `/reportall`.
- All headers/constants (`ktx`, `ktxx`, API base URLs, etc.) are
  unchanged from the original script.
- If `/courses` or other commands return empty results, the upstream
  API may be blocking your hosting provider's IP or the endpoint
  may have changed — check the logs (`GET /health` confirms the
  service itself is up).
