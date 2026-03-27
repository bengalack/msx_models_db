import { defineConfig, type Plugin } from 'vitest/config';

/**
 * Ensures the built HTML is compatible with file:// protocol:
 * - Removes type="module" and crossorigin (Chrome blocks ES module scripts on file://)
 * - Moves bundle.js to end of <body>, after data.js, so window.MSX_DATA is set first
 */
function fileProtocolCompat(): Plugin {
  return {
    name: 'file-protocol-compat',
    transformIndexHtml(html: string): string {
      // Remove the bundle script from <head> (where Vite injects it)
      const stripped = html.replace(
        /<script type="module" crossorigin src="\.\/bundle\.js"><\/script>\s*/g,
        ''
      );
      // Append it at the end of <body>, after data.js
      return stripped.replace('</body>', '  <script src="./bundle.js"></script>\n  </body>');
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [fileProtocolCompat()],
  build: {
    outDir: 'docs',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        format: 'iife',
        name: 'MSXApp',
        entryFileNames: 'bundle.js',
        chunkFileNames: 'bundle.js',
        assetFileNames: '[name][extname]',
      },
    },
  },
  test: {
    environment: 'jsdom',
    passWithNoTests: true,
  },
});
