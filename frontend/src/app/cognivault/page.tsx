"use client";

import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { ScribeNav } from "@/components/cogniscribe/nav";
import { ScribeFooter } from "@/components/cogniscribe/footer";
import {
  VaultHero,
  HowItWorks,
  VaultChat,
  VaultFeatures,
  VaultUseCases,
  VaultCrossProduct,
  VaultCTA,
} from "@/components/cogniscribe/vault-sections";

export default function CogniVaultPage() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  return (
    <div
      className={`theme-root min-h-screen ${aiDemosPlaying ? "" : "paused"} ${
        isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-[#0a0a0a]"
      }`}
    >
      <ScribeNav currentProduct="vdr" />
      <VaultHero />
      <HowItWorks />
      <VaultChat />
      <VaultFeatures />
      <VaultUseCases />
      <VaultCrossProduct />
      <VaultCTA />
      <ScribeFooter />
    </div>
  );
}
