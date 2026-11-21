import type { NextConfig } from "next";

const config: NextConfig = {
  distDir: process.env.PORT && process.env.PORT !== "3000" ? `.next-${process.env.PORT}` : ".next",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_URL || `http://127.0.0.1:${process.env.API_PORT || "8000"}`}/:path*` }];
  },
};
export default config;
