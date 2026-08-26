import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Syurell — pemantauan pintu air",
  description: "Tinggi air, curah hujan, dan penumpukan sampah di depan pintu.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id">
      <head>
        {/* Nunito Sans, as the design specifies. The gatehouse may have no
            internet, so this is decoration only -- globals.css carries a real
            system-font fallback stack and the page is legible without it. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
