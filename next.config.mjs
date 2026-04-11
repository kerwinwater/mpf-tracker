/** @type {import('next').NextConfig} */
const nextConfig = {
  // 讓 Next.js 可以讀取 data/ 目錄中的 JSON 檔案
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
