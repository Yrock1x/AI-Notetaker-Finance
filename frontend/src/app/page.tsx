"use client";

import React, { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";
import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import "../styles/landing-v2.css";

// Ensure GSAP registers on client side
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// --------------------------------------------------------------------------
// SHARED COMPONENTS
// --------------------------------------------------------------------------

const Navbar = () => {
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ctx = gsap.context(() => {
      ScrollTrigger.create({
        start: "top -50",
        onUpdate: (self) => {
          if (self.progress > 0) {
            gsap.to(navRef.current, {
              backgroundColor: "rgba(242, 240, 233, 0.8)",
              backdropFilter: "blur(16px)",
              color: "#1A1A1A",
              border: "1px solid rgba(26,26,26,0.1)",
              duration: 0.3
            });
          } else {
            gsap.to(navRef.current, {
              backgroundColor: "transparent",
              backdropFilter: "blur(0px)",
              color: "#F2F0E9",
              border: "1px solid transparent",
              duration: 0.3
            });
          }
        }
      });
    });
    return () => ctx.revert();
  }, []);

  return (
    <div ref={navRef} className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex items-center justify-between px-6 py-3 rounded-[3rem] w-[90%] max-w-5xl transition-all border border-transparent text-[#F2F0E9]">
      <div className="font-heading font-bold text-lg tracking-tight">Deal Companion</div>
      <div className="hidden md:flex items-center gap-8 font-subheading text-sm font-medium">
        <a href="#features" className="link-lift">Features</a>
        <a href="#philosophy" className="link-lift">Philosophy</a>
        <a href="#protocol" className="link-lift">Protocol</a>
      </div>
      <Link href="/login" className="magnetic-btn relative bg-[#CC5833] text-white px-6 py-2.5 rounded-[2rem] font-subheading text-sm font-semibold overflow-hidden group shadow-lg">
        <span className="relative z-10 transition-colors">Log in</span>
        <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out z-0"></div>
      </Link>
    </div>
  );
};

// --------------------------------------------------------------------------
// HERO
// --------------------------------------------------------------------------

const Hero = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ctx = gsap.context(() => {
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
            <span className="relative z-10">Sign up</span>
            <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          </Link>
          <button className="magnetic-btn relative bg-white/10 backdrop-blur-md border border-white/20 text-white px-8 py-4 rounded-[2rem] font-subheading text-sm font-semibold overflow-hidden group hover:border-transparent transition-colors shadow-xl">
            <span className="relative z-10 transition-colors">Book a demo</span>
            <div className="absolute inset-0 bg-[#2E4036] translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          </button>
        </div>
      </div>
    </section>
  );
};

// --------------------------------------------------------------------------
// FEATURES - Artifacts
// --------------------------------------------------------------------------

const Features = () => {
  return (
    <section id="features" className="py-32 px-6 md:px-12 xl:px-24">
      <div className="mb-20 max-w-2xl">
        <h2 className="font-heading text-4xl md:text-6xl font-bold text-[#2E4036] tracking-tight leading-tight">
          Interactive <br /> Functional Artifacts
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
    { id: 3, label: "// Deal Memos", bg: "bg-[#1A1A1A]" }
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      setStack(prev => {
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
              transition: 'all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)',
              transform: `translateY(${i * -24}px) scale(${1 - i * 0.06})`,
              zIndex: 10 - i,
              opacity: 1 - i * 0.15
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
        setDisplayed(prev => prev + text.charAt(index));
        setIndex(index + 1);
      }, 60);
      return () => clearTimeout(timeout);
    } else {
      const reset = setTimeout(() => { setDisplayed(""); setIndex(0); }, 4000);
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
  const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const cursorRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const saveRef = useRef<HTMLDivElement>(null);
  const [activeDay, setActiveDay] = useState(-1);

  useEffect(() => {
    let ctx = gsap.context(() => {
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
              className={`w-9 h-9 flex items-center justify-center rounded-xl font-data text-xs transition-colors duration-300 font-medium ${activeDay === i ? 'bg-[#CC5833] text-white shadow-lg' : 'bg-white text-[#1A1A1A] border border-[#1A1A1A]/10'}`}
            >
              {d}
            </div>
          ))}
        </div>

        <div ref={saveRef} className="px-6 py-2.5 bg-transparent text-[#1A1A1A] font-subheading font-medium text-sm rounded-full border border-[#1A1A1A]/20 transition-all">
          Sync to Pipeline
        </div>

        <div ref={cursorRef} className="absolute z-10 text-[#2E4036]" style={{ pointerEvents: 'none' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" className="drop-shadow-xl" xmlns="http://www.w3.org/2000/svg">
            <path d="M5.5 3.21V20.8c0 .45.54.67.85.35l4.86-4.86h7.6c.45 0 .81-.36.81-.81V3.21c0-.45-.36-.81-.81-.81H6.31c-.45 0-.81.36-.81.81z" />
          </svg>
        </div>
      </div>
    </div>
  );
};

// --------------------------------------------------------------------------
// PHILOSOPHY
// --------------------------------------------------------------------------

const Philosophy = () => {
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
    let ctx = gsap.context(() => {
      gsap.from(".split-word", {
        y: 50, opacity: 0, stagger: 0.05, duration: 1, ease: "power3.out",
        scrollTrigger: { trigger: sectionRef.current, start: "top 60%" }
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

// --------------------------------------------------------------------------
// PROTOCOL
// --------------------------------------------------------------------------

const Protocol = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>('.protocol-card');
      cards.forEach((card, i) => {
        const inner = card.querySelector('.protocol-inner');
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
            }
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

      <ProtocolCard
        num="01/03"
        title="Meeting Ingestion"
        desc="The AI joins your calls, taking live notes, full transcriptions, and executive summaries."
        Graphic={ProtoGraphic1}
        color="bg-[#2E4036]"
        textColor="text-[#F2F0E9]"
      />
      <ProtocolCard
        num="02/03"
        title="Deal-Team Collaboration"
        desc="Information is dynamically routed into deal-specific segments for your team to work collaboratively."
        Graphic={ProtoGraphic2}
        color="bg-white border-2 border-[#1A1A1A]/10"
        textColor="text-[#1A1A1A]"
      />
      <ProtocolCard
        num="03/03"
        title="Deliverable Production"
        desc="Generate structured outputs like financial models, PowerPoints, and presentations in seconds."
        Graphic={ProtoGraphic3}
        color="bg-[#CC5833]"
        textColor="text-white"
      />
      {/* The spacer that allows the last card to scroll out */}
      <div className="protocol-end h-[60vh] pointer-events-none md:h-[100vh]"></div>
    </section>
  );
};

const ProtocolCard = ({ num, title, desc, Graphic, color, textColor }: any) => {
  return (
    <div className={`protocol-card h-[100dvh] w-full flex items-center justify-center sticky top-0 px-4 md:px-12`}>
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

const ProtoGraphic2 = () => {
  return (
    <div className="w-48 h-48 md:w-80 md:h-80 relative bg-black/5 rounded-[2rem] overflow-hidden flex items-center justify-center border border-black/10">
      <div className="grid grid-cols-6 gap-3 opacity-30">
        {Array.from({ length: 36 }).map((_, i) => <div key={i} className={`w-2 h-2 md:w-3 md:h-3 rounded-full ${i % 7 === 0 ? 'bg-[#CC5833]' : 'bg-current'}`}></div>)}
      </div>
      <div className="absolute top-0 w-full h-[2px] bg-[#CC5833] animate-[bounce_4s_infinite] shadow-[0_0_20px_#CC5833]"></div>
    </div>
  );
};

const ProtoGraphic3 = () => (
  <div className="w-full h-40 flex items-center justify-center opacity-90">
    <svg viewBox="0 0 200 50" className="w-full h-full stroke-current fill-none stroke-2">
      <path strokeDasharray="300" strokeDashoffset="300" className="animate-[dash_4s_linear_infinite]"
        d="M0,25 L30,25 L40,10 L50,40 L60,25 L100,25 L110,5 L120,45 L130,25 L200,25" />
      <path strokeDasharray="300" strokeDashoffset="300" className="animate-[dash_4s_linear_infinite] opacity-30" style={{ animationDelay: '1s' }}
        d="M0,25 L30,25 L40,10 L50,40 L60,25 L100,25 L110,5 L120,45 L130,25 L200,25" />
    </svg>
  </div>
);

// --------------------------------------------------------------------------
// PRICING / GET STARTED
// --------------------------------------------------------------------------

const Pricing = () => {
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

const PricingCard = ({ title, price, features, highlight }: any) => (
  <div className={`rounded-[3rem] p-10 font-subheading flex flex-col h-full min-h-[500px] ${highlight ? 'bg-[#2E4036] text-[#F2F0E9] md:scale-105 shadow-2xl relative z-10' : 'bg-white text-[#1A1A1A] border border-[#1A1A1A]/10 shadow-sm'}`}>
    <div className="font-data text-xs uppercase tracking-widest mb-10 opacity-70 font-semibold">{title}</div>
    <div className="font-heading text-5xl font-bold mb-12">{price}</div>
    <ul className="space-y-4 mb-12 flex-1">
      {features.map((f: string, i: number) => (
        <li key={i} className="flex items-center gap-4 text-sm font-medium opacity-90">
          <Check className={`w-5 h-5 flex-shrink-0 ${highlight ? 'text-[#CC5833]' : 'text-[#2E4036]'}`} />
          <span>{f}</span>
        </li>
      ))}
    </ul>
    <button className={`magnetic-btn w-full py-5 rounded-[2rem] font-bold text-sm transition-all overflow-hidden relative group ${highlight ? 'bg-[#CC5833] text-white' : 'bg-[#F2F0E9] text-[#1A1A1A] hover:bg-[#1A1A1A] hover:text-white border border-[#1A1A1A]/10'}`}>
      <span className="relative z-10">Choose Protocol</span>
      {highlight && <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform"></div>}
    </button>
  </div>
);

// --------------------------------------------------------------------------
// FOOTER
// --------------------------------------------------------------------------

const Footer = () => (
  <footer className="bg-[#1A1A1A] pt-24 pb-12 px-8 md:px-16 rounded-t-[4rem] text-[#F2F0E9] font-subheading relative z-40">
    <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-16 mb-24">
      <div className="md:col-span-2">
        <div className="font-heading text-3xl font-bold mb-6 tracking-tight text-white">Deal Companion</div>
        <p className="text-white/50 max-w-md mb-10 text-lg leading-relaxed">
          The ultimate digital instrument for investment banking, private equity, and venture capital.
        </p>
        <div className="flex items-center gap-3 bg-white/5 inline-flex px-5 py-2.5 rounded-full border border-white/10 shadow-inner">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-[pulse_2s_infinite]"></div>
          <span className="font-data text-xs uppercase tracking-[0.2em] text-white/70 font-medium">System Operational</span>
        </div>
      </div>
      <div>
        <div className="font-data text-xs uppercase tracking-widest mb-8 opacity-40">Platform</div>
        <ul className="space-y-4 text-sm text-white/70 font-medium">
          <li><a href="#" className="hover:text-white transition-colors">Features</a></li>
          <li><a href="#" className="hover:text-white transition-colors">Integrations</a></li>
          <li><a href="#" className="hover:text-white transition-colors">Security Architecture</a></li>
        </ul>
      </div>
      <div>
        <div className="font-data text-xs uppercase tracking-widest mb-8 opacity-40">Company</div>
        <ul className="space-y-4 text-sm text-white/70 font-medium">
          <li><a href="#" className="hover:text-white transition-colors">Manifesto</a></li>
          <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
          <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
        </ul>
      </div>
    </div>
    <div className="max-w-7xl mx-auto border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center text-xs text-white/30 font-data tracking-wider gap-4">
      <div>© 2026 DEAL COMPANION.</div>
      <div>GENERATION 01.</div>
    </div>
  </footer>
);

// --------------------------------------------------------------------------
// MAIN EXTERNAL EXPORT
// --------------------------------------------------------------------------

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
