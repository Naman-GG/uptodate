/**
 * The name, split the way it reads: "upto" is the state you want to be in,
 * "date" is the part that goes stale. Silver for the half that is just a
 * preposition, the brand green for the half that carries the meaning.
 */
export default function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-[-0.02em] ${className}`}>
      <span className="text-silver">upto</span>
      <span className="text-eligible">date</span>
    </span>
  );
}
