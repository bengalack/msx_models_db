import { defineConfig, type Plugin } from 'vitest/config';

/**
 * Strips type="module" and crossorigin from script tags in the built HTML.
 * Required for file:// protocol support — Chrome blocks ES module scripts
 * loaded from file:// regardless of path format.
 */
function stripModuleType(): Plugin {
  return {
    name: 'strip-module-type',
    transformIndexHtml(html: string): string {
      return html.replace(/<script type="module" crossorigin/g, '<script');
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [stripModuleType()],
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
