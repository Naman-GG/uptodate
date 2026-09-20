import type { Funnel } from "../types";

/**
 * The winnowing, drawn to scale.
 *
 * A job board shows you what survived; the work is in what didn't. Of 14,564
 * postings, all but a few dozen are ineligible for a fresher, and no keyword
 * search can tell you which.
 *
 * Bars are LINEAR, deliberately. A log scale would make the final row a
 * comfortable twelve percent of the width instead of the sliver it really is,
 * which would be a lie told for the sake of a tidier graphic. The sliver is
 * the product.
 */

const fmt = new Intl.NumberFormat("en-IN");

export default function FunnelBar({ funnel }: { funnel: Funnel }) {
  const rows = [
    { label: "scanned", count: funnel.total_ingested, note: "pulled from 201 job boards" },
    { label: "screened", count: funnel.screened, note: "senior and non-technical titles dropped in code" },
    { label: "read", count: funnel.read, note: "every description read by Bedrock" },
    { label: "eligible", count: funnel.eligible, note: "cleared every hard rule", final: true },
  ];
  const max = Math.max(...rows.map((r) => r.count), 1);
  const discarded = funnel.total_ingested - funnel.eligible;

  return (
    <section className="border-b border-rule bg-card" aria-label="Screening funnel">
      <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-6">
        <h1 className="font-display text-[2.6rem] leading-[1.05] font-bold tracking-[-0.02em] sm:text-[3.3rem]">
          <span className="tnum text-eligible">{fmt.format(funnel.eligible)}</span> you can apply to
        </h1>
        <p className="mt-2 max-w-[64ch] text-muted">
          Out of <span className="tnum text-ink">{fmt.format(funnel.total_ingested)}</span> postings. The other{" "}
          <span className="tnum text-ink">{fmt.format(discarded)}</span> wanted experience you don&rsquo;t have, a
          graduation year that isn&rsquo;t yours, or the right to work somewhere you can&rsquo;t.
        </p>

        <ol className="mt-7 space-y-2.5">
          {rows.map((r) => {
            const pct = (r.count / max) * 100;
            return (
              <li key={r.label} className="grid grid-cols-[4.8rem_1fr] items-center gap-x-3 sm:grid-cols-[5.5rem_1fr]">
                <span className="text-right text-[0.84rem] text-muted">{r.label}</span>
                <div className="flex min-w-0 items-center gap-2.5">
                  <div className="h-3.5 flex-1 rounded-sm bg-faint">
                    <div
                      className={`h-full rounded-sm ${r.final ? "bg-eligible" : "bg-muted/40"}`}
                      style={{ width: `${Math.max(pct, 0.18)}%` }}
                    />
                  </div>
                  <span className={`tnum w-[4.5rem] shrink-0 text-right text-[0.95rem] ${r.final ? "text-eligible" : ""}`}>
                    {fmt.format(r.count)}
                  </span>
                </div>
                <span />
                <span className="text-[0.78rem] leading-snug text-muted">{r.note}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
