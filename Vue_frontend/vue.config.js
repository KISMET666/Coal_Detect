module.exports = {
  devServer: {
    port: 7000,
    proxy: {
      '/api': {
        target: 'http://172.19.72.20:5000',
        changeOrigin: true,
        ws: true,  // 确保WebSocket代理启用
        pathRewrite: {
          '^/api': '/api'  // 确保路径重写正确
        },
        // 添加以下选项确保连接稳定
        secure: false,
        headers: {
          Connection: 'keep-alive'
        }
      }
    },
    client: {

      overlay: false

 },
  }
}