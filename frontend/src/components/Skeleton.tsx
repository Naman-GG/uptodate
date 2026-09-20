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
    <header className="border-b border-rule bg-card" aria-busy="true" aria-label="Loading">
      <div className="mx-auto max-w-[1180px] animate-pulse px-4 py-6 sm:px-6">
        <div className="h-5 w-24 rounded bg-faint" />
        <div className="mt-4 h-[2.6rem] w-[20rem] max-w-full rounded bg-faint" />
        <div className="mt-2 h-4 w-[32rem] max-w-full rounded bg-faint" />
        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
          <div className="flex min-w-[15rem] flex-1 items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-faint" />
            <div className="h-2 w-2 rounded-full bg-faint" />
          </div>
          <div className="h-4 w-56 rounded bg-faint" />
        </div>
      </div>
    </header>
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
