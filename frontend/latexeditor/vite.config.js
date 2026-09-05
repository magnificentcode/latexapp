import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Builds one fixed-name bundle straight into the root static/ dir, mounted
// into a plain HTML page via a single root div — mirrors Abibotti's
// frontend/studyhub -> static/matikka.bundle.js pattern.
export default defineConfig({
  plugins: [react()],
  // Assets (including KaTeX's font url()s emitted from its CSS) are
  // served under /static/, not site root — without this, Vite emits
  // root-relative asset URLs like /katex-fonts/... that 404.
  base: '/static/',
  build: {
    outDir: '../../static',
    emptyOutDir: false,
    rollupOptions: {
      input: 'src/editor.entry.jsx',
      output: {
        entryFileNames: 'editor.bundle.js',
        chunkFileNames: 'editor.bundle.[name].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'editor.bundle.css';
          }
          return 'katex-fonts/[name][extname]';
        },
      },
    },
  },
});
