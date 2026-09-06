import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CivicMint — AI Permit Navigator",
  description:
    "AI-driven local compliance and permit navigator for small businesses, with citation-backed municipal code guidance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
