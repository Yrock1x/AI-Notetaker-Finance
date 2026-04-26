"use client";

import dynamic from "next/dynamic";
import { Navbar } from "@/components/landing-v1/navbar";
import { Hero } from "@/components/landing-v1/hero";
import "@/styles/landing-v2.css";

// Lazy-load below-the-fold sections to reduce initial bundle size
const Features = dynamic(() => import("@/components/landing-v1/features").then((m) => ({ default: m.Features })), {
  loading: () => <SectionSkeleton />,
});
const Philosophy = dynamic(() => import("@/components/landing-v1/philosophy").then((m) => ({ default: m.Philosophy })), {
  loading: () => <SectionSkeleton />,
});
const Protocol = dynamic(() => import("@/components/landing-v1/protocol").then((m) => ({ default: m.Protocol })), {
  loading: () => <SectionSkeleton />,
});
const Pricing = dynamic(() => import("@/components/landing-v1/pricing").then((m) => ({ default: m.Pricing })), {
  loading: () => <SectionSkeleton />,
});
const Footer = dynamic(() => import("@/components/landing-v1/footer").then((m) => ({ default: m.Footer })), {
  loading: () => <div className="h-64" />,
});

function SectionSkeleton() {
  return (
    <div className="py-32 px-6 md:px-12 xl:px-24">
      <div className="animate-pulse space-y-6 max-w-2xl">
        <div className="h-12 bg-[#1A1A1A]/5 rounded-2xl w-2/3" />
        <div className="h-6 bg-[#1A1A1A]/5 rounded-xl w-1/2" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-16">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse bg-[#1A1A1A]/5 rounded-[2.5rem] h-[420px]" />
        ))}
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="bg-[#F2F0E9] text-[#1A1A1A] font-subheading min-h-screen overflow-x-hidden selection:bg-[#CC5833] selection:text-white relative antialiased">
      <div className="noise-bg pointer-events-none fixed inset-0 z-[999] opacity-5"></div>

      <Navbar />
      <Hero />
      <Features />
      <Philosophy />
      <Protocol />
      <Pricing />
      <Footer />
    </div>
  );
}
