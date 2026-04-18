"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";
import Link from "next/link";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export const Navbar = () => {
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        start: "top -50",
        onUpdate: (self) => {
          if (self.progress > 0) {
            gsap.to(navRef.current, {
              backgroundColor: "rgba(242, 240, 233, 0.8)",
              backdropFilter: "blur(16px)",
              color: "#1A1A1A",
              border: "1px solid rgba(26,26,26,0.1)",
              duration: 0.3,
            });
          } else {
            gsap.to(navRef.current, {
              backgroundColor: "transparent",
              backdropFilter: "blur(0px)",
              color: "#F2F0E9",
              border: "1px solid transparent",
              duration: 0.3,
            });
          }
        },
      });
    });
    return () => ctx.revert();
  }, []);

  return (
    <div
      ref={navRef}
      className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex items-center justify-between px-6 py-3 rounded-[3rem] w-[90%] max-w-5xl transition-all border border-transparent text-[#F2F0E9]"
    >
      <div className="font-heading font-bold text-lg tracking-tight">Deal Companion</div>
      <div className="hidden md:flex items-center gap-8 font-subheading text-sm font-medium">
        <a href="#features" className="link-lift">Features</a>
        <a href="#philosophy" className="link-lift">Philosophy</a>
        <a href="#protocol" className="link-lift">Protocol</a>
      </div>
      <Link
        href="/login"
        className="magnetic-btn relative bg-[#CC5833] text-white px-6 py-2.5 rounded-[2rem] font-subheading text-sm font-semibold overflow-hidden group shadow-lg"
      >
        <span className="relative z-10 transition-colors">Log in</span>
        <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out z-0"></div>
      </Link>
    </div>
  );
};
