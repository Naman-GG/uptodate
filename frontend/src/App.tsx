import { useEffect, useMemo, useState } from "react";
import FunnelBar from "./components/Funnel";
import PostingCard from "./components/PostingCard";
import ProfilePanel from "./components/ProfilePanel";
import { ColumnSkeleton, FunnelSkeleton } from "./components/Skeleton";
import { dropCard, getFunnel, getPostings, getProfile, isLive, moveCard, saveProfile } from "./api";
import type { Column, Funnel, Posting, Profile } from "./types";

const COLUMNS: { key: Column; heading: string; empty: string }[] = [
  { key: "new", heading: "To review", empty: "Nothing new since the last run. The pipeline checks every morning." },
  { key: "applied", heading: "Applied", empty: "Roles you've applied to will collect here." },
  { key: "interviewing", heading: "Interviewing", empty: "Move a role here once someone replies." },
];

export default function App() {
  const [postings, setPostings] = useState<Posting[] | null>(null);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [showProfile, setShowProfile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overColumn, setOverColumn] = useState<Column | null>(null);

  useEffect(() => {
    Promise.all([getPostings(), getFunnel(), getProfile()])
      .then(([p, f, pr]) => { setPostings(p); setFunnel(f); setProfile(pr); })
      .catch((e) => setError(String(e)));
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (postings ?? []).filter((p) => {
      if (p.fit_score < minScore) return false;
      if (!q) return true;
      return (
        p.title.toLowerCase().includes(q) ||
        p.company.toLowerCase().includes(q) ||
        p.locations.join(" ").toLowerCase().includes(q) ||
        (p.why ?? "").toLowerCase().includes(q)
      );
    });
  }, [postings, query, minScore]);


  function handleMove(id: string, column: Column) {
    setPostings((prev) => prev?.map((p) => (p.posting_id === id ? { ...p, board_column: column } : p)) ?? prev);
    moveCard(id, column).catch((e) => setError(String(e)));
  }

  function handleDrop(id: string) {
    setPostings((prev) => prev?.filter((p) => p.posting_id !== id) ?? prev);
    dropCard(id).catch((e) => setError(String(e)));
  }

  async function handleSaveProfile(next: Profile) {
    setSaving(true);
    try {
      const updated = await saveProfile(next);
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <main className="mx-auto max-w-[62ch] px-6 py-20">
        <h1 className="font-display text-2xl font-bold">The board couldn&rsquo;t load</h1>
        <p className="mt-2 text-muted">{error}</p>
        <button onClick={() => location.reload()} className="mt-4 rounded border border-rule px-3 py-1.5 hover:border-ink">
          Try again
        </button>
      </main>
    );
  }

  return (
    <>
      {funnel ? <FunnelBar funnel={funnel} /> : <FunnelSkeleton />}

      <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6">
        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2.5">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, company, city"
            aria-label="Search postings"
            className="min-w-[13rem] flex-1 rounded border border-rule bg-card px-2.5 py-1.5"
          />

          <label className="flex items-center gap-2 text-[0.86rem] whitespace-nowrap">
            Min fit
            <input
              type="range" min={0} max={90} step={10}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-24 accent-eligible"
            />
            <span className="tnum w-6">{minScore}</span>
          </label>

          {postings && (visible.length !== postings.length) && (
            <span className="text-[0.86rem] whitespace-nowrap text-muted">
              showing <span className="tnum text-ink">{visible.length}</span> of{" "}
              <span className="tnum">{postings.length}</span>
            </span>
          )}

          <button
            onClick={() => setShowProfile((v) => !v)}
            aria-expanded={showProfile}
            className="rounded border border-rule px-2.5 py-1.5 text-[0.86rem] hover:border-ink"
          >
            {showProfile ? "Hide criteria" : "Edit criteria"}
          </button>
        </div>

        {showProfile && profile && (
          <section className="mb-6 rounded-lg border border-rule bg-card p-4" aria-label="Your criteria">
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h2 className="font-display text-[1.05rem] font-medium">Who this board is for</h2>
              {saved && <span className="text-[0.82rem] text-eligible">Saved</span>}
            </div>
            <ProfilePanel profile={profile} onSave={handleSaveProfile} saving={saving} />
          </section>
        )}

        <div className="grid gap-5 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const cards = visible
              .filter((p) => p.board_column === col.key)
              .sort((a, b) => b.fit_score - a.fit_score);
            const isTarget = overColumn === col.key && dragId !== null;
            return (
              <section
                key={col.key}
                aria-labelledby={`col-${col.key}`}
                onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOverColumn(col.key); }}
                onDragLeave={(e) => {
                  // Leaving for a child element still fires dragleave; ignore those.
                  if (!e.currentTarget.contains(e.relatedTarget as Node)) setOverColumn(null);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const id = e.dataTransfer.getData("text/plain");
                  setOverColumn(null);
                  setDragId(null);
                  if (id) handleMove(id, col.key);
                }}
                className={`rounded-lg p-1.5 transition-colors ${
                  isTarget ? "bg-faint ring-1 ring-eligible/40" : ""
                }`}
              >
                <div className="mb-2.5 flex items-baseline justify-between border-b border-rule pb-1.5">
                  <h2 id={`col-${col.key}`} className="font-display text-[1.05rem] font-medium">{col.heading}</h2>
                  <span className="tnum text-[0.82rem] text-muted">{cards.length}</span>
                </div>
                {postings === null ? (
                  <ColumnSkeleton cards={col.key === "new" ? 3 : 1} />
                ) : cards.length === 0 ? (
                  <p className={`rounded border border-dashed px-3 py-6 text-center text-[0.86rem] leading-snug text-muted ${
                    isTarget ? "border-eligible" : "border-faint"
                  }`}>
                    {isTarget ? "Drop to move it here"
                      : query || minScore > 0 ? "Nothing matches those filters."
                      : col.empty}
                  </p>
                ) : (
                  <div className="flex flex-col gap-2.5">
                    {cards.map((p) => (
                      <PostingCard
                        key={p.posting_id}
                        posting={p}
                        onMove={handleMove}
                        onDrop={handleDrop}
                        onDragStart={setDragId}
                        onDragEnd={() => { setDragId(null); setOverColumn(null); }}
                        dragging={dragId === p.posting_id}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </main>

      <footer className="mx-auto max-w-[1180px] px-4 pb-10 text-[0.8rem] leading-relaxed text-muted sm:px-6">
        {isLive ? "Live pipeline. " : "Sample board. "}
        Postings come from Greenhouse, Lever, Ashby and Adzuna. Every description is read by a model on
        Amazon Bedrock; the eligibility rules are applied in code, which is why each card carries its reason.
      </footer>
    </>
  );
}
