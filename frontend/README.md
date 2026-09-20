# frontend — ETMMS 前端

> React + TypeScript + Vite。界面规范（Chrome / Material Design 3）的唯一真源是根目录 `UI.md`。

## 启动（开发态）

```bash
npm install
npm run dev      # http://localhost:5173，/api 代理到 8088
```

## 构建与检查

```bash
npm run build    # tsc -b + vite build
npm run lint     # oxlint
npm test         # vitest（组件测试）
```

## 结构

```txt
src/
├─ components/   通用组件库（见 UI.md 7.1）
├─ pages/        页面组装（只做拼装，不写样式细节）
├─ features/     各流程单元的表单状态与业务调用（M5 建立）
├─ styles/       tokens.css（Token 唯一来源）、base.css、components.css
├─ api/          接口封装（超时、取消、统一错误，M4/M5 建立）
├─ types/        与后端对齐的类型（M4/M5 建立）
└─ hooks/
```

## 硬约束（来自 UI.md，违反即视为缺陷）

- 零 inline style；未登记 Token 不得使用；未使用 Token 必须删除
- 按钮文案必须是动词短语，禁止"确定/提交/是/否"
- 一个界面最多一个主按钮；底部动作条真实存在
- 前台不得出现状态代码（STxx）、规则 ID、字段 ID
