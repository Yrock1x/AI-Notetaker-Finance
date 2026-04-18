"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";

export const Features = () => {
  return (
    <section id="features" className="py-32 px-6 md:px-12 xl:px-24">
      <div className="mb-20 max-w-2xl">
        <h2 className="font-heading text-4xl md:text-6xl font-bold text-[#2E4036] tracking-tight leading-tight">
          AI-Powered <br /> Deal Tools
        </h2>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <CardShuffler />
        <CardTypewriter />
        <CardScheduler />
      </div>
    </section>
  );
};

const CardShuffler = () => {
  const [stack, setStack] = useState([
    { id: 1, label: "// Financial Models", bg: "bg-[#2E4036]" },
    { id: 2, label: "// Pitch Decks", bg: "bg-[#CC5833]" },
    { id: 3, label: "// Deal Memos", bg: "bg-[#1A1A1A]" },
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      setStack((prev) => {
        const newArr = [...prev];
        const last = newArr.pop();
        if (last) newArr.unshift(last);
        return newArr;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white rounded-[2.5rem] p-8 shadow-sm border border-[#1A1A1A]/5 h-[420px] flex flex-col relative group overflow-hidden">
      <h3 className="font-heading font-bold text-xl text-[#2E4036] mb-2">Generate Deliverables</h3>
      <p className="font-subheading text-[#1A1A1A]/60 text-sm mb-12 max-w-[80%]">Instantly produce comprehensive financial models and presentations from meeting context.</p>
      <div className="relative flex-1 flex items-center justify-center w-full">
        {stack.map((item, i) => (
          <div
            key={item.id}
            className={`absolute w-[90%] h-[140px] rounded-[2rem] ${item.bg} text-[#F2F0E9] p-6 flex flex-col justify-end font-data text-xs shadow-[0_10px_30px_rgba(0,0,0,0.1)]`}
            style={{
              transition: "all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)",
              transform: `translateY(${i * -24}px) scale(${1 - i * 0.06})`,
              zIndex: 10 - i,
              opacity: 1 - i * 0.15,
            }}
          >
            <span className="opacity-80 font-medium">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const CardTypewriter = () => {
  const text = "> Joining meeting...\n> Live transcription active.\n> Summarizing deal points.\n> Ready for queries.";
  const [displayed, setDisplayed] = useState("");
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index < text.length) {
      const timeout = setTimeout(() => {
        setDisplayed((prev) => prev + text.charAt(index));
        setIndex(index + 1);
      }, 60);
      return () => clearTimeout(timeout);
    } else {
      const reset = setTimeout(() => {
        setDisplayed("");
        setIndex(0);
      }, 4000);
      return () => clearTimeout(reset);
    }
  }, [index, text]);

  return (
    <div className="bg-white rounded-[2.5rem] p-8 shadow-sm border border-[#1A1A1A]/5 h-[420px] flex flex-col relative">
      <h3 className="font-heading font-bold text-xl text-[#2E4036] mb-2">Live Notes & Q&A</h3>
      <p className="font-subheading text-[#1A1A1A]/60 text-sm mb-8 max-w-[80%]">Seamlessly takes live transcriptions and summaries. Ask it anything relating to the meeting.</p>
      <div className="flex-1 bg-[#1A1A1A] rounded-[2rem] p-6 overflow-hidden relative shadow-inner">
        <div className="flex items-center gap-2 mb-4 bg-white/5 inline-flex px-3 py-1.5 rounded-full border border-white/10">
          <div className="w-2 h-2 rounded-full bg-[#CC5833] animate-pulse"></div>
          <span className="font-data text-[10px] text-[#F2F0E9]/70 uppercase tracking-widest">Telemetry</span>
        </div>
        <div className="font-data text-[13px] text-[#F2F0E9]/90 whitespace-pre-line leading-loose">
          {displayed}<span className="inline-block w-2 bg-[#CC5833] h-4 ml-1 translate-y-1 animate-pulse"></span>
        </div>
      </div>
    </div>
  );
};

const CardScheduler = () => {
  const days = ["S", "M", "T", "W", "T", "F", "S"];
  const cursorRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const saveRef = useRef<HTMLDivElement>(null);
  const [activeDay, setActiveDay] = useState(-1);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ repeat: -1, repeatDelay: 1 });
      tl.set(cursorRef.current, { x: 50, y: 150, opacity: 0 });
      tl.to(cursorRef.current, { opacity: 1, duration: 0.2 });
      tl.to(cursorRef.current, { x: -28, y: -24, duration: 0.8, ease: "power2.inOut" });
      tl.to(cursorRef.current, { scale: 0.8, duration: 0.1 });
      tl.call(() => setActiveDay(3));
      tl.to(boxRef.current, { scale: 0.9, duration: 0.1 }, "<");
      tl.to(cursorRef.current, { scale: 1, duration: 0.1 });
      tl.to(boxRef.current, { scale: 1, duration: 0.1 }, "<");
      tl.to(cursorRef.current, { x: 0, y: 65, duration: 0.8, ease: "power2.inOut", delay: 0.2 });
      tl.to(cursorRef.current, { scale: 0.8, duration: 0.1 });
      tl.to(saveRef.current, { scale: 0.95, duration: 0.1 }, "<");
      tl.to(cursorRef.current, { scale: 1, duration: 0.1 });
      tl.to(saveRef.current, { scale: 1, duration: 0.1 }, "<");
      tl.to(saveRef.current, { backgroundColor: "#CC5833", color: "white", borderColor: "transparent", duration: 0.2 }, "<");
      tl.to(cursorRef.current, { opacity: 0, duration: 0.2, delay: 0.5 });
      tl.call(() => setActiveDay(-1));
      tl.to(saveRef.current, { backgroundColor: "transparent", color: "#1A1A1A", borderColor: "rgba(26,26,26,0.2)", duration: 0.2, clearProps: "all" }, "<");
    });
    return () => ctx.revert();
  }, []);

  return (
    <div className="bg-white rounded-[2.5rem] p-8 shadow-sm border border-[#1A1A1A]/5 h-[420px] flex flex-col relative">
      <h3 className="font-heading font-bold text-xl text-[#2E4036] mb-2">Collaborative Deal Rooms</h3>
      <p className="font-subheading text-[#1A1A1A]/60 text-sm mb-8 max-w-[80%]">Segmented by deal. Your whole deal team can work collaboratively inside dedicated workspaces.</p>
      <div className="flex-1 w-full bg-[#F2F0E9]/50 rounded-[2rem] border border-[#1A1A1A]/5 p-6 flex flex-col items-center justify-center relative overflow-hidden">
        <div className="flex gap-2 mb-10 w-full justify-center">
          {days.map((d, i) => (
            <div
              key={i}
              ref={i === 3 ? boxRef : null}
              className={`w-9 h-9 flex items-center justify-center rounded-xl font-data text-xs transition-colors duration-300 font-medium ${activeDay === i ? "bg-[#CC5833] text-white shadow-lg" : "bg-white text-[#1A1A1A] border border-[#1A1A1A]/10"}`}
            >
              {d}
            </div>
          ))}
        </div>
        <div ref={saveRef} className="px-6 py-2.5 bg-transparent text-[#1A1A1A] font-subheading font-medium text-sm rounded-full border border-[#1A1A1A]/20 transition-all">
          Sync to Pipeline
        </div>
        <div ref={cursorRef} className="absolute z-10 text-[#2E4036]" style={{ pointerEvents: "none" }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" className="drop-shadow-xl" xmlns="http://www.w3.org/2000/svg">
            <path d="M5.5 3.21V20.8c0 .45.54.67.85.35l4.86-4.86h7.6c.45 0 .81-.36.81-.81V3.21c0-.45-.36-.81-.81-.81H6.31c-.45 0-.81.36-.81.81z" />
          </svg>
        </div>
      </div>
    </div>
  );
};
