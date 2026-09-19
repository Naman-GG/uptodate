import { useEffect, useMemo, useState } from "react";
import FunnelBar from "./components/Funnel";
import PostingCard from "./components/PostingCard";
import { dropCard, getFunnel, getPostings, isLive, moveCard } from "./api";
import type { Column, Funnel, Posting } from "./types";

const COLUMNS: { key: Column; heading: string; empty: string }[] = [
  { key: "new", heading: "To review", empty: "Nothing new since the last run. The pipeline checks every morning." },
  { key: "applied", heading: "Applied", empty: "Roles you've applied to will collect here." },
  { key: "interviewing", heading: "Interviewing", empty: "Move a role here once someone replies." },
];

export default function App() {
  const [postings, setPostings] = useState<Posting[] | null>(null);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hideFlagged, setHideFlagged] = useState(false);

  useEffect(() => {
    Promise.all([getPostings(), getFunnel()])
      .then(([p, f]) => {
        setPostings(p);
        setFunnel(f);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const visible = useMemo(
    () => (postings ?? []).filter((p) => !hideFlagged || !p.credibility_concern),
    [postings, hideFlagged],
  );

  const flaggedCount = (postings ?? []).filter((p) => p.credibility_concern).length;

  function handleMove(id: string, column: Column) {
    setPostings((prev) => prev?.map((p) => (p.posting_id === id ? { ...p, board_column: column } : p)) ?? prev);
    moveCard(id, column).catch((e) => setError(String(e)));
  }

  function handleDrop(id: string) {
    setPostings((prev) => prev?.filter((p) => p.posting_id !== id) ?? prev);
    dropCard(id).catch((e) => setError(String(e)));
  }

  if (error) {
    return (
      <main className="mx-auto max-w-[62ch] px-6 py-20">
        <h1 className="font-display text-2xl font-bold">The board couldn&rsquo;t load</h1>
        <p className="mt-2 text-muted">{error}</p>
        <button onClick={() => location.reload()}
                className="mt-4 rounded border border-rule px-3 py-1.5 hover:border-ink">
          Try again
        </button>
      </main>
    );
  }

  return (
    <>
      {funnel && <FunnelBar funnel={funnel} />}

      <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[0.86rem] text-muted">
            {isLive ? "Live pipeline" : "Sample board — pipeline not yet connected"}
          </p>
          {flaggedCount > 0 && (
            <label className="flex items-center gap-2 text-[0.86rem]">
              <input
                type="checkbox"
                checked={hideFlagged}
                onChange={(e) => setHideFlagged(e.target.checked)}
                className="accent-eligible"
              />
              Hide {flaggedCount} flagged {flaggedCount === 1 ? "listing" : "listings"}
            </label>
          )}
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const cards = visible
              .filter((p) => p.board_column === col.key)
              .sort((a, b) => b.fit_score - a.fit_score);
            return (
              <section key={col.key} aria-labelledby={`col-${col.key}`}>
                <div className="mb-2.5 flex items-baseline justify-between border-b border-rule pb-1.5">
                  <h2 id={`col-${col.key}`} className="font-display text-[1.05rem] font-medium">
                    {col.heading}
                  </h2>
                  <span className="tnum text-[0.82rem] text-muted">{cards.length}</span>
                </div>
                {postings === null ? (
                  <p className="text-[0.86rem] text-muted">Loading…</p>
                ) : cards.length === 0 ? (
                  <p className="text-[0.86rem] leading-snug text-muted">{col.empty}</p>
                ) : (
                  <div className="flex flex-col gap-2.5">
                    {cards.map((p) => (
                      <PostingCard key={p.posting_id} posting={p} onMove={handleMove} onDrop={handleDrop} />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </main>

      <footer className="mx-auto max-w-[1180px] px-4 pb-10 text-[0.8rem] leading-relaxed text-muted sm:px-6">
        Postings come from Greenhouse, Lever, Ashby and Adzuna. Every description is read by Claude on
        Amazon Bedrock; the eligibility rules are applied in code, which is why each card carries its reason.
      </footer>
    </>
  );
}
