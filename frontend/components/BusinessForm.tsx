"use client";

import { Building2, Loader2, SendHorizonal } from "lucide-react";
import { useState } from "react";
import type { BusinessInput, BusinessType } from "@/lib/types";
import { BUSINESS_TYPE_LABELS } from "@/lib/types";

interface Props {
  onSubmit: (business: BusinessInput) => void;
  isLoading: boolean;
}

const BUSINESS_TYPES = Object.keys(BUSINESS_TYPE_LABELS) as BusinessType[];

const EMPTY_FORM: BusinessInput = {
  business_name: "",
  business_type: "restaurant",
  address: "",
  city: "",
  state: "",
  description: "",
  employee_count: 1,
  serves_alcohol: false,
  outdoor_seating: false,
  square_footage: undefined,
};

export default function BusinessForm({ onSubmit, isLoading }: Props) {
  const [form, setForm] = useState<BusinessInput>(EMPTY_FORM);
  const [clientError, setClientError] = useState<string | null>(null);

  function update<K extends keyof BusinessInput>(key: K, value: BusinessInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setClientError(null);

    if (form.description.trim().length < 10) {
      setClientError("Please describe your business in at least a sentence or two.");
      return;
    }
    if (form.address.trim().length < 5) {
      setClientError("Please enter a valid street address.");
      return;
    }
    onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} className="card p-6 space-y-5">
      <div className="flex items-center gap-2 text-civic-700">
        <Building2 size={20} />
        <h2 className="text-lg font-bold">Tell us about your business</h2>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="business_name">
            Business name
          </label>
          <input
            id="business_name"
            className="input-field"
            required
            maxLength={150}
            value={form.business_name}
            onChange={(e) => update("business_name", e.target.value)}
            placeholder="Sunrise Coffee Co."
          />
        </div>

        <div>
          <label className="label" htmlFor="business_type">
            Business type
          </label>
          <select
            id="business_type"
            className="input-field"
            value={form.business_type}
            onChange={(e) => update("business_type", e.target.value as BusinessType)}
          >
            {BUSINESS_TYPES.map((type) => (
              <option key={type} value={type}>
                {BUSINESS_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>

        <div className="sm:col-span-2">
          <label className="label" htmlFor="address">
            Street address
          </label>
          <input
            id="address"
            className="input-field"
            required
            maxLength={250}
            value={form.address}
            onChange={(e) => update("address", e.target.value)}
            placeholder="123 Main Street, Suite 4"
          />
        </div>

        <div>
          <label className="label" htmlFor="city">
            City
          </label>
          <input
            id="city"
            className="input-field"
            required
            maxLength={100}
            value={form.city}
            onChange={(e) => update("city", e.target.value)}
            placeholder="Springfield"
          />
        </div>

        <div>
          <label className="label" htmlFor="state">
            State
          </label>
          <input
            id="state"
            className="input-field"
            required
            maxLength={56}
            value={form.state}
            onChange={(e) => update("state", e.target.value)}
            placeholder="IL"
          />
        </div>

        <div>
          <label className="label" htmlFor="employee_count">
            Number of employees
          </label>
          <input
            id="employee_count"
            type="number"
            min={0}
            max={100000}
            className="input-field"
            value={form.employee_count}
            onChange={(e) => update("employee_count", Number(e.target.value) || 0)}
          />
        </div>

        <div>
          <label className="label" htmlFor="square_footage">
            Square footage (optional)
          </label>
          <input
            id="square_footage"
            type="number"
            min={0}
            className="input-field"
            value={form.square_footage ?? ""}
            onChange={(e) =>
              update("square_footage", e.target.value ? Number(e.target.value) : undefined)
            }
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-300 text-civic-600 focus:ring-civic-500"
            checked={form.serves_alcohol}
            onChange={(e) => update("serves_alcohol", e.target.checked)}
          />
          Serves alcohol
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-300 text-civic-600 focus:ring-civic-500"
            checked={form.outdoor_seating}
            onChange={(e) => update("outdoor_seating", e.target.checked)}
          />
          Outdoor seating / sidewalk area
        </label>
      </div>

      <div>
        <label className="label" htmlFor="description">
          Describe your business
        </label>
        <textarea
          id="description"
          className="input-field min-h-[110px] resize-y"
          required
          minLength={10}
          maxLength={1200}
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          placeholder="A 900 sq ft neighborhood coffee shop with a small kitchen, 4 employees, and a few outdoor tables on the sidewalk."
        />
        <p className="mt-1 text-xs text-slate-400">{form.description.length}/1200 characters</p>
      </div>

      {clientError && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{clientError}</p>
      )}

      <button type="submit" className="btn-primary w-full sm:w-auto" disabled={isLoading}>
        {isLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Analyzing municipal code...
          </>
        ) : (
          <>
            <SendHorizonal size={16} />
            Find my permits
          </>
        )}
      </button>
    </form>
  );
}
