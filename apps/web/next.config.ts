import type { NextConfig } from 'next';
const nextConfig: NextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  transpilePackages: ['@outcometrik/system', '@outcometrik/access', '@outcometrik/ui'],
  async rewrites() {
    const upstream = process.env.API_UPSTREAM ?? 'http://127.0.0.1:8000';
    return [
      { source: '/api/:path*/', destination: `${upstream}/api/:path*/` },
      { source: '/api/:path*', destination: `${upstream}/api/:path*` },
    ];
  },
};
export default nextConfig;
