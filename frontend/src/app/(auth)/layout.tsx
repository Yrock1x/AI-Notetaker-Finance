export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background overflow-hidden px-6">
      <div className="noise-bg"></div>
      <div className="w-full max-w-md space-y-8 rounded-[3rem] border bg-white p-10 md:p-14 shadow-2xl relative z-10">
        {children}
      </div>
    </div>
  );
}
