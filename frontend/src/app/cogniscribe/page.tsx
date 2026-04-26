"use client";

import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { ScribeNav } from "@/components/cogniscribe/nav";
import { ScribeFooter } from "@/components/cogniscribe/footer";
import {
  ScribeHero,
  ScribePipeline,
  ScribeExtraction,
  ScribeLibrary,
  ScribeIntegrations,
  ScribeCrossProduct,
  ScribeCTA,
} from "@/components/cogniscribe/sections";

export default function CogniScribePage() {
  const { isDark, aiDemosPlaying } = useScribeTheme();
  return (
    <div
      className={`theme-root min-h-screen ${aiDemosPlaying ? "" : "paused"} ${
        isDark ? "bg-[#0a0a0a] text-white" : "bg-[#fafafa] text-[#0a0a0a]"
      }`}
    >
      <ScribeNav currentProduct="mic" />
      <ScribeHero />
      <ScribePipeline />
      <ScribeExtraction />
      <ScribeLibrary />
      <ScribeIntegrations />
      <ScribeCrossProduct />
      <ScribeCTA />
      <ScribeFooter />
    </div>
  );
}
