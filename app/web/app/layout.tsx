import type { Metadata } from "next";
import { Providers } from "../components/providers";
import { Shell } from "../components/shell";
import "./globals.css";

export const metadata: Metadata = { title: "EventLens — Event risk research", description: "Market probabilities, transparent forecasts and paper portfolio scenarios." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
