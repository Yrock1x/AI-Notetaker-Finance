"use client";

// Renders the toast queue from the toast-store in a fixed bottom-right stack.
// Click a toast to dismiss it; each also auto-dismisses after a few seconds.

import { useToastStore } from "@/lib/toast-store";

const KIND_CLASSES: Record<string, string> = {
  error: "bg-red-600 text-white",
  success: "bg-emerald-600 text-white",
  info: "bg-neutral-800 text-white",
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] flex max-w-sm flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => dismiss(t.id)}
          className={`rounded-md px-4 py-3 text-left text-sm shadow-lg ${
            KIND_CLASSES[t.kind] ?? KIND_CLASSES.info
          }`}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}
