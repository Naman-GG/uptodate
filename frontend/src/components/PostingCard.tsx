import type { Column, Posting } from "../types";

const SOURCE_LABEL: Record<Posting["source"], string> = {
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  adzuna: "Adzuna",
  paste: "Pasted",
};

const NEXT: Record<Column, Column | null> = {
  new: "applied",
  applied: "interviewing",
  interviewing: null,
};

const NEXT_LABEL: Record<Column, string> = {
  new: "Mark applied",
  applied: "Mark interviewing",
  interviewing: "",
};

export default function PostingCard({
  posting,
  onMove,
  onDrop,
}: {
  posting: Posting;
  onMove: (id: string, column: Column) => void;
  onDrop: (id: string) => void;
}) {
  const next = NEXT[posting.board_column];
  const flagged = Boolean(posting.credibility_concern);

  return (
    <article
      className={`rounded-lg border bg-card p-3.5 ${
        flagged ? "border-blocked/40" : "border-rule"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="leading-snug font-semibold">
            <a href={posting.apply_url} target="_blank" rel="noreferrer noopener"
               className="underline decoration-rule underline-offset-2 hover:decoration-ink">
              {posting.title}
            </a>
          </h3>
          <p className="mt-0.5 text-[0.86rem] text-muted">
            {posting.company} · {posting.locations.join(", ") || "Location not stated"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className={`tnum text-[1.4rem] leading-none font-medium ${flagged ? "text-blocked" : "text-score"}`}>
            {posting.fit_score}
          </div>
          <div className="text-[0.7rem] text-muted">fit</div>
        </div>
      </div>

      <p className="mt-2.5 text-[0.88rem] leading-snug">{posting.why}</p>

      {flagged && (
        <p className="mt-2.5 border-l-2 border-blocked pl-2.5 text-[0.82rem] leading-snug text-blocked">
          {posting.credibility_concern}
        </p>
      )}

      {posting.gaps.length > 0 && (
        <p className="mt-2 text-[0.82rem] leading-snug text-muted">
          Wants what you haven&rsquo;t shown: {posting.gaps.join(", ")}
        </p>
      )}

      <div className="mt-3 border-t border-faint pt-2.5">
        <p className="text-[0.74rem] leading-snug text-muted">
          {SOURCE_LABEL[posting.source]}
          {posting.extraction_confidence === "partial" && " · description truncated at source"}
        </p>
        <div className="mt-1.5 flex flex-wrap justify-end gap-1.5">
          {next && (
            <button
              onClick={() => onMove(posting.posting_id, next)}
              className="rounded border border-rule px-2 py-1 text-[0.76rem] hover:border-ink"
            >
              {NEXT_LABEL[posting.board_column]}
            </button>
          )}
          <button
            onClick={() => onDrop(posting.posting_id)}
            className="rounded border border-transparent px-2 py-1 text-[0.76rem] text-muted hover:border-rule hover:text-blocked"
            aria-label={`Remove ${posting.title} at ${posting.company}`}
          >
            Not for me
          </button>
        </div>
      </div>
    </article>
  );
}
