export function Gauge({ score, level }: { score: number; level: string }) {
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <div>
      <div className="flex items-end justify-between">
        <p className="font-serif text-4xl tabular-nums text-ink">{clamped}</p>
        <p className="text-sm font-semibold tracking-wide text-muted">{level}</p>
      </div>
      <div
        className="relative mt-3 h-3 overflow-hidden rounded-full bg-line"
        role="meter"
        aria-label="Combined risk"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        aria-valuetext={`${clamped} out of 100, ${level}`}
      >
        <div className="absolute inset-y-0 left-0 w-[30%] bg-approve/80" />
        <div className="absolute inset-y-0 left-[30%] w-[40%] bg-hold/80" />
        <div className="absolute inset-y-0 left-[70%] right-0 bg-block/80" />
        <div
          className="absolute top-1/2 h-5 w-1.5 -translate-y-1/2 rounded-full bg-ink shadow"
          style={{ left: `calc(${clamped}% - 3px)` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] font-medium text-muted">
        <span>0 approve</span>
        <span>31 hold</span>
        <span>71 block</span>
        <span>100</span>
      </div>
    </div>
  );
}
