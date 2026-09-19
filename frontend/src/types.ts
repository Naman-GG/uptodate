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
  extracted: number;
  gate_passed: number;
  gate_blocked: number;
  scored: number;
  quarantined: number;
}
