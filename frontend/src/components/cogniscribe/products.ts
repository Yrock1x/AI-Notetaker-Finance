import type { ComponentType } from "react";
import { I } from "./icons";

export type ProductKey = "vdr" | "mic";

export type ProductDef = {
  key: ProductKey;
  name: string;
  tagline: string;
  href: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  text: { dark: string; light: string };
  bg: { dark: string; light: string };
  border: { dark: string; light: string };
  dotCls: string;
};

export const PRODUCTS: Record<ProductKey, ProductDef> = {
  vdr: {
    key: "vdr",
    name: "CogniVault",
    tagline: "AI-native data room",
    href: "/cognivault",
    icon: I.Shield,
    text: { dark: "text-emerald-300", light: "text-emerald-700" },
    bg: { dark: "bg-emerald-500/10", light: "bg-emerald-50" },
    border: { dark: "border-emerald-500/25", light: "border-emerald-200/70" },
    dotCls: "bg-emerald-400",
  },
  mic: {
    key: "mic",
    name: "CogniScribe",
    tagline: "Meeting intelligence",
    href: "/cogniscribe",
    icon: I.Mic,
    text: { dark: "text-amber-300", light: "text-amber-700" },
    bg: { dark: "bg-amber-500/10", light: "bg-amber-50" },
    border: { dark: "border-amber-500/25", light: "border-amber-200/70" },
    dotCls: "bg-amber-400",
  },
};

export const MIC_ACCENT = "245 158 11"; // amber-500
