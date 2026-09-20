import { useRef, useState } from "react";
import { suggestFromResume } from "../api";
import type { Profile } from "../types";

/**
 * The criteria the gate and the scorer both read.
 *
 * Without this the board is ranked against whatever defaults happen to be in
 * the code -- which is not a product, it is one person's script. Everything
 * here is stored server-side and applied on the next pipeline run.
 */

const ROLE_FAMILIES: [string, string][] = [
  ["software_engineering", "Software engineering"],
  ["ai_ml", "AI / ML"],
  ["data", "Data"],
  ["devops_infra", "DevOps / infra"],
  ["security", "Security"],
  ["product", "Product"],
  ["design", "Design"],
];

const ROLE_TYPES: [string, string][] = [
  ["internship", "Internships"],
  ["new_grad_fte", "Entry-level full-time"],
];

function Chips({
  options, selected, onToggle,
}: { options: [string, string][]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(([value, label]) => {
        const on = selected.includes(value);
        return (
          <button
            key={value}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(value)}
            className={`rounded-full border px-2.5 py-1 text-[0.8rem] ${
              on ? "border-eligible bg-eligible text-white" : "border-rule text-muted hover:border-ink hover:text-ink"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Comma-separated fields keep their raw text in state while being edited.
 *
 * Deriving the input's value from `array.join(", ")` on every keystroke means
 * the comma you just typed is parsed into an empty item, filtered out, and
 * erased before you can type the next word -- so a second entry is impossible.
 * The raw string is the source of truth while focused; the array is derived
 * when the value is read.
 */
const toList = (raw: string) => raw.split(",").map((s) => s.trim()).filter(Boolean);

export default function ProfilePanel({
  profile, onSave, saving,
}: { profile: Profile; onSave: (p: Profile) => void; saving: boolean }) {
  const [draft, setDraft] = useState<Profile>(profile);
  const [skillsText, setSkillsText] = useState(profile.skills.join(", "));
  const [citiesText, setCitiesText] = useState(profile.preferred_cities.join(", "));
  const [reading, setReading] = useState(false);
  const [readError, setReadError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setDraft({ ...draft, [k]: v });
  const toggle = (k: "role_families" | "role_types", v: string) =>
    set(k, (draft[k].includes(v) ? draft[k].filter((x) => x !== v) : [...draft[k], v]) as Profile[typeof k]);

  const current: Profile = { ...draft, skills: toList(skillsText), preferred_cities: toList(citiesText) };
  const dirty = JSON.stringify(current) !== JSON.stringify(profile);

  async function handleResume(file: File) {
    setReading(true);
    setReadError(null);
    try {
      const p = await suggestFromResume(file);
      setDraft({
        ...draft,
        headline: p.headline || draft.headline,
        about: p.about || draft.about,
        grad_year: p.grad_year ?? draft.grad_year,
        role_families: p.role_families.length ? p.role_families : draft.role_families,
      });
      if (p.skills.length) setSkillsText(p.skills.join(", "));
      if (p.preferred_cities.length) setCitiesText(p.preferred_cities.join(", "));
    } catch (e) {
      setReadError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <form
      className="grid gap-5 md:grid-cols-2"
      onSubmit={(e) => { e.preventDefault(); onSave(current); }}
    >
      <div className="flex flex-col gap-4">
        <div className="rounded border border-dashed border-rule p-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={reading}
              className="rounded border border-rule px-2.5 py-1.5 text-[0.86rem] hover:border-ink disabled:text-muted"
            >
              {reading ? "Reading resume…" : "Fill from my resume"}
            </button>
            <span className="text-[0.78rem] text-muted">PDF, DOCX or text, up to 5MB</span>
          </div>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.txt,.md,.doc,.docx,application/pdf"
            className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleResume(f); }}
          />
          <p className="mt-2 text-[0.78rem] leading-snug text-muted">
            Your resume is read once to suggest these fields, then discarded. Nothing is stored.
            Check what it filled in — a resume says what you&rsquo;ve done, not what you want next.
          </p>
          {readError && <p className="mt-2 text-[0.8rem] text-blocked">{readError}</p>}
        </div>

        <label className="block">
          <span className="text-[0.84rem] text-muted">What you're looking for</span>
          <input
            value={draft.headline}
            onChange={(e) => set("headline", e.target.value)}
            placeholder="Final-year CS student looking for ML internships"
            className="mt-1 w-full rounded border border-rule bg-card px-2.5 py-1.5"
          />
        </label>

        <label className="block">
          <span className="text-[0.84rem] text-muted">Your skills, comma separated</span>
          <input
            value={skillsText}
            onChange={(e) => setSkillsText(e.target.value)}
            placeholder="python, pytorch, sql, react"
            className="mt-1 w-full rounded border border-rule bg-card px-2.5 py-1.5"
          />
          <span className="mt-1 block text-[0.76rem] text-muted">
            Used to rank matches, never to exclude a role.
          </span>
        </label>

        <label className="block">
          <span className="text-[0.84rem] text-muted">What you&rsquo;ve actually built</span>
          <textarea
            value={draft.about}
            onChange={(e) => set("about", e.target.value)}
            rows={3}
            placeholder="Built a RAG pipeline on Bedrock; two internships; comfortable with distributed systems"
            className="mt-1 w-full resize-y rounded border border-rule bg-card px-2.5 py-1.5"
          />
          <span className="mt-1 block text-[0.76rem] text-muted">
            Projects, internships, the specific systems and tools. This is what makes a match
            say &ldquo;you&rsquo;ve shipped retrieval but not evaluation&rdquo; instead of &ldquo;your skills align&rdquo;.
          </span>
        </label>

        <label className="block">
          <span className="text-[0.84rem] text-muted">Cities you'd move to, comma separated</span>
          <input
            value={citiesText}
            onChange={(e) => setCitiesText(e.target.value)}
            placeholder="Bengaluru, Hyderabad, Pune"
            className="mt-1 w-full rounded border border-rule bg-card px-2.5 py-1.5"
          />
        </label>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <span className="text-[0.84rem] text-muted">Kinds of role</span>
          <div className="mt-1.5"><Chips options={ROLE_TYPES} selected={draft.role_types} onToggle={(v) => toggle("role_types", v)} /></div>
        </div>

        <div>
          <span className="text-[0.84rem] text-muted">Fields you'd work in</span>
          <div className="mt-1.5"><Chips options={ROLE_FAMILIES} selected={draft.role_families} onToggle={(v) => toggle("role_families", v)} /></div>
        </div>

        <label className="flex items-center gap-2 text-[0.88rem]">
          <input
            type="checkbox"
            checked={draft.include_remote_global}
            onChange={(e) => set("include_remote_global", e.target.checked)}
            className="accent-eligible"
          />
          Include roles hiring from any country
        </label>

        <div className="flex flex-wrap items-end gap-4">
          <label className="block">
            <span className="text-[0.84rem] text-muted">Most experience you'd accept</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number" min={0} max={5}
                value={draft.max_yoe}
                onChange={(e) => set("max_yoe", Number(e.target.value))}
                className="w-16 rounded border border-rule bg-card px-2 py-1.5 tnum"
              />
              <span className="text-[0.84rem] text-muted">years</span>
            </div>
          </label>

          <label className="block">
            <span className="text-[0.84rem] text-muted">Graduation year</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                value={draft.grad_year ?? ""}
                onChange={(e) => set("grad_year", e.target.value || null)}
                placeholder="2027"
                className="w-20 rounded border border-rule bg-card px-2 py-1.5 tnum"
              />
              <label className="flex items-center gap-1.5 text-[0.82rem] text-muted">
                <input
                  type="checkbox"
                  checked={draft.enforce_grad_year}
                  onChange={(e) => set("enforce_grad_year", e.target.checked)}
                  className="accent-eligible"
                />
                require it
              </label>
            </div>
            <span className="mt-1 block text-[0.76rem] text-muted">
              Most postings never state a batch year. Requiring it hides them.
            </span>
          </label>
        </div>

        <div className="mt-auto flex items-center gap-3">
          <button
            type="submit"
            disabled={!dirty || saving}
            className="rounded border border-eligible bg-eligible px-3 py-1.5 text-white disabled:border-rule disabled:bg-faint disabled:text-muted"
          >
            {saving ? "Saving…" : "Save criteria"}
          </button>
          {dirty && !saving && (
            <span className="text-[0.8rem] text-muted">Applies on the next pipeline run.</span>
          )}
        </div>
      </div>
    </form>
  );
}
