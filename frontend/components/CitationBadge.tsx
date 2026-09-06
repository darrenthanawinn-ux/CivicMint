"use client";

import { BookText, ChevronDown } from "lucide-react";
import { useState } from "react";
import type { CitationMeta } from "@/lib/types";

export default function CitationBadge({ citation }: { citation: CitationMeta }) {
  const [open, setOpen] = useState(false);
  const scorePercent = Math.round(citation.retrieval_score * 100);

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs font-medium text-slate-600 hover:text-civic-700"
      >
        <span className="flex items-center gap-1.5">
          <BookText size={13} />
          {citation.source_document} &middot; Section {citation.section}
        </span>
        <span className="flex items-center gap-1.5 text-slate-400">
          {scorePercent}% match
          <ChevronDown
            size={14}
            className={`transition-transform ${open ? "rotate-180" : ""}`}
          />
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-200 px-3 py-2 text-xs leading-relaxed text-slate-600">
          &ldquo;{citation.excerpt}&rdquo;
          <div className="mt-1 font-mono text-[10px] text-slate-400">
            chunk_id: {citation.chunk_id}
          </div>
        </div>
      )}
    </div>
  );
}
