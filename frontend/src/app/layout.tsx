import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nuclei Cloud — Vulnerability Scanner Dashboard",
  description: "Distributed Nuclei scan orchestrator & dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "hsl(222 47% 8%)",
              color: "hsl(213 31% 91%)",
              border: "1px solid hsl(222 47% 14%)",
            },
          }}
        />
      </body>
    </html>
  );
}
