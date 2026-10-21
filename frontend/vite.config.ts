/**
 * 文件名称：vite.config.ts
 * 所属层级：构建配置
 * 功能说明：Vite 构建与开发服务器配置。
 *   1. 开发服务器端口 5173；
 *   2. /api 代理到后端 8088（开发期前后端分离）；
 *   3. 单元测试使用 jsdom（组件测试）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */
// 使用 vitest/config 的 defineConfig，才能在配置中声明 test 段
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // 固定监听 IPv4 回环地址，确保本机浏览器通过 127.0.0.1 稳定访问，且不暴露到局域网
    host: '127.0.0.1',
    port: 5173,
    // 开发期把 /api 请求代理到后端，保持前后端分离（生产打包时由后端同源托管）
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
      },
    },
  },
  test: {
    // 组件测试运行环境
    environment: 'jsdom',
    // 限制工作线程避免本机沙箱并发启动超时；不降低断言要求。
    pool: 'threads',
    maxWorkers: 1,
    testTimeout: 15000,
    hookTimeout: 15000,
    globals: true,
    // 引入 jest-dom 断言（toBeInTheDocument 等）
    setupFiles: ['./src/test/setup.ts'],
  },
})
