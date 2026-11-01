import type { Metadata } from "next";
import { Bricolage_Grotesque, Instrument_Sans, JetBrains_Mono } from "next/font/google";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

// Fonts (1 Nov 2026 redesign): a characterful grotesque for headings, a clean humanist sans for text, a monospace for numbers.
const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"] });
const body = Instrument_Sans({ variable: "--font-body", subsets: ["latin"] });
const data = JetBrains_Mono({ variable: "--font-data", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Spillover Studio · Influencer-Brand Matching",
  description: "Influencer recommendation with graph spillover, cross-platform evidence and honest uncertainty",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${data.variable} dark h-full antialiased`}>
      <body className="min-h-full">
        <Sidebar />
        <div className="flex min-h-screen flex-col lg:pl-64">{children}</div>
      </body>
    </html>
  );
}
