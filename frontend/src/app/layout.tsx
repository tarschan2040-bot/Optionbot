import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OptionBot — Options Scanner Dashboard",
  description: "Find the best Covered Call and Cash-Secured Put opportunities. Scored, ranked, and ready to trade.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
