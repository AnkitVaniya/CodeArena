# CodeArena

A LeetCode/Codeforces-style DSA practice platform: solve coding questions,
gain rating with an Elo-style system, get ML-recommended next questions, and
climb a rating-based leaderboard. FastAPI backend, MySQL + MongoDB, vanilla
JS frontend.

## What changed from the original design

The original plan included a resume-upload/skill-matching feature. That's
been removed in favor of a sharper, more cohesive concept: this is now a
pure DSA-practice platform, closer to Codeforces than a job-matching tool.
Every remaining feature serves one loop: **solve → rate → recommend → repeat.**

## The rating system (the core mechanic)

Every question has a numeric `rating` (e.g. 800–2400, Codeforces-style)
instead of just an "easy/medium/hard" label — difficulty labels are now
*derived* from that number (`app/services/rating_service.py::rating_to_difficulty_label`).

Every user has a `rating`, starting at 1200. When you solve a question for
the **first time**, your rating updates using the standard Elo formula:

```
expected = 1 / (1 + 10^((problem_rating - user_rating) / 400))
new_rating = old_rating + K * (1 - expected)      # K = 32
```

Beating a problem rated well above you gains a lot of rating (you were the
underdog). Solving something far below your rating gains almost nothing
(you were expected to win anyway). Re-solving an already-solved question
never changes your rating — checked via `_has_already_solved()` in
`app/api/questions.py` before any Elo math runs.

This is the same idea Codeforces and chess ratings use, just simplified
(no opponent pool, one "opponent" being the problem itself).

## The ML recommender

`app/ml/recommender.py` — combines two real, learned/computed signals:

1. **Content similarity**: TF-IDF vectors over each question's title, tags,
   topic, and description, compared via cosine similarity against questions
   you've already solved. This is a real vector space learned from the
   question corpus — not a hand-written rule — so it can surface questions
   that share vocabulary/tags with ones you enjoyed, even across topics.
2. **Rating fairness**: using the same Elo expected-score curve as the
   rating system, scored so a coin-flip-difficulty question (50% expected
   win) ranks highest — not too easy, not too hard.

These combine with the topic dependency graph (Phase 4) so you're never
recommended a question in a topic you haven't unlocked yet.

Cold start (no solves yet): skips the similarity step, just picks the
closest-rated question in an unlocked topic.

## Project structure by phase

| Phase | What it is | Where |
|---|---|---|
| 1 | Backend skeleton, DB connections, health check | `app/main.py`, `app/db/` |
| 2 | Auth (JWT, bcrypt) | `app/core/security.py`, `app/api/auth.py` |
| 3 | Question bank + code execution + submissions | `app/api/questions.py`, `app/services/code_executor.py` |
| 4 | DSA features: Trie, Heap, Graph | `app/dsa/`, `app/api/dsa_routes.py` |
| 5 | Elo rating + TF-IDF recommender | `app/services/rating_service.py`, `app/ml/recommender.py` |
| 6 | Contests & timers | `app/models/contest.py`, `app/api/contests.py` |
| 7 | Frontend (vanilla JS) | `frontend/` |
| 8 | Tests + Docker deployment | `tests/`, `docker-compose.yml` |

## Run everything with one command

```bash
cp .env.example .env
docker compose up --build
```

Starts 4 containers: `api`, `mysql`, `mongo`, `frontend` (nginx).

Once "Application startup complete" appears, seed sample data (second terminal):

```bash
docker compose exec api python -m app.seed
```

Then open:
- **http://localhost:5500** — the app itself
- **http://localhost:8000/docs** — Swagger API explorer
- **http://localhost:8000/health** — DB connection check

Seeded login: `admin@codearena.dev` / `admin123` (admin — can create questions/contests)

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

17 tests: Trie, Heap, topic Graph, code executor (4 verdict paths), and the
Elo rating math (fairness curve, underdog-gains-more, rating floor at 0).

## Full endpoint list

```
POST   /auth/register
POST   /auth/login
POST   /auth/refresh
GET    /auth/me

GET    /questions
GET    /questions/{id}
POST   /questions            (admin)
POST   /questions/submit

GET    /search/autocomplete
GET    /leaderboard           — ranked by rating
GET    /topics/order
GET    /topics/next-unlocked

GET    /recommend/next-question

POST   /contests             (admin)
GET    /contests
GET    /contests/{id}
POST   /contests/{id}/join
GET    /contests/{id}/leaderboard   — ranked by problems solved in-contest

GET    /health
```

## Known limitations (documented in-code, intentional for a learning project)

- **Code execution** runs Python via subprocess on the host — fine for local
  dev, not a security sandbox. Upgrade path: Judge0.
- **Redis** intentionally left out — leaderboard computes on read.
- **K-factor is fixed at 32** — real rating systems (Codeforces, chess) often
  use a higher K for newer/provisional accounts and lower it as ratings
  stabilize. Worth mentioning as a future improvement if asked in an interview.
