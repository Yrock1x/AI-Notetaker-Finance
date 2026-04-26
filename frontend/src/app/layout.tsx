import type { Metadata } from "next";
import { Providers } from "./providers";
import { ScribeThemeProvider } from "@/components/cogniscribe/theme-provider";
import "@/styles/globals.css";
import "@/styles/cogniscribe.css";

export const metadata: Metadata = {
  title: "CogniSuite.ai — The AI workspace for complex engagements",
  description:
    "Purpose-built for finance, legal, and advisory teams. A secure data room and a meeting intelligence engine — sharing one context, one audit trail, one source of truth.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="cogniscribe-root antialiased">
        <ScribeThemeProvider initialTheme="dark">
          <Providers>{children}</Providers>
        </ScribeThemeProvider>
      </body>
    </html>
  );
}
