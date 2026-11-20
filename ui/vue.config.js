const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    port: 7000,
    proxy: {
      '/auth': {
        target: process.env.VUE_APP_BACKEND_URL || 'http://127.0.0.1:810',
        changeOrigin: true
      }
    }
  }
})
