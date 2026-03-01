"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import "../styles/landing.css";

const FEATURES = [
  {
    icon: "M12 18.75a6.75 6.75 0 1 1 0-13.5 6.75 6.75 0 0 1 0 13.5ZM12 2.25v1.5M12 20.25v1.5M4.22 4.22l1.06 1.06M18.72 18.72l1.06 1.06M2.25 12h1.5M20.25 12h1.5M4.22 19.78l1.06-1.06M18.72 5.28l1.06-1.06",
    title: "AI Transcription",
    description:
      "Automatically transcribe meetings with speaker diarization powered by Deepgram, capturing every detail with financial-grade accuracy.",
  },
  {
    icon: "M3.75 6.75h16.5M3.75 12h16.5M12 17.25h8.25",
    title: "Deal Intelligence",
    description:
      "Extract key terms, action items, and risk signals from every conversation. AI-powered analysis tailored for IB, PE, and VC workflows.",
  },
  {
    icon: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 0 1-.825-.242m9.345-8.334a2.126 2.126 0 0 0-.476-.095 48.64 48.64 0 0 0-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0 0 11.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
    title: "Q&A Over Meetings",
    description:
      "Ask questions across your entire meeting history. Get instant, sourced answers powered by Claude with full context from your deal pipeline.",
  },
  {
    icon: "M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z",
    title: "Enterprise Security",
    description:
      "SOC 2 ready architecture with row-level security, role-based access control, and full audit logging. Your deal data stays protected.",
  },
  {
    icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
    title: "Deal Analytics",
    description:
      "Track deal progress, meeting cadence, and team engagement across your entire portfolio with real-time dashboards and insights.",
  },
  {
    icon: "M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244",
    title: "Integrations",
    description:
      "Connect with Zoom, Microsoft Teams, Slack, and your CRM. Seamless workflow integration that fits how your team already works.",
  },
];

const STEPS = [
  {
    num: "01",
    title: "Connect your meetings",
    description: "Link Zoom, Teams, or upload recordings directly. DealWise joins automatically.",
  },
  {
    num: "02",
    title: "AI processes everything",
    description: "Transcription, speaker identification, and intelligent analysis happen in minutes.",
  },
  {
    num: "03",
    title: "Get deal insights",
    description: "Key terms, action items, risk signals, and searchable Q&A across all your meetings.",
  },
];

function FeatureIcon({ path }: { path: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className="lp-feature-icon"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

export default function HomePage() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="landing-page">
      {/* NAV */}
      <nav className={`lp-nav${scrolled ? " lp-nav--scrolled" : ""}`}>
        <div className="lp-nav-inner">
          <Link href="/" className="lp-logo">
            <span className="lp-logo-icon">D</span>
            <span>DealWise AI</span>
          </Link>

          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
          </div>

          <div className="lp-nav-actions">
            <Link href="/login" className="lp-btn lp-btn--ghost">
              Log In
            </Link>
            <Link href="/login" className="lp-btn lp-btn--primary">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-hero-glow" />
        <div className="lp-hero-content">
          <div className="lp-badge">AI-Powered Meeting Intelligence</div>
          <h1 className="lp-hero-title">
            Turn every deal meeting
            <br />
            into a <span className="lp-gradient-text">competitive edge</span>
          </h1>
          <p className="lp-hero-sub">
            DealWise AI automatically transcribes, analyzes, and extracts
            actionable intelligence from your investment meetings — so your
            team never misses a detail.
          </p>
          <div className="lp-hero-cta">
            <Link href="/login" className="lp-btn lp-btn--primary lp-btn--lg">
              Start Free Trial
            </Link>
            <a href="#how-it-works" className="lp-btn lp-btn--outline lp-btn--lg">
              See How It Works
            </a>
          </div>
          <p className="lp-hero-note">No credit card required. Free for up to 10 meetings/month.</p>
        </div>

        {/* Dashboard preview */}
        <div className="lp-hero-visual">
          <div className="lp-dash-preview">
            <div className="lp-dash-topbar">
              <div className="lp-dash-dots">
                <span /><span /><span />
              </div>
              <span className="lp-dash-url">app.dealwise.ai/dashboard</span>
            </div>
            <div className="lp-dash-body">
              <div className="lp-dash-sidebar">
                <div className="lp-dash-sidebar-item lp-dash-sidebar-item--active" />
                <div className="lp-dash-sidebar-item" />
                <div className="lp-dash-sidebar-item" />
                <div className="lp-dash-sidebar-item" />
              </div>
              <div className="lp-dash-main">
                <div className="lp-dash-card lp-dash-card--wide">
                  <div className="lp-dash-card-title" />
                  <div className="lp-dash-bars">
                    <div className="lp-dash-bar" style={{ width: "85%" }} />
                    <div className="lp-dash-bar" style={{ width: "62%" }} />
                    <div className="lp-dash-bar" style={{ width: "94%" }} />
                    <div className="lp-dash-bar" style={{ width: "45%" }} />
                  </div>
                </div>
                <div className="lp-dash-grid">
                  <div className="lp-dash-card">
                    <div className="lp-dash-card-title" />
                    <div className="lp-dash-metric">24</div>
                    <div className="lp-dash-card-sub" />
                  </div>
                  <div className="lp-dash-card">
                    <div className="lp-dash-card-title" />
                    <div className="lp-dash-metric">3</div>
                    <div className="lp-dash-card-sub" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* LOGOS / SOCIAL PROOF */}
      <section className="lp-logos">
        <p>Trusted by leading investment firms</p>
        <div className="lp-logos-row">
          {["Meridian Capital", "Atlas Ventures", "Pinnacle Partners", "Crestview PE", "Summit Advisory"].map(
            (name) => (
              <span key={name} className="lp-logo-text">{name}</span>
            )
          )}
        </div>
      </section>

      {/* FEATURES */}
      <section className="lp-features" id="features">
        <div className="lp-section-header">
          <div className="lp-badge">Capabilities</div>
          <h2>Everything your deal team needs</h2>
          <p>
            From automatic transcription to AI-powered analysis, DealWise AI
            handles the full meeting intelligence lifecycle.
          </p>
        </div>
        <div className="lp-features-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="lp-feature-card">
              <FeatureIcon path={f.icon} />
              <h3>{f.title}</h3>
              <p>{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-how" id="how-it-works">
        <div className="lp-section-header">
          <div className="lp-badge">Workflow</div>
          <h2>Up and running in minutes</h2>
          <p>
            Three simple steps from meeting to actionable intelligence.
          </p>
        </div>
        <div className="lp-steps">
          {STEPS.map((s) => (
            <div key={s.num} className="lp-step">
              <span className="lp-step-num">{s.num}</span>
              <h3>{s.title}</h3>
              <p>{s.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <div className="lp-cta-glow" />
        <h2>Ready to transform your deal workflow?</h2>
        <p>
          Join top-tier investment teams already using DealWise AI to capture
          every insight from every meeting.
        </p>
        <div className="lp-hero-cta">
          <Link href="/login" className="lp-btn lp-btn--primary lp-btn--lg">
            Get Started Free
          </Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <span className="lp-logo">
              <span className="lp-logo-icon">D</span>
              <span>DealWise AI</span>
            </span>
            <p>AI-powered meeting intelligence for investment professionals.</p>
          </div>
          <div className="lp-footer-col">
            <h4>Product</h4>
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <Link href="/login">Dashboard</Link>
          </div>
          <div className="lp-footer-col">
            <h4>Company</h4>
            <a href="#features">About</a>
            <a href="#features">Security</a>
            <a href="#features">Contact</a>
          </div>
        </div>
        <div className="lp-footer-bottom">
          <p>&copy; {new Date().getFullYear()} DealWise AI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
