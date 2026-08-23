import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Syurell — pemantauan pintu air",
  description: "Tinggi air, curah hujan, dan penumpukan sampah di depan pintu.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
