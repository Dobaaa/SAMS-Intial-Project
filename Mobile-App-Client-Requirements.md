# Mobile App — Accounts & Payments Required from BGCC

**SAMS — Subcontract Agreement Management System**
Prepared for Bhatia General Contracting Co. (BGCC) — September 2026

To publish the SAMS mobile app (iPhone + Android) and send push notifications, BGCC needs to own the accounts below. **Everything must be registered in BGCC's company name** — never a personal account — so the app stays under BGCC's control if staff or the developer change.

---

## 1. Payments summary

| # | Item | Cost | Frequency | Required? |
|---|---|---|---|---|
| 1 | Apple Developer Program (organization) | **US $99** | Every year | Yes — for iPhone |
| 2 | Google Play Console (organization) | **US $25** | One time | Yes — for Android |
| 3 | D-U-N-S company number | **Free** | One time | Yes — prerequisite for 1 and 2 |
| 4 | Firebase (push notifications) | **Free** | — | Yes |
| 5 | Cloud build service (Expo EAS) | **Free** tier (US $19/month only if BGCC wants faster/more builds) | Optional | No |
| 6 | Server upgrade (current VPS) | Existing plan is fine for notifications; upgrade only if PDF load grows | Optional | No |

**Total required: US $124 in the first year (US $99/year afterwards).**
Payment needs a company credit/debit card that supports international online payments (USD).

---

## 2. Accounts to create

### 2.1 D-U-N-S Number (do this first — it takes the longest)
- Free unique company ID, needed by Apple and Google to verify BGCC is a real organization.
- Request at https://developer.apple.com/enroll/duns-lookup/ (BGCC may already have one — lookup is free).
- **Time: usually 5–14 days** if new. Needs: legal company name, trade licence, Dubai address, phone.

### 2.2 Apple Developer Program — US $99/year
- Enroll as **Organization** at https://developer.apple.com/programs/enroll/
- Needs: D-U-N-S number, legal entity name, a **company email domain** (e.g. name@bgcc.ae — not Gmail), company website, and the enrolling person must have **legal authority to bind BGCC** (owner/director/GM).
- Apple will phone the company to verify. **Time: 2 days – 2 weeks.**
- After approval, BGCC adds the developer (our email) as an **App Manager / Admin** in App Store Connect — no password sharing.

### 2.3 Google Play Console — US $25 one time
- Register as **Organization** at https://play.google.com/console/signup
- Needs: D-U-N-S number, company details, phone + email verification, ID of the account owner.
- **Time: 2–7 days** for verification.
- Then invite our developer as a user with **Release manager** permission.

### 2.4 Firebase (Google) — Free
- Create a project at https://console.firebase.google.com using BGCC's Google account (a shared company Google account, not an individual's).
- Add our developer as **Editor**. Push notifications on both platforms run through this; free at BGCC's volume (~15 users).

### 2.5 Expo account — Free (optional but recommended)
- https://expo.dev — lets us build the iPhone app in the cloud, so **no Mac is required**. Company-owned account, developer invited as member.

---

## 3. Items BGCC must provide (no cost)

| Item | Why |
|---|---|
| Company email address for the developer accounts (e.g. apps@bgcc.ae) | Apple/Google send verification and store-review emails here |
| Public **privacy policy** web page URL | Mandatory for both stores (we can draft the text; BGCC publishes it on its website) |
| Support contact email/URL | Shown on the store listing |
| App name & logo (1024×1024 PNG) | Store listing / app icon. If none, we make a simple one |
| A **demo login** (a dedicated test reviewer account in SAMS) | Apple and Google reviewers need to sign in to approve the app |
| List of employees to receive the app (roles) | Confirms who gets notifications |
| Decision: MDM/internal-only or public store listing? | Public listing = any store visitor sees it (login still required). Private/unlisted distribution is possible but changes the accounts above |

---

## 4. Timeline for the accounts

| Step | Duration |
|---|---|
| D-U-N-S (if BGCC has none) | 5–14 days |
| Apple + Google verification (in parallel) | 2–14 days |
| Firebase / Expo | Same day |

**Start now** — these approvals, not development, are usually the critical path. Development can proceed in parallel; the app can't be published until 2.2 and 2.3 are approved.

---

## 5. Who does what

| Task | BGCC | Us (developer) |
|---|---|---|
| Get/look up D-U-N-S number | ✅ (needs company legal documents) | Guide with the exact steps |
| Enroll in Apple Developer Program & pay $99 | ✅ (needs company authority, card, phone verification call) | Prepare the checklist; cannot do this for them |
| Register Google Play Console & pay $25 | ✅ (company identity + owner ID verification) | Same |
| Create Firebase project (company Google account) | ✅ create; invite us as Editor | Configure everything inside it: FCM, Android/iOS app registration, service-account key |
| Create Expo account | ✅ create; invite us | Configure builds, signing certificates, push keys |
| Invite developer to App Store Connect / Play Console | ✅ | — |
| Publish privacy policy page | ✅ on their website | Write the policy text |
| Provide demo login account for store reviewers | ✅ approves | Create it in SAMS |
| Logo / app name / store description | ✅ approves | Draft; generate icon and screenshots if none |
| Backend: device-token table, push hook beside every email send, read-only mobile endpoints | — | ✅ |
| Build the React Native app (login, lists with filters, detail, notification tap-through) | — | ✅ |
| Generate APNs key, upload to Firebase; Android signing keys | — | ✅ (once invited to their accounts) |
| Build, upload to TestFlight/Play internal testing, store submission, answer store-review questions | — | ✅ (BGCC only clicks final approval if they insist) |
| Test with real BGCC reviewers on phones | ✅ few users | Support |
| Later: turn on `EMAIL_PAUSED=true` after push is proven | ✅ decision | ✅ VPS config |

**In short: BGCC owns identity, payments and legal sign-off; we do all configuration, code, builds and submissions once invited.**

---

## 6. What is NOT needed
- No separate SMS or push-notification vendor (Firebase covers both platforms).
- No new server, database or domain — the app uses the existing SAMS system.
- No monthly fee for the app itself.

*Confidential — Bhatia General Contracting Co. (BGCC), Dubai, UAE — September 2026*
