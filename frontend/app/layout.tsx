import type { ReactNode } from "react";
import type { Metadata } from "next";
import { IBM_Plex_Mono, Noto_Sans_KR } from "next/font/google";

import "@/app/globals.css";


const sans = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});


export const metadata: Metadata = {
  title: {
    default: "Personal API Admin",
    template: "%s | Personal API Admin",
  },
  description: "Personal operations console for API and database management.",
  robots: { index: false, follow: false },
};


export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko">
      <body className={`${sans.variable} ${mono.variable} bg-shell font-sans text-ink antialiased`}>
        {children}
      </body>
    </html>
  );
}
