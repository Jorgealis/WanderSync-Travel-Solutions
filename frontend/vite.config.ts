import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo (`npm run dev`), /graphql se reenvía al gateway igual que lo hace Nginx en
// el contenedor: navegador y API comparten origen, así la cookie SameSite=Strict funciona
// sin CORS. Para el desarrollo local el gateway se publica con docker-compose.debug.yml.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/graphql": process.env.WANDERSYNC_GATEWAY_URL ?? "http://localhost:8000",
    },
  },
});
