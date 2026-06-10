"use client";

// One tile of the calendar's stats strip.

export function StatTile({
  label,
  value,
  unit,
  sub,
  isLive,
}: {
  label: string;
  value: number;
  unit?: string;
  sub: string;
  isLive?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border bg-white px-4 py-3 ${
        isLive ? "border-red-200" : "border-[#1A1A1A]/5"
      }`}
    >
      <p className="text-[10.5px] font-bold uppercase tracking-widest text-[#1A1A1A]/40">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="font-data text-2xl font-bold text-[#1A1A1A]">
          {value}
        </span>
        {unit && (
          <span className="text-sm font-semibold text-[#1A1A1A]/50">
            {unit}
          </span>
        )}
        {isLive && (
          <span className="ml-auto inline-flex h-2 w-2 animate-pulse rounded-full bg-red-500" />
        )}
      </div>
      <p className="mt-0.5 text-[10.5px] text-[#1A1A1A]/50">{sub}</p>
    </div>
  );
}
