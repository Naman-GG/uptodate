import type { Funnel, Posting, Profile } from "./types";

/**
 * Seed data for reviewing the interface before the pipeline is deployed.
 *
 * Every posting here is real -- pulled from the live corpus during development
 * (Greenhouse, Lever, Ashby and Adzuna). The `fit_score`, `why` and `gaps`
 * fields are illustrative of what the scoring agent produces; everything else
 * is as the source returned it.
 */

const p = (x: Omit<Posting, "board_column"> & { board_column?: Posting["board_column"] }): Posting => ({
  board_column: "new",
  ...x,
});

export const SEED_POSTINGS: Posting[] = [
  p({
    posting_id: "lever#epifi#ai-eng-intern",
    company: "Fi Money",
    title: "Ai Engg Intern",
    locations: ["Bangalore"],
    apply_url: "https://jobs.lever.co/epifi",
    source: "lever",
    fit_score: 91,
    why: "Applied ML work on a consumer fintech product, open to current students with no experience floor.",
    gaps: ["No named production LLM deployment"],
    strengths: ["PyTorch", "Agentic systems", "Python"],
    credibility_concern: null,
    extraction_confidence: "full",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "onsite", role_family: "ai_ml" },
  }),
  p({
    posting_id: "lever#epifi#ds-ml-intern",
    company: "Fi Money",
    title: "DS/ML Intern",
    locations: ["Bangalore"],
    apply_url: "https://jobs.lever.co/epifi",
    source: "lever",
    fit_score: 88,
    why: "Data science internship asking for Python and classical ML, both stated as learnable on the job.",
    gaps: ["Prefers prior SQL at scale"],
    strengths: ["Python", "SQL", "Statistics"],
    credibility_concern: null,
    extraction_confidence: "full",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "onsite", role_family: "ai_ml" },
  }),
  p({
    posting_id: "greenhouse#stripe#swe-intern-blr",
    company: "Stripe",
    title: "Software Engineer, Intern",
    locations: ["Bengaluru"],
    apply_url: "https://stripe.com/jobs",
    source: "greenhouse",
    fit_score: 84,
    why: "Structured internship in Bengaluru with no experience floor and an explicit student track.",
    gaps: ["Large-scale distributed systems", "Ruby"],
    strengths: ["Backend", "Python", "API design"],
    credibility_concern: null,
    extraction_confidence: "full",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "onsite", role_family: "software_engineering" },
  }),
  p({
    posting_id: "adzuna#in#coinbase-ml-intern",
    company: "Coinbase",
    title: "Machine Learning Engineer Intern",
    locations: ["India"],
    apply_url: "https://www.adzuna.in/details/5878277468",
    source: "adzuna",
    fit_score: 80,
    why: "Remote-India ML internship; description is truncated at source so the experience floor is inferred, not stated.",
    gaps: ["Crypto domain knowledge"],
    strengths: ["PyTorch", "Python"],
    credibility_concern: null,
    extraction_confidence: "partial",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "remote_country", role_family: "ai_ml" },
  }),
  p({
    posting_id: "greenhouse#rubrik#winter-intern",
    company: "Rubrik",
    title: "Software Engineer - Winter Intern",
    locations: ["Bangalore"],
    apply_url: "https://www.rubrik.com/company/careers",
    source: "greenhouse",
    fit_score: 76,
    why: "Winter internship in Bangalore, open to students graduating in the next two cycles.",
    gaps: ["Go", "Kubernetes"],
    strengths: ["Systems programming", "C++"],
    credibility_concern: null,
    extraction_confidence: "full",
    board_column: "applied",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "onsite", role_family: "software_engineering" },
  }),
  p({
    posting_id: "greenhouse#twilio#swe-intern-remote",
    company: "Twilio",
    title: "Software Engineer Intern (23 weeks)",
    locations: ["Remote - India"],
    apply_url: "https://www.twilio.com/en-us/company/jobs",
    source: "greenhouse",
    fit_score: 73,
    why: "Fully remote from India, 23-week term, explicitly open to students with no prior industry experience.",
    gaps: ["Telephony/CPaaS background"],
    strengths: ["Backend", "REST APIs"],
    credibility_concern: null,
    extraction_confidence: "full",
    board_column: "applied",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "remote_country", role_family: "software_engineering" },
  }),
  p({
    posting_id: "adzuna#in#peakflo-ml-intern",
    company: "Peakflo",
    title: "Machine Learning (ML) Engineer Intern",
    locations: ["India"],
    apply_url: "https://www.adzuna.in/details/5889517261",
    source: "adzuna",
    fit_score: 68,
    why: "ML internship at a B2B fintech; posting text is cut short, so scored conservatively.",
    gaps: ["Production MLOps", "Document extraction"],
    strengths: ["Python", "ML fundamentals"],
    credibility_concern: null,
    extraction_confidence: "partial",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "remote_country", role_family: "ai_ml" },
  }),
  p({
    posting_id: "adzuna#in#maxgen-ml-ahmedabad",
    company: "MAXGEN Technologies",
    title: "Machine learning Internship in Ahmedabad",
    locations: ["India"],
    apply_url: "https://www.adzuna.in/details/5875071104",
    source: "adzuna",
    fit_score: 22,
    why: "Generic internship advert with no named team, product or responsibilities.",
    gaps: [],
    strengths: [],
    credibility_concern:
      "Same listing reposted under several IDs. The employer offers training and certificates rather than describing a product team.",
    extraction_confidence: "partial",
    board_column: "new",
    extraction: { role_type: "internship", min_yoe: 0, work_location_mode: "onsite", role_family: "ai_ml" },
  }),
];

/**
 * `total_ingested` and `screened` are measured from the live corpus on
 * 2026-09-18. The later stages are illustrative until the pipeline has run.
 */
export const SEED_FUNNEL: Funnel = {
  total_ingested: 14547,
  prescreened_out: 10834,
  screened: 3713,
  read: 3700,
  eligible: 169,
  extracted: 0,
  quarantined: 13,
  gate_blocked: 3531,
  gate_passed: 0,
  scored: 169,
};

export const SEED_PROFILE: Profile = {
  profile_id: "default",
  label: "Fresher / new grad",
  role_types: ["internship", "new_grad_fte"],
  max_yoe: 1,
  role_families: ["software_engineering", "ai_ml", "data", "devops_infra", "security"],
  require_technical: true,
  countries: ["IN"],
  include_remote_global: true,
  exclude_closed: true,
  grad_year: null,
  enforce_grad_year: false,
  headline: "",
  skills: [],
  about: "",
  preferred_cities: [],
};
