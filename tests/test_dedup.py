"""Cross-source deduplication.

Two real situations: 14 companies run boards on more than one ATS, and Adzuna
aggregates postings we also pull directly from the employer.
"""
from common.dedup import deduplicate, fingerprint
from common.posting import RawPosting


def posting(**kw):
    base = dict(posting_id="x#1", source="greenhouse", company_token="acme",
                company="Acme", title="Software Engineer Intern",
                locations=["Bengaluru, Karnataka"], description="d" * 100,
                apply_url="https://acme.example/1")
    base.update(kw)
    return RawPosting(**base)


def test_ats_record_wins_over_aggregator():
    """The ATS record carries the full description and a canonical apply link;
    Adzuna gives 500 truncated characters and a tracking bounce."""
    ats = posting(posting_id="greenhouse#coinbase#9", source="greenhouse",
                  description="y" * 5000, apply_url="https://coinbase.com/careers/9")
    agg = posting(posting_id="adzuna#in#1", source="adzuna", title="Software Engineer, Intern",
                  description="y" * 400, apply_url="https://adzuna/bounce")
    kept, dropped = deduplicate([agg, ats])
    assert dropped == 1
    assert kept[0].source == "greenhouse"
    assert "coinbase.com" in kept[0].apply_url


def test_company_suffixes_collide():
    a = posting(company="MongoDB")
    b = posting(posting_id="lever#m#2", source="lever", company="MongoDB Inc")
    assert fingerprint(a)[0] == fingerprint(b)[0]


def test_title_noise_is_ignored_when_matching():
    """'Winter Intern 2027' and 'Intern' are the same role to a deduplicator."""
    a = posting(title="Software Engineer - Winter Intern 2027")
    b = posting(posting_id="lever#a#2", source="lever", title="Software Engineer Intern")
    assert fingerprint(a)[1] == fingerprint(b)[1]


def test_genuinely_different_roles_are_kept():
    a = posting(title="Machine Learning Intern")
    b = posting(posting_id="x#2", title="Data Analyst Intern")
    kept, dropped = deduplicate([a, b])
    assert dropped == 0 and len(kept) == 2


def test_same_role_different_cities_kept():
    """Bengaluru and Pune postings are separate opportunities."""
    a = posting(locations=["Bengaluru"])
    b = posting(posting_id="x#2", locations=["Pune"])
    kept, _ = deduplicate([a, b])
    assert len(kept) == 2
