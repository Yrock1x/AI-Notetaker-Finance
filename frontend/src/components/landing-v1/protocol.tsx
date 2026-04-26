"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export const Protocol = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>(".protocol-card");
      cards.forEach((card, i) => {
        const inner = card.querySelector(".protocol-inner");
        if (!inner) return;

        ScrollTrigger.create({
          trigger: card,
          start: "top top",
          pin: true,
          pinSpacing: false,
          endTrigger: ".protocol-end",
          end: "bottom bottom",
        });

        if (i < cards.length - 1) {
          gsap.to(inner, {
            scale: 0.9,
            opacity: 0.5,
            filter: "blur(20px)",
            ease: "none",
            scrollTrigger: {
              trigger: cards[i + 1],
              start: "top bottom",
              end: "top top",
              scrub: true,
            },
          });
        }
      });
    }, containerRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} id="protocol" className="relative bg-[#F2F0E9] pt-32 pb-0 z-20">
      <div className="text-center mb-16 px-6">
        <h2 className="font-heading text-4xl md:text-6xl font-bold text-[#2E4036] tracking-tight">The Deal Protocol</h2>
      </div>

      <ProtocolCard num="01/03" title="Meeting Ingestion" desc="The AI joins your calls, taking live notes, full transcriptions, and executive summaries." Graphic={ProtoGraphic1} color="bg-[#2E4036]" textColor="text-[#F2F0E9]" />
      <ProtocolCard num="02/03" title="Deal-Team Collaboration" desc="Information is dynamically routed into deal-specific segments for your team to work collaboratively." Graphic={ProtoGraphic2} color="bg-white border-2 border-[#1A1A1A]/10" textColor="text-[#1A1A1A]" />
      <ProtocolCard num="03/03" title="Deliverable Production" desc="Generate structured outputs like financial models, PowerPoints, and presentations in seconds." Graphic={ProtoGraphic3} color="bg-[#CC5833]" textColor="text-white" />
      <div className="protocol-end h-[60vh] pointer-events-none md:h-[100vh]"></div>
    </section>
  );
};

const ProtocolCard = ({ num, title, desc, Graphic, color, textColor }: { num: string; title: string; desc: string; Graphic: React.ComponentType; color: string; textColor: string }) => {
  return (
    <div className="protocol-card h-[100dvh] w-full flex items-center justify-center sticky top-0 px-4 md:px-12">
      <div className={`protocol-inner w-full max-w-6xl h-[75vh] md:h-[80vh] rounded-[3rem] ${color} ${textColor} p-8 md:p-20 flex flex-col md:flex-row items-center justify-between gap-12 shadow-[0_30px_60px_rgba(0,0,0,0.1)]`}>
        <div className="flex-1 space-y-8 w-full">
          <div className="font-data text-sm opacity-60 flex items-center gap-4 uppercase tracking-widest font-semibold">
            <span className="w-12 h-px bg-current"></span>
            {num}
          </div>
          <h3 className="font-heading text-4xl md:text-6xl font-bold leading-tight tracking-tight">{title}</h3>
          <p className="font-subheading text-lg md:text-xl opacity-80 max-w-md leading-relaxed">{desc}</p>
        </div>
        <div className="flex-1 w-full h-full relative flex items-center justify-center">
          <Graphic />
        </div>
      </div>
    </div>
  );
};

const ProtoGraphic1 = () => (
  <div className="w-48 h-48 md:w-80 md:h-80 relative animate-[spin_25s_linear_infinite]">
    <svg viewBox="0 0 100 100" className="w-full h-full stroke-current fill-none overflow-visible" strokeWidth="0.5">
      <circle cx="50" cy="50" r="45" className="opacity-20" />
      <circle cx="50" cy="50" r="30" className="opacity-40" strokeWidth="1" />
      <circle cx="50" cy="50" r="15" className="opacity-80" strokeWidth="2" />
      <rect x="25" y="25" width="50" height="50" className="animate-[spin_12s_linear_infinite] origin-center opacity-30" />
      <rect x="35" y="35" width="30" height="30" className="animate-[spin_8s_linear_infinite_reverse] origin-center opacity-60" strokeWidth="1" />
    </svg>
  </div>
);

const ProtoGraphic2 = () => (
  <div className="w-48 h-48 md:w-80 md:h-80 relative bg-black/5 rounded-[2rem] overflow-hidden flex items-center justify-center border border-black/10">
    <div className="grid grid-cols-6 gap-3 opacity-30">
      {Array.from({ length: 36 }).map((_, i) => <div key={i} className={`w-2 h-2 md:w-3 md:h-3 rounded-full ${i % 7 === 0 ? "bg-[#CC5833]" : "bg-current"}`}></div>)}
    </div>
    <div className="absolute top-0 w-full h-[2px] bg-[#CC5833] animate-[bounce_4s_infinite] shadow-[0_0_20px_#CC5833]"></div>
  </div>
);

const ProtoGraphic3 = () => (
  <div className="w-full h-40 flex items-center justify-center opacity-90">
    <svg viewBox="0 0 200 50" className="w-full h-full stroke-current fill-none stroke-2">
      <path strokeDasharray="300" strokeDashoffset="300" className="animate-[dash_4s_linear_infinite]" d="M0,25 L30,25 L40,10 L50,40 L60,25 L100,25 L110,5 L120,45 L130,25 L200,25" />
      <path strokeDasharray="300" strokeDashoffset="300" className="animate-[dash_4s_linear_infinite] opacity-30" style={{ animationDelay: "1s" }} d="M0,25 L30,25 L40,10 L50,40 L60,25 L100,25 L110,5 L120,45 L130,25 L200,25" />
    </svg>
  </div>
);
