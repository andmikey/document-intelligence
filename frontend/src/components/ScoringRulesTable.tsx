import type { RuleResult } from "../types";

interface ScoringRulesTableProps {
  rules: RuleResult[];
}

export function ScoringRulesTable({ rules }: ScoringRulesTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-3 py-2 font-medium text-gray-700">
              Rule ID
            </th>
            <th className="text-center px-3 py-2 font-medium text-gray-700">
              Triggered
            </th>
            <th className="text-right px-3 py-2 font-medium text-gray-700">
              Weight
            </th>
            <th className="text-left px-3 py-2 font-medium text-gray-700">
              Explanation
            </th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr
              key={rule.rule_id}
              className="border-b border-gray-100 hover:bg-gray-50"
            >
              <td className="px-3 py-2 font-mono text-xs text-gray-700">
                {rule.rule_id}
              </td>
              <td className="px-3 py-2 text-center">
                {rule.triggered ? (
                  <span className="text-red-600 font-bold">✓</span>
                ) : (
                  <span className="text-gray-400">✗</span>
                )}
              </td>
              <td className="px-3 py-2 text-right text-gray-600">
                {rule.weight.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-gray-600 text-xs">
                {rule.triggered ? rule.explanation : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
