import { defineConfig } from "vite";
import { cloudflare } from "@cloudflare/vite-plugin";

// cloudflare() reads cloudflare.config.ts.
export default defineConfig({ plugins: [cloudflare()] });
