"use client";

import { AlertTriangle, MapPin, ShieldAlert } from "lucide-react";
import type { BusinessInput, PermitAnalysisResponse } from "@/lib/types";
import PermitCard from "./PermitCard";

interface Props {
  result: PermitAnalysisResponse;
  business: BusinessInput;
}

export default function ResultsPanel({ result, business }: Props) {
  return (
    <div className="space-y-5">
      <div className="card flex flex-col gap-2 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{result.business_name}</h2>
          <p className="flex items-center gap-1.5 text-sm text-slate-500">
            <MapPin size={14} />
            {result.jurisdiction}
          </p>
        </div>
        <div className="text-xs text-slate-400">
          {result.permits.length} permit{result.permits.length === 1 ? "" : "s"} identified
        </div>
      </div>

      {result.degraded_mode && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <ShieldAlert size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Running in verified fallback mode</p>
            <p className="mt-0.5 text-amber-700">
              Full AI reasoning was unavailable, so results below come directly from
              matched municipal code sections rather than AI-synthesized summaries. Every
              citation is still real and verifiable.
            </p>
          </div>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-slate-400" />
          <ul className="list-disc space-y-1 pl-4">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.permits.length === 0 ? (
        <div className="card p-8 text-center text-sm text-slate-500">
          No permit requirements were found for this business profile in the current
          municipal code index.
        </div>
      ) : (
        <div className="space-y-4">
          {result.permits.map((permit, i) => (
            <PermitCard key={`${permit.citation.chunk_id}-${i}`} permit={permit} business={business} />
          ))}
        </div>
      )}
    </div>
  );
}
