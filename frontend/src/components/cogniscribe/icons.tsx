"use client";

import type { ReactNode, SVGProps } from "react";

type IconProps = {
  size?: number;
  className?: string;
  fill?: string;
};

const baseProps = {
  xmlns: "http://www.w3.org/2000/svg",
  viewBox: "0 0 24 24",
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const make = (children: ReactNode, overrides: Partial<SVGProps<SVGSVGElement>> = {}) =>
  function IconCmp({ size = 16, className = "", fill }: IconProps) {
    return (
      <svg
        {...baseProps}
        {...overrides}
        width={size}
        height={size}
        className={className}
        fill={fill ?? overrides.fill ?? baseProps.fill}
      >
        {children}
      </svg>
    );
  };

export const I = {
  Shield: make(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />),
  Mic: make(
    <>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <path d="M12 19v3" />
    </>
  ),
  Mail: make(
    <>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-10 6L2 7" />
    </>
  ),
  Arrow: make(<path d="M5 12h14M13 6l6 6-6 6" />),
  Check: make(<path d="M20 6 9 17l-5-5" />),
  CheckCircle: make(
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  Loader: make(<path d="M21 12a9 9 0 1 1-6.22-8.56" />),
  Search: make(
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-5-5" />
    </>
  ),
  Sparkles: make(<path d="M12 3 13.5 8.5 19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />),
  File: make(<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6" />),
  Lock: make(
    <>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  Play: ({ size = 16, className = "" }: IconProps) => (
    <svg {...baseProps} width={size} height={size} className={className} fill="currentColor">
      <path d="M6 4v16l14-8z" />
    </svg>
  ),
  Pause: ({ size = 16, className = "" }: IconProps) => (
    <svg {...baseProps} width={size} height={size} className={className} fill="currentColor" stroke="none">
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  ),
  Sun: make(
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </>
  ),
  Moon: make(<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />),
  Menu: make(<path d="M3 6h18M3 12h18M3 18h18" />),
  X: make(<path d="M18 6 6 18M6 6l12 12" />),
  ChevDown: make(<path d="m6 9 6 6 6-6" />),
  TrendUp: make(<path d="m3 17 6-6 4 4 8-8M14 7h7v7" />),
  Users: make(
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  Calendar: make(
    <>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </>
  ),
  Scale: make(
    <path d="M12 3v18M3 9h18M6 9l-3 7c0 2 1.5 3 3 3s3-1 3-3l-3-7zM18 9l-3 7c0 2 1.5 3 3 3s3-1 3-3l-3-7z" />
  ),
  Briefcase: make(
    <>
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </>
  ),
  Brain: make(
    <path d="M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0-3 3 3 3 0 0 0 0 6 3 3 0 0 0 3 3v1a3 3 0 0 0 6 0v-1a3 3 0 0 0 3-3 3 3 0 0 0 0-6 3 3 0 0 0-3-3V5a3 3 0 0 0-3-3z" />
  ),
  Git: make(
    <>
      <circle cx="18" cy="18" r="3" />
      <circle cx="6" cy="6" r="3" />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <line x1="6" y1="9" x2="6" y2="21" />
    </>
  ),
  Eye: make(
    <>
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  Folder: make(
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  ),
  Paper: make(
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8M8 17h5M8 9h2" />
    </>
  ),
  Filter: make(<path d="M22 3H2l8 9.46V19l4 2v-8.54z" />),
  Zap: make(<path d="m13 2-10 12 9 1-3 7 10-12-9-1z" />),
};
