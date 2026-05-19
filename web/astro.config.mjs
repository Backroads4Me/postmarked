// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';
import react from '@astrojs/react';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  security: {
    checkOrigin: false
  },
  adapter: node({
    mode: 'standalone'
  }),
  vite: {
    server: {
      allowedHosts: ['werehere.app']
    },
    plugins: [tailwindcss()]
  },

  integrations: [react()]
});
