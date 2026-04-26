"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export const Philosophy = () => {
  const sectionRef = useRef<HTMLElement>(null);
  const [phraseIndex, setPhraseIndex] = useState(0);
  const phrases1 = ["broad transcription.", "generic outputs.", "cookie cutter templates."];
  const phrases2 = ["deal-level intelligence.", "deliverable production.", "deal team collaboration."];

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % phrases1.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from(".split-word", {
        y: 50, opacity: 0, stagger: 0.05, duration: 1, ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 60%" },
      });
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  const sentence1Prefix = "Most AI tools focus on:".split(" ");
  const sentence2Prefix = "We focus on:".split(" ");

  return (
    <section ref={sectionRef} id="philosophy" className="relative py-40 px-6 flex items-center justify-center overflow-hidden bg-[#1A1A1A] text-[#F2F0E9] rounded-[3rem] mx-2 shadow-2xl">
      <div className="absolute inset-0 opacity-[0.15]">
        <img src="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&q=80&w=2000" className="w-full h-full object-cover grayscale mix-blend-overlay" />
      </div>
      <div className="relative z-10 max-w-6xl mx-auto text-center space-y-16">
        <h3 className="font-heading text-2xl md:text-3xl lg:text-4xl text-[#F2F0E9]/40 tracking-tight font-semibold flex flex-wrap justify-center items-center gap-x-2 md:gap-x-3 transition-all">
          {sentence1Prefix.map((w, i) => <span key={i} className="split-word inline-block">{w}</span>)}
          <span className="inline-block text-left text-white/90 ml-1">
            <span key={phraseIndex} className="block animate-slide-up-fade text-[#CC5833]">{phrases1[phraseIndex]}</span>
          </span>
        </h3>
        <h2 className="font-drama text-5xl md:text-7xl lg:text-8xl italic leading-tight flex flex-wrap justify-center items-center gap-x-3 md:gap-x-4">
          {sentence2Prefix.map((w, i) => <span key={`s2-${i}`} className="split-word inline-block">{w}</span>)}
          <span className="inline-block text-left text-[#CC5833] font-bold ml-1">
            <span key={phraseIndex} className="block animate-slide-up-fade">{phrases2[phraseIndex]}</span>
          </span>
        </h2>
      </div>
    </section>
  );
};
