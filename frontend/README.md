# ETMMS frontend / 前端 0.4.3

React + TypeScript + Vite. Use Node.js 22.12+, install with `npm ci`, and verify with `npm test`, `npm run lint`, `npm run build`. Production `dist/` is built during setup and served by the backend; it is not committed. Vite's local development server is not the public entrypoint.

使用 React、TypeScript、Vite 和 Node.js 22.12+。通过 `npm ci` 安装，使用 `npm test`、`npm run lint`、`npm run build` 验证。生产 `dist/` 在准备时构建，由后端同源托管，不提交 Git。Vite 本地开发服务器不作为公网入口。

The 0.4.2→0.4.3 patch contains prebuilt pages; applying it does not require rebuilding on Sealos. Source development remains reproducible through the lockfile.

0.4.2→0.4.3 补丁包含已构建页面，应用补丁时无需在 Sealos 重新构建；源码开发仍按锁文件复现。
