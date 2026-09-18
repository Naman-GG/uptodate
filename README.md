# Eligibility triage for fresher job postings

Job boards fail freshers in a specific way: search "ML intern, India", get a wall
of results, and almost none are actually open to you. Filtering is keyword-based
while **eligibility lives in unstructured prose** — the experience floor, the
graduation batch, the work-authorisation clause, whether "remote" means remote
*from India*.

This reads every job description with an LLM, extracts the eligibility facts into
a strict schema, and then lets **plain code** make the yes/no call.

## The core claim

> The model reads. The code decides.

The gate Lambda holds **no `bedrock:*` IAM permission at all**. It structurally
cannot ask a model whether you are eligible — it can only apply rules to fields
the extractor already pulled out. Every rejection carries a reason you can read.

That split is the whole architecture, and it is why the results are defensible
rather than vibes.

## Why it is not a keyword filter

Measured on the live corpus (9,040 postings, 76 boards, 2026-09-18):

| Filter | Survivors |
|---|---|
| All postings | 9,040 |
| Location mentions India | 794 |
| …plus a technical-sounding title | 289 |
| …plus an early-career title | 19 |
| …of those 19, actually technical | ~5 |

A keyword search for "intern in India" surfaces *Talent Acquisition Intern*,
*Video Editor Intern* and *Copy Intern*. Reading the description is the only way
to tell those apart from a software internship — which is precisely the job the
extraction pass does.

Regex fails in the other direction too: matching `/fully remote/` against
description text flags *Senior Manager, FP&A — Austin, Texas* as a
work-from-anywhere role, because the phrase appears in boilerplate.

## Sources

Structured public JSON APIs only — no HTML scraping, nothing ToS-hostile.

| Source | Endpoint | Auth |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | none |
| Lever | `api.lever.co/v0/postings/{token}?mode=json` | none |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{token}` | none |

76 boards verified live and recorded in `data/boards.json`.

Anything those boards do not cover — LinkedIn, Naukri, Unstop — is handled by
pasting a job description straight into the same pipeline.

## Layout

```
backend/
  common/     schema, profile, gate, text and http helpers
  adapters/   one module per source, all returning RawPosting
  functions/  ingest · extract · gate · score · api
data/         verified board registry
frontend/     kanban UI
```
