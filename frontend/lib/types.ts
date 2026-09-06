export type BusinessType =
  | "restaurant"
  | "retail"
  | "home_based"
  | "professional_services"
  | "construction_contractor"
  | "food_truck"
  | "salon_personal_care"
  | "bar_nightlife"
  | "other";

export interface BusinessInput {
  business_name: string;
  business_type: BusinessType;
  address: string;
  city: string;
  state: string;
  description: string;
  employee_count: number;
  serves_alcohol: boolean;
  outdoor_seating: boolean;
  square_footage?: number | null;
}

export interface CitationMeta {
  source_document: string;
  section: string;
  chunk_id: string;
  retrieval_score: number;
  excerpt: string;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export interface PermitRequirement {
  permit_name: string;
  issuing_authority: string;
  description: string;
  estimated_processing_days?: number | null;
  estimated_fee_usd?: number | null;
  citation: CitationMeta;
  confidence: ConfidenceLevel;
  form_template_id?: string | null;
}

export interface PermitAnalysisResponse {
  request_id: string;
  generated_at: string;
  business_name: string;
  jurisdiction: string;
  degraded_mode: boolean;
  permits: PermitRequirement[];
  warnings: string[];
}

export interface ApiErrorBody {
  error: string;
  detail: string;
  request_id?: string | null;
}

export const BUSINESS_TYPE_LABELS: Record<BusinessType, string> = {
  restaurant: "Restaurant / Cafe",
  retail: "Retail Store",
  home_based: "Home-Based Business",
  professional_services: "Professional Services",
  construction_contractor: "Construction / Contractor",
  food_truck: "Food Truck",
  salon_personal_care: "Salon / Personal Care",
  bar_nightlife: "Bar / Nightlife Venue",
  other: "Other",
};
