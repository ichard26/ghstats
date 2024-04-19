import { resolve } from 'path'
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    rollupOptions: {
      // https://rollupjs.org/configuration-options/
      input: {
        main: resolve(__dirname, 'index.html'),
        black: resolve(__dirname, 'black/index.html'),
        mypyc: resolve(__dirname, 'mypyc/index.html'),
        pip: resolve(__dirname, 'pip/index.html'),
      },
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    },
  },
})
