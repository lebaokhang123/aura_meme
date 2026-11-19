# AGENTS.md — AuraMeme Autonomous Engineering Guide (Clean MVP Baseline)

This document defines core operational rules, safety boundaries, and workflow instructions for autonomous coding agents (Google Antigravity and OpenAI Codex) collaborating on the **AuraMeme** codebase under the `feat/mvp-notifications` branch.

---

## 1. Worktree & Branch Rules

- **Active Workspace Directory:** `D:\Big\du_an_lon\aura_meme_p2_clean` ONLY.
- **Active Branch:** `feat/mvp-notifications`.
- **Baseline Commit:** `eacfa7d` (Verified public MVP baseline on `origin/dev`).
- **Protected Trees (NEVER touch or modify):**
  - `D:\Big\du_an_lon\aura_meme` (Main workspace / Personal uncommitted edits).
  - `D:\Big\du_an_lon\aura_meme_mvp` (Private P1 Demo / secrets).
  - `D:\Big\du_an_lon\aura_meme_p2` (Preserved Antigravity P2 workspace — do not reset or clean).
- **Git Policy:**
  - Never push directly to `dev` or `main`.
  - Never force push (`--force`), rebase, or squash approved commit history.
  - Never create PRs autonomously without Owner sign-off.
  - Never run `git add .` or blanket `git clean -fd`. Stage only explicit files per task.
  - Follow Conventional Commits: `fix(...)`, `feat(...)`, `docs(...)`.

---

## 2. Scope & UI Preservation Rules

- **Strict Scope Boundaries:**
  - Focus strictly on assigned tasks: Favicon, Personal Inbox Foundation, Social Notifications, Moderation Notifications, Admin Announcements.
  - NEVER alter existing approved MVP UI: Home, Explore, Profile, Vault, Rank, Auth, Header, Footer, and existing Social components.
  - Do NOT modify layout, typography, theme, Avatar/Background equipment, Level/Realm formulas, Rank, or Vault roulette.
  - Do NOT redesign or add icons/dependencies when existing Material Symbols and utilities suffice.

---

## 3. Database & Security Boundaries

- **Database Safety:**
  - Zero tolerance for destructive database actions.
  - DO NOT run migrations, reset, or drop tables against `aurameme_demo`, `aurameme_dev`, preview, or production databases.
  - If a verified, isolated test database is unavailable, mark database integration tests as **`INTEGRATION UNVERIFIED`**. Never fabricate test results.
- **Authorization & Privacy:**
  - Server-side recipient authorization on all notification endpoints.
  - Users must never access or mark notifications belonging to other accounts.
  - Recipient identity must be resolved from authenticated session cookie, never accepted blindly from client request body.
  - Protect all private meme assets (70 demo memes) and proprietary credentials. Never commit `.env` files, API keys, or signing secrets.

---

## 4. Verification & Testing Commands

### Frontend Unit Tests
```powershell
cd frontend
node --test tests/*.test.mjs
```

### Frontend Production Build
```powershell
cd frontend
npm.cmd run build
```

### Backend Non-Integration Pytest
```powershell
cd backend
Remove-Item Env:AUTH_ENVIRONMENT -ErrorAction SilentlyContinue
Set-Item -Path Env:DATABASE_URL -Value "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
.\.venv_p2\Scripts\python.exe -m pytest -m "not integration" -q
```

---

## 5. Codex Handoff Checklist

When completing tasks and preparing handoff for OpenAI Codex:
1. Document baseline commit (`eacfa7d`), new branch (`feat/mvp-notifications`), and individual task commits.
2. Verify zero secrets, zero N+1 queries, zero cross-user notification leaks, and zero regression of MVP UI.
3. List test results and any parts marked `INTEGRATION UNVERIFIED` or pending Owner decision.
