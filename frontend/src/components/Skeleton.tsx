/**
 * Placeholders shaped like the content that replaces them.
 *
 * The first paint happens before the API answers, and three lines of
 * "Loading…" tell the reader nothing about what is coming. These hold the
 * layout still so nothing jumps when the data lands, and they show the shape
 * of a card and of the funnel so the page reads as a board from the first
 * frame. The pulse is suppressed under prefers-reduced-motion by index.css.
 */

export function FunnelSkeleton() {
  return (
    <section className="border-b border-rule bg-card" aria-busy="true" aria-label="Loading screening funnel">
      <div className="mx-auto max-w-[1180px] animate-pulse px-4 py-8 sm:px-6">
        <div className="h-[3rem] w-[22rem] max-w-full rounded bg-faint" />
        <div className="mt-3 h-4 w-[34rem] max-w-full rounded bg-faint" />
        <div className="mt-7 space-y-4">
          {[100, 26, 26, 2].map((w, i) => (
            <div key={i} className="grid grid-cols-[4.8rem_1fr] items-center gap-x-3 sm:grid-cols-[5.5rem_1fr]">
              <div className="ml-auto h-3 w-12 rounded bg-faint" />
              <div className="flex items-center gap-2.5">
                <div className="h-3.5 flex-1 rounded-sm bg-faint">
                  <div className="h-full rounded-sm bg-rule" style={{ width: `${w}%` }} />
                </div>
                <div className="h-3 w-[4.5rem] rounded bg-faint" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-lg border border-rule bg-card p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="h-4 w-3/4 rounded bg-faint" />
          <div className="mt-2 h-3 w-1/2 rounded bg-faint" />
        </div>
        <div className="h-6 w-8 shrink-0 rounded bg-faint" />
      </div>
      <div className="mt-3 space-y-1.5">
        <div className="h-3 w-full rounded bg-faint" />
        <div className="h-3 w-5/6 rounded bg-faint" />
      </div>
      <div className="mt-3 border-t border-faint pt-2.5">
        <div className="h-3 w-24 rounded bg-faint" />
      </div>
    </div>
  );
}

export function ColumnSkeleton({ cards = 2 }: { cards?: number }) {
  return (
    <div className="flex flex-col gap-2.5" aria-busy="true">
      {Array.from({ length: cards }, (_, i) => <CardSkeleton key={i} />)}
    </div>
  );
}
