"use client";

import { ScrollText, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import BusinessForm from "@/components/BusinessForm";
import ResultsPanel from "@/components/ResultsPanel";
import { ApiError, analyzeBusiness } from "@/lib/api";
import type { BusinessInput, PermitAnalysisResponse } from "@/lib/types";

export default function HomePage() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PermitAnalysisResponse | null>(null);
  const [business, setBusiness] = useState<BusinessInput | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(input: BusinessInput) {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await analyzeBusiness(input);
      setResult(response);
      setBusiness(input);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10 sm:py-14">
      <header className="mb-10 text-center">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-civic-200 bg-civic-50 px-3 py-1 text-xs font-semibold text-civic-700">
          <Sparkles size={13} />
          Citation-backed AI compliance guidance
        </div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
          Civic<span className="text-civic-600">Mint</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500 sm:text-base">
          Tell us about your small business and we&apos;ll identify exactly which
          local permits and licenses you need — every requirement linked back to
          the precise municipal code section it comes from.
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} /> Zero-hallucination citation checks
          </span>
          <span className="flex items-center gap-1.5">
            <ScrollText size={14} /> Pre-filled application PDFs
          </span>
        </div>
      </header>

      <div className="space-y-6">
        <BusinessForm onSubmit={handleSubmit} isLoading={isLoading} />

        {error && (
          <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        )}

        {result && business && <ResultsPanel result={result} business={business} />}
      </div>

      <footer className="mt-16 text-center text-xs text-slate-400">
        CivicMint is an informational tool and does not constitute legal advice. Always
        confirm requirements with your local municipality before operating.
      </footer>
    </main>
  );
}
