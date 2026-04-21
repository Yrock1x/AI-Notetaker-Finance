"use client";

interface ToggleSwitchProps {
  enabled: boolean;
  onToggle: () => void;
  // Color class applied to the track when the switch is on — pick a tailwind
  // bg-* that matches the surrounding accent (e.g. "bg-primary",
  // "bg-emerald-500"). Defaults to the brand primary so non-calendar callers
  // don't have to think about it.
  colorClass?: string;
  disabled?: boolean;
  title?: string;
  ariaLabel?: string;
}

// Shared binary toggle used anywhere the user flips a per-row preference
// (calendar bot on/off, deal meetings bot on/off, …). Extracted from the
// calendar page's local definition so both surfaces render the same pill.
export function ToggleSwitch({
  enabled,
  onToggle,
  colorClass = "bg-primary",
  disabled = false,
  title = "Toggle",
  ariaLabel,
}: ToggleSwitchProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        // Toggles routinely sit inside larger clickable rows (Link cards,
        // etc.) — stop propagation so flipping the switch doesn't also
        // navigate.
        e.preventDefault();
        e.stopPropagation();
        if (disabled) return;
        onToggle();
      }}
      disabled={disabled}
      className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border border-[#1A1A1A]/10 transition-colors duration-200 ease-in-out focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
        enabled ? colorClass : "bg-[#1A1A1A]/10"
      }`}
      role="switch"
      aria-checked={enabled}
      aria-label={ariaLabel ?? title}
      title={title}
    >
      <span
        className={`pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-3" : "translate-x-0"
        }`}
      />
    </button>
  );
}
