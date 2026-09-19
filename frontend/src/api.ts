import type { Column, Funnel, Posting } from "./types";
import { SEED_POSTINGS, SEED_FUNNEL } from "./seed";

// Set at build time by Amplify. When absent the board runs on seed data so the
// interface is reviewable before the pipeline is deployed.
const BASE = import.meta.env.VITE_API_URL ?? "";

export const isLive = Boolean(BASE);

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function getPostings(): Promise<Posting[]> {
  if (!BASE) return SEED_POSTINGS;
  const data = await req<{ postings: Posting[] }>("/postings?limit=200");
  return data.postings;
}

export async function getFunnel(): Promise<Funnel> {
  if (!BASE) return SEED_FUNNEL;
  return req<Funnel>("/funnel");
}

export async function moveCard(id: string, column: Column): Promise<void> {
  if (!BASE) return;
  await req(`/postings/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ column }),
  });
}

export async function dropCard(id: string): Promise<void> {
  if (!BASE) return;
  await req(`/postings/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export interface Verdict {
  extraction: Record<string, unknown>;
  gate: { passed: boolean; reasons: string[]; matched: string[] };
}

export async function evaluate(body: {
  company: string;
  title: string;
  description: string;
}): Promise<Verdict> {
  return req<Verdict>("/evaluate", { method: "POST", body: JSON.stringify(body) });
}
