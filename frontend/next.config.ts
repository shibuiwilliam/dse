import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: "http://localhost:8000/v1/:path*",
      },
      {
        source: "/health/:path*",
        destination: "http://localhost:8000/health/:path*",
      },
    ];
  },
};

export default nextConfig;
