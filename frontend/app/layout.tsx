import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Equity Research Agent",
  description:
    "Multi-agent equity research: Researcher → Analyst → Writer over SEC filings, fundamentals, and news.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
