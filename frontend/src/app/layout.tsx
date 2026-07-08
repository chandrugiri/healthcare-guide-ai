import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Healthcare Guide AI",
  description: "Product-support assistant grounded in verified documentation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn("h-full bg-slate-50 antialiased", inter.variable)}
    >
      <body className="min-h-full font-sans">{children}</body>
    </html>
  );
}
