import { useState } from "react";
import type { Funnel } from "../types";
import Wordmark from "./Wordmark";

/**
 * The winnowing, compressed.
 *
 * An earlier version gave each stage its own labelled row and explanatory note.
 * Accurate, but it put a pipeline diagram where a person came to look at jobs --
 * four rows of internals before the first card. The collapse is still drawn to
 * scale, because a sliver is the honest shape of 154 out of 14,547, but the
 * machinery now sits behind a disclosure for anyone who wants it.
 */

const fmt = new Intl.NumberFormat("en-IN");

export default function FunnelBar({ funnel }: { funnel: Funnel }) {
  const [open, setOpen] = useState(false);
  const pct = (n: number) => `${Math.max((n / Math.max(funnel.total_ingested, 1)) * 100, 0.2)}%`;

  return (
    <header className="border-b border-rule bg-card">
      <div className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6">
        <Wordmark className="text-[1.15rem]" />

        <h1 className="mt-4 font-display text-[2.4rem] leading-[1.05] font-bold tracking-[-0.02em] sm:text-[2.9rem]">
          <span className="tnum text-eligible">{fmt.format(funnel.eligible)}</span> you can apply to
        </h1>
        <p className="mt-1.5 max-w-[60ch] text-muted">
          Out of <span className="tnum text-ink">{fmt.format(funnel.total_ingested)}</span> postings,
          these are the ones open to someone at your stage, somewhere you&rsquo;re allowed to work,
          asking for experience you already have.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
          <div className="flex min-w-[15rem] flex-1 items-center gap-2" aria-hidden="true">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-faint">
              <div className="h-full rounded-full bg-muted/35" style={{ width: pct(funnel.read) }} />
            </div>
            <div className="h-2 w-2 shrink-0 rounded-full bg-eligible" />
          </div>
          <p className="text-[0.84rem] text-muted">
            <span className="tnum text-ink">{fmt.format(funnel.total_ingested)}</span> scanned
            <span className="mx-1.5">·</span>
            <span className="tnum text-ink">{fmt.format(funnel.read)}</span> read by Bedrock
            <span className="mx-1.5">·</span>
            <span className="tnum text-eligible">{fmt.format(funnel.eligible)}</span> eligible
          </p>
          <button
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="text-[0.82rem] text-muted underline decoration-rule underline-offset-2 hover:text-ink"
          >
            {open ? "Hide how this was filtered" : "How this was filtered"}
          </button>
        </div>

        {open && (
          <dl className="mt-4 grid gap-x-8 gap-y-2 border-t border-faint pt-4 text-[0.84rem] sm:grid-cols-2">
            {[
              ["Scanned", funnel.total_ingested, "pulled from 201 company job boards and Adzuna"],
              ["Screened", funnel.screened, "senior and clearly non-technical titles dropped in code, before any model ran"],
              ["Read", funnel.read, "every remaining description read in full by a model on Amazon Bedrock"],
              ["Eligible", funnel.eligible, "cleared every hard rule: role type, experience, location, work authorisation"],
            ].map(([label, count, note]) => (
              <div key={label as string} className="flex gap-3">
                <dt className="tnum w-20 shrink-0 text-right text-ink">{fmt.format(count as number)}</dt>
                <dd className="text-muted">
                  <span className="text-ink">{label}</span> — {note}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </header>
  );
}
