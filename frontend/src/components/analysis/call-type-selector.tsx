import { CallType } from "@/types";
import { CALL_TYPE_LABELS } from "@/lib/constants";

interface CallTypeSelectorProps {
  value: CallType;
  onChange: (value: CallType) => void;
}

export function CallTypeSelector({ value, onChange }: CallTypeSelectorProps) {
  return (
    <div className="flex-1">
      <label className="block text-sm font-medium" htmlFor="call-type-select">
        Call Type
      </label>
      <select
        id="call-type-select"
        value={value}
        onChange={(e) => onChange(e.target.value as CallType)}
        className="mt-1 w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {Object.entries(CALL_TYPE_LABELS).map(([val, label]) => (
          <option key={val} value={val}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
}
