"use client";

import { Check } from "lucide-react";
import Link from "next/link";

export const Pricing = () => {
  return (
    <section className="py-20 md:py-40 px-6 max-w-7xl mx-auto relative z-30 bg-[#F2F0E9] rounded-t-[4rem] -mt-10">
      <div className="text-center mb-20 max-w-2xl mx-auto">
        <h2 className="font-heading text-4xl md:text-6xl font-bold text-[#1A1A1A] mb-6 tracking-tight">Select your protocol.</h2>
        <p className="font-subheading text-[#1A1A1A]/70 text-lg">Secure, encrypted, multi-tenant intelligence for every deal room.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
        <PricingCard title="Essential" price="Free" features={["5h transcription limit", "Basic entity extraction", "Shared workspace", "Standard support"]} />
        <PricingCard title="Performance" price="$99/mo" features={["Unlimited transcription", "Deal-level RBAC", "CRM deep integration", "Priority 24/7 Support"]} highlight />
        <PricingCard title="Enterprise" price="Custom" features={["On-prem deployment", "Custom Entity Models", "Dedicated Success Manager", "SLA guarantees"]} />
      </div>
    </section>
  );
};

const PricingCard = ({ title, price, features, highlight }: { title: string; price: string; features: string[]; highlight?: boolean }) => (
  <div className={`rounded-[3rem] p-10 font-subheading flex flex-col h-full min-h-[500px] ${highlight ? "bg-[#2E4036] text-[#F2F0E9] md:scale-105 shadow-2xl relative z-10" : "bg-white text-[#1A1A1A] border border-[#1A1A1A]/10 shadow-sm"}`}>
    <div className="font-data text-xs uppercase tracking-widest mb-10 opacity-70 font-semibold">{title}</div>
    <div className="font-heading text-5xl font-bold mb-12">{price}</div>
    <ul className="space-y-4 mb-12 flex-1">
      {features.map((f, i) => (
        <li key={i} className="flex items-center gap-4 text-sm font-medium opacity-90">
          <Check className={`w-5 h-5 flex-shrink-0 ${highlight ? "text-[#CC5833]" : "text-[#2E4036]"}`} />
          <span>{f}</span>
        </li>
      ))}
    </ul>
    <Link href="/login" className={`magnetic-btn block w-full py-5 rounded-[2rem] font-bold text-sm transition-all overflow-hidden relative group text-center ${highlight ? "bg-[#CC5833] text-white" : "bg-[#F2F0E9] text-[#1A1A1A] hover:bg-[#1A1A1A] hover:text-white border border-[#1A1A1A]/10"}`}>
      <span className="relative z-10">Get Started</span>
      {highlight && <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform"></div>}
    </Link>
  </div>
);
