/** @type {import('next').NextConfig} */
const nextConfig = {
  // 使用標準 Next.js 構建（Vercel 原生支援）
  // 移除 output: 'export'，讓 Vercel 自動生成 routes-manifest.json
  trailingSlash: true,
};

export default nextConfig;
