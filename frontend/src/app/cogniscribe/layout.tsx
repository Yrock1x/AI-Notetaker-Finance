import type { Metadata } from "next";
import "@/styles/cogniscribe.css";

export const metadata: Metadata = {
  title: "CogniScribe — Meeting intelligence | CogniSuite.ai",
  description:
    "A silent AI partner joins every call — Zoom, Meet, Teams, phone bridge. Diarized speakers, extracted metrics, flagged risks, searchable forever.",
};

export default function CogniScribeLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
