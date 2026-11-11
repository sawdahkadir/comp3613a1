# MyAdvisor API — Postman collection

Versioned JSON API at `/api/v1/`, authenticated with a Bearer token from
`POST /api/v1/auth/login`. The existing HTML application and its cookie login
are untouched.

## Files

| File | Purpose |
| --- | --- |
| `MyAdvisor.postman_collection.json` | v2.1 collection: 24 requests across Auth, Student and Advisor folders |
| `MyAdvisor-Local.postman_environment.json` | Local environment with base URL, logins and chained IDs |

## Run it

1. Reset the demo database so the seeded terms and course IDs are predictable:

   ```bash
   python manage.py init
   ```

2. Start the app:

   ```bash
   python manage.py run
   ```

   The default base URL is `http://localhost:5000`.

3. In Postman: **Import** both JSON files, select the **MyAdvisor Local**
   environment, then open the collection and choose **Run**.

Requests run in order and pass values forward through the environment, so a
single Collection Runner pass covers the whole workflow:

- `accessToken` ← Student Login
- `advisorToken` ← Advisor Login
- `courseId`, `courseIdB`, `blockedCourseId` ← Get Course Catalogue (COMP6039, COMP6048, COMP6045)
- `planId` ← Create Plan A
- `planIdB` ← Create Plan B
- `reviewCourseA`, `reviewCourseB` ← advisor review screens

## Request order and expected results

### 1. Auth

| Request | Expected | Notes |
| --- | --- | --- |
| Student Login | 200 | Saves `accessToken` |
| Advisor Login | 200 | Saves `advisorToken` |
| Invalid Login | 401 | Bad password returns JSON `detail` |
| No Token | 401 | Protected route without `Authorization` |

### 2. Student Workflows

| Request | Expected | Notes |
| --- | --- | --- |
| Get Degree Progress | 200 | Credits and completed courses |
| Get Course Catalogue | 200 | Saves the three seeded course IDs |
| List My Plans | 200 | Array of the student's plans |
| Create Empty Plan | 400 | "at least one course" rule |
| Create Plan With Unmet Prerequisite | 400 | COMP6045 needs COMP6037 |
| Create Plan A | 201 | Draft + `Location` header; saves `planId` |
| Create Duplicate Term | 409 | One plan per student per term |
| Get Plan A | 200 | Draft with COMP6039 |
| Update Plan A | 200 | Swaps to COMP6048 |
| Submit Plan A | 200 | Status becomes `submitted` |
| Update Submitted Plan | 409 | Submitted plans are read-only |
| Create Plan B | 201 | Semester 1, 2026/2027; saves `planIdB` |
| Submit Plan B | 200 | Status becomes `submitted` |

### 3. Advisor Workflows

| Request | Expected | Notes |
| --- | --- | --- |
| List Pending Plans | 200 | Includes the newly submitted Plan A |
| Review Plan A | 200 | Saves `reviewCourseA` |
| Approve Plan A | 200 | Status `approved`, feedback saved |
| Review Plan B | 200 | Saves `reviewCourseB` |
| Reject Plan B | 200 | Status `rejected`, feedback saved |
| Approve Plan A Again | 409 | Already reviewed |
| Student Token Cannot Access Advisor | 403 | Role check |

## Environment variables

| Variable | Seeded / source |
| --- | --- |
| `baseUrl` | `http://localhost:5000` |
| `studentUsername` / `studentPassword` | `bob` / `bobpass` |
| `advisorUsername` / `advisorPassword` | `admin` / `adminpass` |
| `accessToken`, `advisorToken` | Filled by the login requests |
| `courseId`, `courseIdB`, `blockedCourseId` | Filled from the catalogue response |
| `planId`, `planIdB` | Filled by the create-plan responses |
| `reviewCourseA`, `reviewCourseB` | Filled by the advisor review responses |

## Notes

- The collection expects a freshly seeded database because term uniqueness
  refuses a second plan for the same semester/year.
- Re-running without `python manage.py init` will fail the create-plan requests
  with `409`; that is the intended rule, not a collection bug.
- Advisor requests always send `{{advisorToken}}` at request level, so they
  never accidentally use the student token.
- No secrets are stored in the exported files beyond the demo passwords.
