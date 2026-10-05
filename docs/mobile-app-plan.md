# SAMS Mobile App — Build Plan

Status: **phases 1–4 built and demoed locally on an Android emulator (2026-10-05); not committed, not deployed.** Remaining: Firebase/APNs credentials, dev/production builds, store submission (all blocked on BGCC accounts).

### Built so far
- Backend: `models/device.py` (`device_tokens`, `notifications`), migration `028_mobile_push`, `services/push_service.py` (hooked into `send_email` *before* the `EMAIL_PAUSED` check, so push keeps working when email is off; FCM via `firebase-admin` when `FIREBASE_CREDENTIALS_PATH` is set, otherwise just records the in-app notification), `routers/mobile.py` (`POST/DELETE /devices`, `GET /notifications`, `POST /notifications/{id}/read`), `tests/test_mobile.py`. Full suite: 64 passed + the 1 known flaky logout test.
- App `mobile/` (Expo SDK 57, TypeScript): login, agreements list (search, status chips, project/subcontractor filters, "Needs my action"), agreement detail (status, approval chain, comments, entered fields, View PDF via share sheet), Alerts tab with unread badge, in-app banner, Account/sign-out. API base URL via `EXPO_PUBLIC_API_URL`.
- Alerts arrive by 15 s polling of `/notifications` + in-app banner (works in Expo Go). Real system push needs a dev/production build + Firebase creds (Expo Go can't load `expo-notifications`).

### Run the demo locally
Backend on a throwaway DB, then `cd mobile && EXPO_PUBLIC_API_URL=http://10.0.2.2:8000/api npx expo start --android` (emulator reaches the host at 10.0.2.2). Don't run Metro with `CI=1` (no reloads).

Original status line: planned, saved 2026-10-01. Blocked on BGCC accounts — see `Mobile-App-Client-Requirements.md` (and `.pdf`) in the repo root. Earlier, simpler pitch: `Mobile-App-Proposal.md`.

## Goal
React Native app (iOS + Android, one codebase). Phase 1 is **read-only**: login, browse all SAMS data with filters. Main purpose: **push notification for every event that sends an email today**, so emails can later be switched off (`EMAIL_PAUSED=true`). No create/update/delete. UI/UX: none exists yet — design the minimal screens with the user before building.

## Decisions already made
- React Native (Expo, EAS cloud builds so no Mac needed) + Firebase Cloud Messaging for both platforms.
- Reviewers sign in with existing SAMS credentials (JWT). Subcontractors are never users — no app for them.
- Accounts must be in BGCC's company name (Apple $99/yr, Google $25 once, Firebase/Expo free).

## Backend work (`backend/`)
1. **Device tokens**: new table `device_tokens` (user_id FK, token unique, platform, created_at, last_seen) + Alembic migration (revision id ≤ 32 chars). Router `POST /devices` (register/upsert for current user), `DELETE /devices/{token}` (on logout). Delete tokens FCM reports as invalid.
2. **Push hook — one choke point**: every email goes through `send_email(to_email, subject, body)` in `services/email_service.py` (callers: `workflow_engine.py` ×5, `routers/comments.py`). Add `send_push(to_email, subject, body)` called **before** the `EMAIL_PAUSED` early return, resolving user by email → their tokens → FCM. Same best-effort contract: never raises, logs failures. This gives push parity with email with zero caller changes. (Later, optionally pass `agreement_id` so a tap deep-links to the agreement; until then derive it, or add an optional kwarg to `send_email` and thread it from the 6 call sites.)
3. FCM sender: `firebase-admin` or plain HTTP v1 with a service-account key; key path via `.env` (per-environment, never committed — see CLAUDE.md §9).
4. **Read endpoints** — mostly exist, reuse; add only what's missing:
   - `GET /workflow/my-agreements`, `GET /workflow/pending`, `GET /workflow/gm-dashboard` (GM), `GET /workflow/agreements/{id}` (summary + comments)
   - `GET /archive/agreements` (filters: project_code/name, subcontractor_name, scope_of_works, status, date, reference; returns `pending_with`), `GET /archive/agreements/{id}`, `/archive/projects/{id}`, `/archive/subcontractors/{id}`
   - `GET /archive/agreements/{id}/download` for PDF viewing (confirm auth works from a mobile client)
   - Gap to check: project and subcontractor list endpoints with no id (only `/projects/` dropdown exists); notification-history list if wanted.
5. Auth: confirm refresh-token flow works for a mobile client (access ~short, refresh long); store tokens in the device keychain (`expo-secure-store`).
6. Tests: pytest for device registration + that `send_email` triggers push even when `EMAIL_PAUSED=true` (FCM call stubbed).

## App (`mobile/`, new top-level dir, Expo + TypeScript)
Screens (proposed, confirm with user):
1. Login
2. Agreements list — tabs/filters mirroring Archive (status buckets, project, subcontractor, scope, date, reference search), shows `pending_with`
3. Agreement detail — status, review chain steps, comments, field summary, PDF viewer
4. Projects / Subcontractors browse (read-only)
5. Settings — logout, notification permission status

Libraries: expo, expo-notifications, @react-native-firebase or Expo push w/ FCM credentials, TanStack Query, axios, zustand (same as web, shares patterns), react-navigation / expo-router. Notification tap → open agreement detail.

## Phases
| # | Deliverable |
|---|---|
| 1 | Backend: `device_tokens` + `/devices`, `send_push` hook, tests; deploy + smoke test on alpha with throwaway users (per CLAUDE.md §11) |
| 2 | App shell: Expo project, login, secure token storage, API client |
| 3 | Lists + filters + detail + PDF view |
| 4 | Push: permission, token registration, receive, tap-through; end-to-end with a real approval |
| 5 | TestFlight / Play internal testing with a few BGCC reviewers; store listing, privacy policy, demo login; submit |
| 6 | After push proven: BGCC decides to set `EMAIL_PAUSED=true` on the VPS |

Phase 1–3 can start before store accounts exist (Android debug builds + Firebase test project). Push on iOS and publishing need the Apple account.

## Open questions
- Which roles get the app (4 approvers + Admin, or everyone incl. read-only)?
- Public store listing vs private distribution?
- Should notification content equal the email text, or a shorter title + body?
- Do notifications need an in-app history list?
- UI/UX direction — none yet.

## Risks
- Apple org enrollment (D-U-N-S + verification call) is the critical path, 1–4 weeks.
- App Store review needs a working demo login and a privacy policy URL.
- KVM 1 VPS: fine for push; PDF viewing from mobile adds load (CLAUDE.md §10).
