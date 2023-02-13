import { resolve } from 'path'
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    rollupOptions: {
      // https://rollupjs.org/configuration-options/
      input: {
        main: resolve(__dirname, 'index.html'),
        {% for repo in repositories %}
        {{ repo.name }}: resolve(__dirname, '{{ repo.name }}/index.html'),
        {% endfor %}
      },
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    },
  },
})

