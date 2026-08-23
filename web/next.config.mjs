/** @type {import('next').NextConfig} */
const nextConfig = {
  // better-sqlite3 is a native module; it must stay external to the server
  // bundle or Next tries to trace and rewrite the .node binary and fails.
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;
