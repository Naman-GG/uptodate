# uptodate: full technical detail

> The short submission write-up is [WRITE_UP.md](WRITE_UP.md). This is the long version.

**Live:** https://uptodate.dfaqq1w4pxpfm.amplifyapp.com

**Repo:** https://github.com/Naman-GG/uptodate

**Track:** Ship It · solo

---

## The problem

I am a final-year engineering student looking for an AI/ML job/intern in India. the
search is not hard because there is nothing out there. it is hard because almost
everything out there is not for me, and no filter will tell me which.

Search role "AI Intern" on any board and you get a wall of results, most of them are configured for the US and say things like "eligible for US students" or something similar deep down in the JD or need 1+ YOE and several are not engineering roles at all
they are something unrelated masked under tech role which match every
keyword a student would type and a meaningful fraction are training institutes
selling certificates, posting the same opening/advertisement under a dozen different IDs.

The information that would let you skip all of it **is in the description**, phrased differently every time. job boards filter on titles and tags so
they cannot see it. you find out by opening two hundred tabs.

> A non-technical walkthrough is in [HOW-IT-WORKS.md](HOW-IT-WORKS.md).

## What it does

Four stages, each a separate Lambda so a failure or a prompt change only replays
the stage that needs it.

**Ingest.** Pulls structured JSON from Greenhouse, Lever and Ashby board APIs
(keyless, one GET per company) plus Adzuna for India coverage. no HTML scraping.
201 boards verified live and recorded in [`data/boards.json`](../data/boards.json).
Cross-source deduplication collapses the same role appearing on two ATSes,
preferring the record with the full description and a canonical apply link.

**Prescreen.** Deterministic string matching drops titles no fresher could take:
`Senior`, `Staff`, `Principal`, `Engineer III`, plus clearly non-technical
families. 14,547 → 3,713, before a single token is spent. deliberately
conservative: anything requiring the description to be read stays in because
this file must never become the keyword filter the project exists to replace.

**Extract.** One Bedrock call per posting, no tools and no loop, a pure
transform. structure is guaranteed by forcing a tool call whose input schema is
the target shape, which works across every model on Bedrock rather than relying
on a provider-specific parameter. output: `role_type`, `min_yoe`,
`grad_years_eligible`, `work_location_mode`, `countries`, `work_auth_constraint`,
`role_family`, `is_technical`.

Three defences against drift, in order: schema-constrained generation, our own
field validator on top (an enum can be satisfied by the wrong member), then
quarantine. Nothing unvalidated reaches the board. real-world failure rate:
13 of 3,700, or 0.35%.

Idempotent by `extracted_at`, a re-run only pays for rows that still need work,
which is what makes iterating on the prompt affordable. runs 6-wide in a thread
pool; the work is network-bound so threads are the right tool and the GIL is
irrelevant. sequentially this stage would take over two hours.

**Gate.** Plain code applies the profile's hard rules and records every reason.
Extraction gives facts; this decides. **The gate function holds no `bedrock:*`
permission in its IAM policy** so it is structurally incapable of asking a model
whether someone is eligible, see [`template.yaml`](../template.yaml). that is
why "requires 3 years experience" is a fact from the posting rather than a
model's opinion and why the decision is reproducible.

**Score.** A Strands agent, running only on gate survivors. it fetches the
candidate profile as a tool call then writes a fit score and a one-line
justification naming what the role actually asks for.

**Profile.** Stored in DynamoDB, read by both gate and scorer, editable from the
UI. A resume PDF goes to Bedrock as a Converse document block, with no parsing
library involved and comes back as proposed fields the user edits before
saving.

**Orchestration.** Step Functions chains the stages with independent retry
policies and a `has_more` loop so a large backlog drains across invocations
without a longer Lambda. eventBridge fires it daily.

## What it actually did

Measured on the live deployment, 20 September 2026:

| Stage | Count | What happened |
|---|---|---|
| Scanned | **14,547** | pulled from 201 company job boards plus Adzuna |
| Screened in code | 10,834 dropped | senior and clearly non-technical titles, before any model ran |
| Read by Bedrock | **3,700** | every remaining description, in full |
| Quarantined | 13 | could not be read into the schema (0.35%) |
| **Eligible** | **154** | cleared every hard rule |

**A 98.9% reduction, and every step of it is explainable.**

here are the rejection reasons :

| Reason | Postings |
|---|---|
| Experienced role, not internship or new-grad | 3,206 |
| Located in the US, not India | 1,941 |
| Requires 3 years of experience | 1,326 |
| **Not a technical role** | **1,296** |
| Work authorisation: US only | 840 |
| Requires 5 years of experience | 488 |

and this is what makes **uptodate** even better 
1296 is the number of postings that passed a title level screen and still were not engineering jobs. and 840 were excluded on a work-authorisation clause which is eligibility that exists only in prose.

### Example where the case that shows why titles are not enough - 

two postings survived a filter set to AI/ML roles only:

- *"Software Engineering Intern, **Apple Ads machine learning**"*
- *"Software Engineer Intern, **AI ML and Agentic AI**"*

and still appeared with high confidence on the board

Both are titled "Software Engineer" and both were extracted as `role_family: ai_ml`,
because that is what the work is. A keyword filter on the title drops an Apple
Ads ML internship which is a missed opportunity.

## Where AWS fits

Every component used is AWS, none decorative

| Service | Doing what |
|---|---|
| **Amazon Bedrock** | Nova 2 Lite reads 3,700 descriptions; Nova Pro scores survivors and parses resumes |
| **AWS Lambda** | five functions: ingest, extract, gate, score, api |
| **Amazon DynamoDB** | raw payloads, enriched postings, profiles - two GSIs serve the board and the pipeline backlog |
| **AWS Step Functions** | orchestrates the stages with independent retries and a loop for large backlogs |
| **Amazon EventBridge** | daily schedule - it ran overnight unprompted and ingested new postings |
| **Amazon API Gateway** | HTTP API in front of the read/write Lambda |
| **AWS Amplify** | hosts the React frontend |
| **AWS SAM / CloudFormation** | the whole stack is one template |

**Cost: under $10.00.** Extraction over 3,700 postings costs about $5.50 on Nova 2 Lite

free credits covered it entirely. A $25 budget alarm is armed at 40/80/100%.

## What I learned

Almost nothing that went wrong was a logic error. 59 unit tests passed through
every one of these.

**Third-party models on Bedrock are Marketplace purchases and Marketplace has
its own payment rules.** Anthropic models need a Marketplace subscription which
requires a credit card. mine is a debit card and Marketplace in India does not
accept UPI. the subscription failed with `INVALID_PAYMENT_INSTRUMENT` in a loop
that AWS re:Post threads describe as resolvable only by support escalation.

I rewrote the model layer onto the **Converse API**. It is the cross-model
interface on Bedrock, meaning the same request shape works for Nova, Llama,
Mistral or Claude. I moved to Amazon Nova, which AWS serves directly rather than
brokering through Marketplace. structured output
changed from a provider-specific parameter to a forced tool call. the model
became an environment variable instead of an architectural commitment and
extraction got *cheaper*: about $5.50 against roughly $16 on the original plan.
The constraint produced a better design than the one I set out with.

**A `Default:` in a CloudFormation template only applies at stack creation.**
After that the stack remembers the value it was given and reuses it forever.
I changed the default model, redeployed passing overrides only for the API keys,
and the stack silently kept the old one so the Lambda ran against a model the
account cannot reach and quarantined 600 postings in ten seconds. `sam build` and
`sam deploy` both reported success because neither runs the code.

**A DynamoDB query returns at most 1 MB, and `Select=COUNT` is no exception, it counts only what that page scanned.** Without following `LastEvaluatedKey`,
the funnel reported 2,553 postings when the table held 14,526. the number looked
plausible which is what made it dangerous.

**Lambda's architecture must match your dependency wheels.** I declared `arm64`
for the cheaper Graviton runtime, but without Docker, SAM's pip builder resolved
**x86_64** manylinux wheels for the compiled dependencies. It would have deployed
cleanly and then every cold start would have died on an invalid ELF header, with
the error surfacing deep inside `pydantic_core` and pointing nowhere near the
cause.

**Least privilege caught a real bug.** The scorer's IAM role allowed the postings
and profiles tables but not the raw table which is where the full descriptions
live so it crashed with `not authorized to perform dynamodb:GetItem`. that is
the permission list doing its job: it is a declaration of what the code should
do and the code was doing something I had not declared. Had I given every
function blanket DynamoDB access it would have worked silently and so would the
gate, whose whole guarantee is that it *cannot* reach Bedrock. the strictness
that caught this bug is what makes that guarantee mean anything.

**Nova reads PDFs natively.** A resume goes to Converse as a `document` block and
comes back as structured fields. I had assumed I would need a parsing library and
a text-extraction step; neither was necessary.

**Reasoning models put a `reasoningContent` block before the answer.** Indexing
`content[0]["text"]` raises `KeyError` which made me conclude a model had failed
when it had answered correctly. walk the blocks.

## What is not finished/ needs optimisation 

**I tried to detect fake employers and shipped nothing.** Indian job boards are
full of training institutes selling "internships" with certificates and listing many posting with the same description under many IDs. I attempted to flag them seven
times using five prompt revisions and two deterministic rules and every version was
confidently wrong in a different direction. 

each time it was wither calling real companies fake because their names were unfamiliar, or flagging 89% of the board with reasons like *"legitimate company, but the posting
lacks detail"*. the code-based rules were worse because comparing distinct titles to
posting counts flagged Databricks, OpenAI and Stripe and counting repeated exact
titles flagged Stripe's "Software Engineer, Intern" ×5 because large employers
genuinely repeat titles across locations.

The pattern I was chasing needs descriptions compared against each other across
the whole corpus which is a different shape of problem from scoring one posting
at a time. so I removed the feature. because it is worse to not show an opening for hiding the repetition so I commented out that part of the code, reference - 
[`score/app.py`](../backend/functions/score/app.py).

**The reasoning lines are not that effective** Four rounds of prompt work got them to
name what the posting actually asks for like *"remote patient monitoring and
ballistocardiography"*, *"RAG frameworks and LangGraph"* - but the second half
still tends to restate the candidate profile rather than assess the gap.

## To be added / future scope 

**Single profile.** The pipeline is parameterised by `profile_id` and the profile
is stored server-side, so multi-user is a Cognito integration (researched the service but time constraint) so not added yet
