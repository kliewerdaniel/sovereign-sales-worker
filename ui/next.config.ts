import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The Sovereign Worker backend serves a stdlib HTTP API on 127.0.0.1:8777.
  // This UI is fully self-contained (typed adapter + demo dataset) but supports
  // proxying to a live workspace by setting SOVEREIGN_API_BASE.
  async rewrites() {
    const base = process.env.SOVEREIGN_API_BASE;
    if (!base) return [];
    return [
      {
        source: "/api/v1/:path*",
        destination: `${base.replace(/\/$/, "")}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
