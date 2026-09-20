import type { Column, Funnel, Posting, Profile } from "./types";
import { SEED_POSTINGS, SEED_FUNNEL, SEED_PROFILE } from "./seed";

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

export async function getProfile(): Promise<Profile> {
  if (!BASE) return SEED_PROFILE;
  return req<Profile>("/profile");
}

export async function saveProfile(profile: Partial<Profile>): Promise<Profile> {
  if (!BASE) return { ...SEED_PROFILE, ...profile } as Profile;
  return req<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) });
}

export interface ProposedProfile {
  headline: string;
  skills: string[];
  about: string;
  preferred_cities: string[];
  grad_year: string | null;
  role_families: string[];
}

/** Read a resume and propose profile fields. Never saves -- the user reviews first. */
export async function suggestFromResume(file: File): Promise<ProposedProfile> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  const data = await req<{ proposed: ProposedProfile }>("/profile/suggest", {
    method: "POST",
    body: JSON.stringify({ filename: file.name, content_base64: btoa(binary) }),
  });
  return data.proposed;
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
