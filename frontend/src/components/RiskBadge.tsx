import type { RiskLabel } from "../types";

const CONFIG: Record<RiskLabel, { bg: string; text: string; label: string }> = {
  low: {
    bg: "bg-green-100",
    text: "text-green-800",
    label: "🟢 LOW RISK",
  },
  medium: {
    bg: "bg-yellow-100",
    text: "text-yellow-800",
    label: "🟡 MEDIUM RISK",
  },
  high: {
    bg: "bg-red-100",
    text: "text-red-800",
    label: "🔴 HIGH RISK",
  },
};

interface RiskBadgeProps {
  label: RiskLabel;
}

export function RiskBadge({ label }: RiskBadgeProps) {
  const { bg, text, label: display } = CONFIG[label] ?? CONFIG.medium;
  return (
    <span
      data-testid="risk-badge"
      className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${bg} ${text}`}
    >
      {display}
    </span>
  );
}
