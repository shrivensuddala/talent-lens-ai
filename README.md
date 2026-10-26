# TalentLens AI

TalentLens AI is a small, production-conscious recruitment portal built as a student project. Candidates apply to many jobs with a resume; recruiters review applicants for their own closed jobs, ranked by a deterministic match score, then request an evidence-grounded AI verdict.

## What it does

- JWT authentication with Candidate and Recruiter roles
- Candidate registration, job browsing, asynchronous resume application, and status tracking
- Recruiter job creation, closed-job applicant ranking, candidate detail, and reservation
- PDF/text parsing, logical resume chunks, compact ONNX semantic embeddings, and Qdrant storage
- Deterministic match score: 50% semantic similarity, 30% required skills, 10% experience, 10% preferred skills
- LangChain + Qdrant + Groq RAG verdict generated on demand and cached in PostgreSQL
- One active database-enforced reservation per candidate

The LLM never calculates match scores, ranks candidates, or controls deadlines and reservations.

## Architecture

PostgreSQL is the source of truth for users, jobs, applications, scores, locks, and verdicts. Qdrant stores only resume chunks for scoped semantic retrieval. A FastAPI `BackgroundTasks` worker handles parsing, embedding, vector insertion, and score calculation after the application endpoint has returned `202 Accepted`.

Qdrant metadata always includes `application_id`, `candidate_id`, and `job_id`. The verdict retriever filters by the selected application ID, preventing another candidate’s resume from entering the RAG context.

For local development without Qdrant or Groq, the app uses a lightweight deterministic embedding/verdict fallback so the core workflow remains usable. Docker Compose starts the intended PostgreSQL + Qdrant stack.

## Setup

Copy `backend/.env.example` to the project root as `.env` and set a strong `JWT_SECRET`; add a `GROQ_API_KEY` when you want live RAG verdicts. Docker Compose reads environment variables from the project-root `.env` file.

Run the full local stack:

```bash
docker compose up --build
```

For frontend development with Vite, start the backend and database stack first, then run `npm install` and `npm run dev` inside `frontend`. The Vite development server proxies `/api` requests to `http://localhost:8000`.

Frontend: `http://localhost:5173`
Backend docs: `http://localhost:8000/docs`

## API

The main endpoints are `POST /auth/register`, `POST /auth/login`, `GET /jobs`, `GET /jobs/{id}`, `POST /applications`, `GET /applications/me`, `POST /recruiter/jobs`, `GET /recruiter/jobs`, `GET /recruiter/jobs/{id}/applications`, `POST /recruiter/applications/{id}/verdict`, and candidate reservation/release endpoints. `/api`-prefixed aliases are available for the frontend proxy.

The candidate application endpoint accepts multipart fields `job_id` and `resume` (`.pdf` or `.txt`). The backend rejects expired, closed, and duplicate applications; the database uniquely constrains `(candidate_id, job_id)`.

## Privacy note

Resumes are stored in the local controlled upload directory and are not publicly served. A production deployment should use private object storage, retention/deletion policies, and stricter access auditing.
