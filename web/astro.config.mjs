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
    mode: 'standalone',
    // Backup archives bundle the DB dump plus every media derivative, so they
    // routinely exceed the adapter's 1 GB default. Without this, large restore
    // uploads are dropped at the connection level and surface in the browser as
    // a generic "Network error". Keep this as a generous transport cap; the
    // API enforces the product media upload limit via MAX_UPLOAD_FILE_MIB.
    bodySizeLimit: 5 * 1024 * 1024 * 1024,
  }),
  vite: {
    server: {
      allowedHosts: ['werehere.app'],
      watch: {
        usePolling: true,
      },
    },
    plugins: [tailwindcss()]
  },

  integrations: [react()]
});
