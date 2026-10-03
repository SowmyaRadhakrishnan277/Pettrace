# PetTrace

PetTrace is a small lost-pet matching MVP. It analyzes an uploaded pet photo
and description with an Azure OpenAI vision model, searches local SQLite reports
and publicly indexed Facebook/Instagram pages through Serper, and ranks the
most relevant possible matches. Results are leads for human review, not
confirmed identifications.

## Requirements

- Python 3.10+
- Node.js 18+
- An Azure OpenAI API key and deployed GPT-4.1 model

## Run locally

1. Copy `.env.example` to `.env` and add your Azure OpenAI API key and Serper API
   key from [Serper](https://serper.dev/). You can instead put local credentials
   in `.env.local`, which is ignored by Git. Serper credentials are required for
   live public search. Without them, the application clearly reports that only
   local reports were searched.
2. Start the API:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

   The API loads the sample reports into `backend/data/pettrace.db` on first
   startup and persists the ChromaDB collection in `backend/data/chroma/`.
3. In another terminal, start the UI:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open the Vite URL printed in the terminal (usually
   `http://localhost:5173`).

The API listens on `http://localhost:8000`; its interactive documentation is
at `http://localhost:8000/docs`.

## Matching behavior

The top three reports are ranked using description similarity (25%), extracted
visual characteristics (25%), location text similarity (20%), report-date
proximity (10%), and Azure OpenAI candidate comparison (20%). Location is
matched by text only; PetTrace does not calculate distances. The default
deployment endpoint targets GPT-4.1 using API version `2025-01-01-preview`;
override it with `AZURE_OPENAI_CHAT_COMPLETIONS_URL` for your deployment.

The live provider uses Serper's Google Search API to query publicly indexed
URLs on `facebook.com` and `instagram.com`; it does not log in, crawl, or
scrape those platforms. Search coverage depends on what the search engine has
indexed and what the source pages allow it to show. Results may be missing,
stale, or inaccessible, so users must open and verify the original page.
Titles/snippets, links, and indexed dates are presented only when supplied by
the search response. Profile names, post images, or post dates may be
unavailable; an indexed date is labeled approximate. Candidate post images
are not retrieved or compared by the AI. The user's image is sent to Azure OpenAI;
description, extracted traits, and location are sent to Serper.

Never scrape private content or bypass platform restrictions. Replace
`backend/data/reports.json` only with consented local reports for a real pilot.
Every result is a potential match and requires manual verification against the
original post, image, location, and identifying details.
