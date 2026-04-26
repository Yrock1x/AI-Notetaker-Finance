import type { Metadata } from "next";
import "@/styles/cogniscribe.css";

export const metadata: Metadata = {
  title: "CogniVault — AI-native data room | CogniSuite.ai",
  description:
    "Upload contracts, financials, memos, transcripts. CogniVault indexes them the moment they arrive, auto-matches to your request list, and answers questions with page citations.",
};

export default function CogniVaultLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
