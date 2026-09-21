# JD Match AI V2

This version changes the product from a job-application tracker to a recruiter-JD matcher.

## Changes

- `Matched Jobs` -> `Matched JDs`
- Removes `Applied`
- Removes `Mark Applied`
- Adds `View LinkedIn Post`
- Searches public/indexed LinkedIn recruiter posts through a search API
- Matches those post snippets to the uploaded resume
- Filters C2C, visa, work model, freshness, and match score

## Important limitation

This does **not** scrape a logged-in LinkedIn account and cannot guarantee every LinkedIn post.
It finds public LinkedIn posts that are indexed by Google through the configured search API.

## Required Render environment variable

Create a Serper API key at `serper.dev`, then in Render add:

- Key: `SERPER_API_KEY`
- Value: your API key

Then redeploy the backend.

## Replace files

Frontend:
- replace `index.html`
- replace `app.js`
- replace `styles.css`

Backend:
- replace `backend/main.py`
- replace `backend/requirements.txt`

Render should redeploy automatically after the GitHub commit.
