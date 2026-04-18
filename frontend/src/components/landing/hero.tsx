"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import Link from "next/link";

export const Hero = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".hero-elem", { y: 40, opacity: 0, stagger: 0.08, duration: 1.2, ease: "power3.out", delay: 0.2 });
    }, containerRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="relative h-[100dvh] w-full flex flex-col justify-end p-8 md:p-16 rounded-b-[3rem] overflow-hidden">
      <div className="absolute inset-0 z-0">
        <img src="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&q=80&w=2000" alt="Corporate skyline" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#1A1A1A] via-[#1A1A1A]/60 to-transparent"></div>
      </div>
      <div className="relative z-10 w-full md:w-2/3 lg:w-1/2 text-[#F2F0E9] mb-[5vh]">
        <h1 className="hero-elem font-heading text-5xl md:text-7xl lg:text-[5.5rem] font-extrabold leading-[0.9] mb-2 uppercase tracking-tighter">
          Intelligence is the
        </h1>
        <h2 className="hero-elem font-drama text-6xl md:text-8xl lg:text-[7rem] italic leading-none text-[#CC5833] mb-8 pr-4">
          Advantage.
        </h2>
        <p className="hero-elem font-subheading text-lg md:text-xl max-w-md mb-10 text-[#F2F0E9]/80 font-medium leading-relaxed">
          Deal Companion joins your meetings to take live transcriptions, notes, and summaries. Ask anything, collaborate with your deal team, and produce deliverables instantly.
        </p>
        <div className="hero-elem flex flex-wrap gap-4">
          <Link href="/login" className="magnetic-btn relative bg-[#CC5833] text-white px-8 py-4 rounded-[2rem] font-subheading text-sm font-semibold overflow-hidden group shadow-xl">
            <span className="relative z-10">Get Started</span>
            <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          </Link>
          <a href="#features" className="magnetic-btn relative bg-white/10 backdrop-blur-md border border-white/20 text-white px-8 py-4 rounded-[2rem] font-subheading text-sm font-semibold overflow-hidden group hover:border-transparent transition-colors shadow-xl">
            <span className="relative z-10 transition-colors">Learn More</span>
            <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          </a>
        </div>
      </div>
    </section>
  );
};
