"use client";

import { Building, Calendar, DollarSign, Download, ShieldCheck, ShieldQuestion } from "lucide-react";
import { useState } from "react";
import { ApiError, fillForm, getDownloadUrl } from "@/lib/api";
import type { BusinessInput, PermitRequirement } from "@/lib/types";
import CitationBadge from "./CitationBadge";

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
};

interface Props {
  permit: PermitRequirement;
  business: BusinessInput;
}

export default function PermitCard({ permit, business }: Props) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    if (!permit.form_template_id) return;
    setDownloading(true);
    setError(null);
    try {
      const result = await fillForm(permit.form_template_id, business, permit.permit_name);
      const url = getDownloadUrl(result.filename);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Could not generate the form.";
      setError(message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-900">{permit.permit_name}</h3>
          <p className="mt-0.5 flex items-center gap-1.5 text-sm text-slate-500">
            <Building size={14} />
            {permit.issuing_authority}
          </p>
        </div>
        <span
          className={`flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
            CONFIDENCE_STYLES[permit.confidence]
          }`}
        >
          {permit.confidence === "low" ? <ShieldQuestion size={12} /> : <ShieldCheck size={12} />}
          {permit.confidence} confidence
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-700">{permit.description}</p>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
        {permit.estimated_processing_days != null && (
          <span className="flex items-center gap-1.5">
            <Calendar size={13} />
            ~{permit.estimated_processing_days} business days
          </span>
        )}
        {permit.estimated_fee_usd != null && (
          <span className="flex items-center gap-1.5">
            <DollarSign size={13} />${permit.estimated_fee_usd.toLocaleString()}
          </span>
        )}
      </div>

      <CitationBadge citation={permit.citation} />

      {permit.form_template_id && (
        <div className="mt-3">
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-civic-200 bg-civic-50 px-3 py-1.5 text-xs font-semibold text-civic-700 transition hover:bg-civic-100 disabled:opacity-50"
          >
            <Download size={13} />
            {downloading ? "Generating..." : "Pre-fill application PDF"}
          </button>
          {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
