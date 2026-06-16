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

// Applies the saved theme (matching ScribeThemeProvider's "cogni-theme" key)
// synchronously before first paint, so the page doesn't render dark and then
// flip to the stored light theme after hydration.
const themeInitScript = `(function(){try{var t=localStorage.getItem('cogni-theme');if(t!=='dark'&&t!=='light')t='dark';var r=document.documentElement;if(t==='dark')r.classList.add('dark');else r.classList.remove('dark');document.body.style.backgroundColor=t==='dark'?'#0a0a0a':'#fafafa';document.body.style.color=t==='dark'?'#ffffff':'#0a0a0a';}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="cogniscribe-root antialiased">
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <ScribeThemeProvider initialTheme="dark">
          <Providers>{children}</Providers>
        </ScribeThemeProvider>
      </body>
    </html>
  );
}
