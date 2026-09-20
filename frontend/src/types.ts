export type Column = "new" | "applied" | "interviewing";

export interface Posting {
  posting_id: string;
  company: string;
  title: string;
  locations: string[];
  apply_url: string;
  source: "greenhouse" | "lever" | "ashby" | "adzuna" | "paste";
  fit_score: number;
  why: string;
  gaps: string[];
  strengths: string[];
  credibility_concern: string | null;
  extraction_confidence: "full" | "partial";
  board_column: Column;
  posted_at?: string;
  extraction?: {
    role_type: string;
    min_yoe: number;
    work_location_mode: string;
    role_family: string;
  };
}

export interface Funnel {
  total_ingested: number;
  screened: number;
  /** Cumulative: everything that has been through extraction. */
  read: number;
  /** Cumulative: everything that cleared the gate. */
  eligible: number;
  prescreened_out: number;
  extracted: number;
  gate_passed: number;
  gate_blocked: number;
  scored: number;
  quarantined: number;
}

export interface Profile {
  profile_id: string;
  label: string;
  role_types: string[];
  max_yoe: number;
  role_families: string[];
  require_technical: boolean;
  countries: string[];
  include_remote_global: boolean;
  exclude_closed: boolean;
  grad_year: string | null;
  enforce_grad_year: boolean;
  headline: string;
  skills: string[];
  about: string;
  preferred_cities: string[];
}
