"""Stage 4: score the gate survivors with the Strands agent.

Runs only on postings that passed the gate, which is what keeps the stronger
model's cost proportional to the useful output rather than the corpus size.
"""
from __future__ import annotations

import collections
import json
import logging

from common.ddb import from_ddb, postings_table, profiles_table, query_stage, raw_table, to_ddb
from common.posting import utcnow
from common.profile import DEFAULT_PROFILE, Profile
from common.scorer import build_agent, score_posting

log = logging.getLogger()
log.setLevel(logging.INFO)

SAFETY_MARGIN_MS = 60_000


def _load_profile(profile_id: str) -> Profile:
    item = profiles_table().get_item(Key={"profile_id": profile_id}).get("Item")
    return Profile.from_item(from_ddb(item)) if item else DEFAULT_PROFILE


def handler(event, context):
    profile_id = (event or {}).get("profile_id", "default")
    profile = _load_profile(profile_id)
    table = postings_table()
    raw = raw_table()

    backlog = list(query_stage("gate_passed", limit=300))

    # Employer context must come from the WHOLE corpus, not this batch.
    # MAXGEN posts the same internship under nine ids spread across 14.5k rows;
    # a batch of 154 sees one or two of them and concludes nothing is wrong.
    # One projected scan is a few seconds and it is what makes the duplicate
    # signal true rather than accidental.
    by_company: collections.Counter = collections.Counter()
    titles_by_company: dict[str, list[str]] = collections.defaultdict(list)
    scan_kwargs = {"ProjectionExpression": "company, title"}
    while True:
        page = table.scan(**scan_kwargs)
        for row in page.get("Items", []):
            company = (row.get("company") or "").strip()
            if not company:
                continue
            by_company[company] += 1
            if len(titles_by_company[company]) < 40:
                titles_by_company[company].append(row.get("title", ""))
        token = page.get("LastEvaluatedKey")
        if not token:
            break
        scan_kwargs["ExclusiveStartKey"] = token
    log.info("employer index built over %s companies", len(by_company))

    def company_lookup(company: str) -> dict:
        """What else this employer has open, across the whole corpus."""
        titles = titles_by_company.get(company, [])
        distinct = len({t.strip().lower() for t in titles})
        total = by_company.get(company, len(titles))
        # A real employer hiring several people writes several different
        # postings. A listing farm repeats one title under many ids. Stating
        # the conclusion beats handing the model two numbers and hoping.
        repetition = (
            "several openings share the same title, which is what listing farms do"
            if total >= 3 and distinct <= max(1, total // 3)
            else "openings have distinct titles, consistent with a real employer"
            if total >= 3
            else "too few openings in our index to judge"
        )
        return {
            "company": company,
            "open_roles_in_our_index": total,
            "distinct_titles": distinct,
            "repetition_signal": repetition,
            "sample_titles": titles[:8],
        }

    agent = build_agent(profile, company_lookup)
    scored = failed = flagged = 0

    for item in backlog:
        if context and context.get_remaining_time_in_millis() < SAFETY_MARGIN_MS:
            log.info("stopping early with %s remaining", len(backlog) - scored - failed)
            return _result(profile_id, scored, failed, flagged, has_more=True)

        posting_id = item["posting_id"]
        raw_item = raw.get_item(Key={"posting_id": posting_id}).get("Item")
        merged = {**item, **({"description": from_ddb(raw_item).get("description")} if raw_item else {})}

        assessment = score_posting(agent, merged, from_ddb(item.get("extraction") or {}))
        if assessment is None:
            failed += 1
            continue



        # to_ddb drops None values, so an attribute whose value is None must be
        # left out of the expression too -- referencing :c while the values map
        # omits it fails validation, and most postings have no concern to record.
        sets = [
            "fit_score = :f", "why = :w", "gaps = :g", "strengths = :st",
            "pipeline_stage = :s", "scored_at = :t",
            "board_column = if_not_exists(board_column, :col)",
        ]
        values = {
            ":f": assessment.fit_score,
            ":w": assessment.why,
            ":g": assessment.gaps,
            ":st": assessment.strengths,
            ":s": "scored",
            ":t": utcnow(),
            ":col": "new",
        }
        # Always clear: earlier passes wrote concerns we no longer stand behind.
        removes = ["credibility_concern"]

        expression = "SET " + ", ".join(sets)
        if removes:
            expression += " REMOVE " + ", ".join(removes)

        table.update_item(
            Key={"posting_id": posting_id},
            UpdateExpression=expression,
            ExpressionAttributeValues=to_ddb(values),
        )
        scored += 1

    return _result(profile_id, scored, failed, flagged, has_more=False)


# Employer-legitimacy detection was attempted and removed. The record, because
# the failures were instructive:
#
#   Asking the model      -- five prompt revisions. In turn: missed listing farms;
#                            real companies called fake for having unfamiliar
#                            names; and finally 89% of the board flagged with
#                            reasons like "legitimate company, but the posting
#                            lacks detail".
#   Distinct-title ratio  -- flagged Databricks, OpenAI and Stripe, because a
#                            capped title sample was compared against an uncapped
#                            posting count.
#   Repeated exact titles -- flagged Stripe's "Software Engineer, Intern" x5 and
#                            Databricks' "Solutions Architect" x16. Large
#                            employers repeat titles across locations; that is
#                            ordinary hiring, not spam.
#
# The real pattern -- a training institute posting nine differently-titled
# generic internships -- needs the descriptions compared against each other,
# which is a corpus-level task this per-posting pipeline is the wrong shape for.
# Shipping a flag that mislabels Stripe while missing the actual farm is worse
# than shipping none: it teaches the reader to distrust every other signal.


def _result(profile_id, scored, failed, flagged, has_more):
    result = {
        "profile_id": profile_id,
        "scored": scored,
        "failed": failed,
        "credibility_flagged": flagged,
        "has_more": has_more,
    }
    log.info("score complete: %s", json.dumps(result))
    return result
