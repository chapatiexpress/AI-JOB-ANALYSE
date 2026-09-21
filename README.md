# JobMatch AI — Deployable Starter

This package contains separate frontend and backend files.

## What this version does

- Upload a PDF/DOCX resume.
- Extract a lightweight candidate profile.
- Match jobs against the resume.
- Filter by:
  - 30 minutes / 1h / 3h / 6h / 12h / 24h
  - Match percentage
  - C2C / W2 / 1099
  - Visa
  - Remote / Hybrid / Onsite
- Show only non-blocked matching jobs.
- Open the original job link.
- Mark jobs as applied.

## Important LinkedIn note

This starter intentionally does **not** scrape LinkedIn.

LinkedIn does not provide a general public API that lets an ordinary website download every job listing. To make the site live, connect `backend/main.py -> load_jobs()` to an authorized/permitted job source, employer ATS feed, approved partner API, or job-alert ingestion source.

## Run locally

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend:
`http://localhost:8000`

### Frontend

You can serve the frontend with any static server:

```bash
cd frontend
python -m http.server 5500
```

Open:
`http://localhost:5500`

## Deploy

### Frontend
Deploy the `frontend` folder to:
- Netlify
- Vercel static hosting
- Cloudflare Pages
- GitHub Pages

### Backend
Deploy the `backend` folder to:
- Render
- Railway
- Fly.io
- AWS
- Azure

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Connect frontend to deployed backend

In browser console on the deployed frontend:

```js
localStorage.setItem("jobmatch_api", "https://YOUR-BACKEND-DOMAIN");
location.reload();
```

Or replace this line in `frontend/app.js`:

```js
const API_BASE = localStorage.getItem("jobmatch_api") || "http://localhost:8000";
```

with your production backend URL.

## Next live-data step

Replace this function in `backend/main.py`:

```python
def load_jobs():
    return SAMPLE_JOBS
```

with an authorized source connector. The rest of the matching dashboard can stay the same.
