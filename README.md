# uptodate

### a friendly and smart job board for freshers looking for tech jobs offcampus

**Live:** https://uptodate.dfaqq1w4pxpfm.amplifyapp.com
**Write-up:** [docs/WRITE_UP.md](docs/WRITE_UP.md) ([PDF](docs/WRITE_UP.pdf))
**Also:** [full technical detail](docs/DETAILS.md) · [non-technical walkthrough](docs/HOW-IT-WORKS.md)

Built for WeMakeDevs **First Commit**, Ship It track, solo.

Job boards fail freshers in a specific way: search "ML intern, India", get a wall
of results, and almost none are actually open to you. Filtering is keyword-based
while **eligibility lives in unstructured prose**, the experience floor, the
graduation batch, the work-authorisation clause, whether "remote" means remote
*from India*.

This reads every job description with an LLM, extracts the eligibility facts into
a strict schema, and then lets **plain code** make the yes/no call.

## The core claim

> The model reads. The code decides.

The gate Lambda holds **no `bedrock:*` IAM permission at all**. It structurally
cannot ask a model whether you are eligible, it can only apply rules to fields
the extractor already pulled out. Every rejection carries a reason you can read.

That split is the whole architecture, and it is why the results are defensible
rather than vibes.

## Why it is not a keyword filter

Measured on the live deployment, 201 boards, 20 September 2026:

| Stage | Count |
|---|---|
| Scanned | **14,547** |
| Screened out in code (senior and non-technical titles) | 10,834 |
| Read by Bedrock | **3,700** |
| Quarantined (could not be read into the schema) | 13 |
| **Eligible** | **154** |

The rejection reasons are the argument: **1,296** postings were not technical
roles at all, and **840** required US work authorisation. Both facts live only in
the description.

A keyword search for "intern in India" surfaces *Talent Acquisition Intern*,
*Video Editor Intern* and *Copy Intern*. Reading the description is the only way
to tell those apart from a software internship, which is precisely the job the
extraction pass does.

Regex fails in the other direction too: matching `/fully remote/` against
description text flags *Senior Manager, FP&A, Austin, Texas* as a
work-from-anywhere role, because the phrase appears in boilerplate.

## Sources

Structured public JSON APIs only, no HTML scraping, nothing ToS-hostile.

| Source | Endpoint | Auth |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | none |
| Lever | `api.lever.co/v0/postings/{token}?mode=json` | none |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{token}` | none |
| Adzuna | `api.adzuna.com/v1/api/jobs/in/search/{page}` | free app id + key |

201 boards verified live and recorded in `data/boards.json`. Adzuna covers the
Indian market the ATS boards do not reach; its descriptions are truncated at 500
characters, which is surfaced on each card rather than hidden.

## Layout

```
backend/
  common/       schema, profile, gate, prefilter, converse, scorer, resume
  adapters/     one module per source, all returning RawPosting
  functions/    ingest · extract · gate · score · api
statemachine/   Step Functions pipeline definition
data/           verified board registry
frontend/       React board: funnel, kanban, profile editor
tests/          59 offline + 17 live (RUN_LIVE=1)
docs/           write-up
template.yaml   the whole stack
```

## Running it

```bash
make test                      # 59 offline tests
make build                     # sam build
sam deploy --guided            # first deploy
RUN_LIVE=1 .venv/bin/python -m pytest tests/test_extraction_live.py
```
