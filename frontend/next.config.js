/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxies /api/* calls to the FastAPI backend during local dev so the
    // browser never needs CORS-exempt cross-origin calls at all. Set
    // NEXT_PUBLIC_API_BASE_URL if you'd rather call the backend directly.
    return [
      {
        source: "/backend-api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
