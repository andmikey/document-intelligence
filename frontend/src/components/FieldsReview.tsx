import { useState } from "react";
import type { ExtractedFields } from "../types";

interface FieldsReviewProps {
  fields: ExtractedFields | null;
  warnings: string[];
  imageB64: string | null;
  onConfirm: (fields: ExtractedFields) => void;
}

export function FieldsReview({
  fields,
  warnings,
  imageB64,
  onConfirm,
}: FieldsReviewProps) {
  const f: Partial<ExtractedFields> = fields ?? {};

  const [entityName, setEntityName] = useState(f.entity_name ?? "");
  const [amountRaw, setAmountRaw] = useState(
    f.amount != null ? String(f.amount) : ""
  );
  const [currency, setCurrency] = useState(f.currency ?? "");
  const [date, setDate] = useState(f.date ?? "");
  const [counterparty, setCounterparty] = useState(f.counterparty ?? "");
  const [platform, setPlatform] = useState(f.platform ?? "");
  const [contactDetails, setContactDetails] = useState(f.contact_details ?? "");
  const [showWarnings, setShowWarnings] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const amount =
      amountRaw.trim() !== "" && !isNaN(Number(amountRaw))
        ? Number(amountRaw)
        : null;

    onConfirm({
      entity_name: entityName.trim() || null,
      amount,
      currency: currency.trim() || null,
      date: date.trim() || null,
      counterparty: counterparty.trim() || null,
      platform: platform.trim() || null,
      contact_details: contactDetails.trim() || null,
      // Red flags are passed through unchanged from the extraction output.
      red_flags: f.red_flags ?? [],
    });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Document preview */}
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">
            Original Document
          </p>
          {imageB64 ? (
            <img
              src={`data:image/jpeg;base64,${imageB64}`}
              alt="Uploaded document"
              className="w-full rounded border border-gray-200"
            />
          ) : (
            <div className="w-full h-48 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-sm">
              No preview
            </div>
          )}
        </div>

        {/* Form */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Review Extracted Fields
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Confirm or edit the extracted fields before scoring.
          </p>

          {warnings.length > 0 && (
            <div className="mb-4">
              <button
                type="button"
                onClick={() => setShowWarnings((v) => !v)}
                className="text-sm text-amber-700 underline"
              >
                ⚠️ {warnings.length} extraction warning
                {warnings.length > 1 ? "s" : ""} {showWarnings ? "▲" : "▼"}
              </button>
              {showWarnings && (
                <ul className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-3 space-y-1">
                  {warnings.map((w, i) => (
                    <li key={i}>
                      <code>{w}</code>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="Entity name"
                value={entityName}
                onChange={setEntityName}
              />
              <Field
                label="Amount"
                value={amountRaw}
                onChange={setAmountRaw}
                inputMode="decimal"
                placeholder="e.g. 500.00"
              />
              <Field
                label="Currency"
                value={currency}
                onChange={setCurrency}
                placeholder="e.g. USD"
              />
              <Field label="Date" value={date} onChange={setDate} />
              <Field
                label="Counterparty"
                value={counterparty}
                onChange={setCounterparty}
              />
              <Field
                label="Platform"
                value={platform}
                onChange={setPlatform}
              />
              <div className="sm:col-span-2">
                <Field
                  label="Contact details"
                  value={contactDetails}
                  onChange={setContactDetails}
                />
              </div>
            </div>

            {(f.red_flags ?? []).length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">Red flags</p>
                <ul className="text-xs font-mono text-gray-600 bg-gray-50 border border-gray-200 rounded p-3 space-y-1">
                  {(f.red_flags ?? []).map((flag, i) => (
                    <li key={i}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}

            <button
              type="submit"
              className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Continue →
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

// Small reusable text input helper (not exported — internal to this file)
function Field({
  label,
  value,
  onChange,
  inputMode,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode={inputMode}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}
