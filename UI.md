# UI.md — ETMMS 界面规范与代码注释规范（唯一真源）

> **版本**：v1.0｜**日期**：2026-09-19｜**状态**：有效（V1.0 基线）
> **适用范围**：本软件全部前端界面与全部前后端代码注释。
> **效力**：本文件是 UI 与注释的**唯一真源**。`_SPEC` 各文件不再重复描述 UI 细节；实现与本文冲突时以本文为准。
> **变更控制**：任何 Token 新增、修改或删除，必须在本文件第二节与附录 B 登记，并同步 `mapping.md`。

---

## 目录

**第一部分 UI 设计规范**

1. 设计总原则与视觉体系
2. Design Token（强制）
3. 组件规范
4. 布局规范
5. 反模式清单（禁止行为）
6. Token 使用率自查机制

**第二部分 前端工程规范**

7. 组件库与目录约定
8. 交互与无障碍

**第三部分 代码注释规范**

9. 注释总原则
10. 文件头与函数块模板
11. 逐行注释规则
12. 注释禁用项

**附录**

A. TypeScript / CSS 常量
B. Token 使用登记表

---

# 第一部分 UI 设计规范

## 1. 设计总原则与视觉体系

本软件是**临床决策支持工具**，核心用户是门诊医生。界面最高目标是：**让医生在最短时间内、无歧义地理解当前临床状态和下一步操作**。

### 1.1 四条原则（优先级从高到低）

1. **逻辑清晰优先于美观**：功能分区一目了然，任何装饰不得干扰信息阅读。医生操作路径（预评估 → 完整评估 → 阶段复评 → 观察 → 判定 → 缓解后复评）始终可见。
2. **克制的视觉层级**：用留白、1px 描边和表面色差表达层级，**不靠阴影和渐变**。禁止大面积高饱和色。
3. **减少歧义**：每个按钮、标签、提示的文字必须明确表达"点击后会发生什么"。禁止"确定""提交""是/否"等含糊措辞，改用动词短语（"进入完整评估""确认进入缓解观察期"）。
4. **减少不必要元素**：一个界面只呈现当前决策所需元素；非当前步骤的字段一律隐藏或折叠；同一信息只出现一次。

### 1.2 视觉体系：Google Chrome / Material Design 3

本软件运行在 Chrome 中，界面体系采用 **Google 现行 Material Design 3（GM3）Web 调色板与形状语言**——即 Chrome 设置页（`chrome://settings`）与 Google 网页应用（Gmail、Drive、日历）自 2023 年起的视觉体系。特征：

- **单一品牌色**：Google 蓝只用于主操作、链接、选中态与焦点环
- **浅灰表面分层**：白面为主，浅灰表面色表达"次级容器"，不用阴影
- **胶囊形交互件**：按钮、导航选中项、状态徽章为全圆角
- **行式设置项**：左侧标签 + 右侧控件 + 下方说明，用 1px 分隔线分组
- **克制的字体层级**：正文 14px，标题 16/24px，页面标题 24px

> **取值来源说明**：本文 Token 值取自 Google Material 3 公开调色板与 Chrome 现行界面特征。
> **校准任务（M1 必须完成）**：用本机 Chrome 打开 `chrome://settings` 截图，与本文 Token 做一次视觉比对，偏差处按实际值修正并在附录 B 记录修订。

---

## 2. Design Token（强制）

> 以下数值是**强制约束**。AI 与开发者必须使用下列变量，**禁止自行发明**新颜色、新圆角、新间距、新字号。确需新增的，必须先在附录 B 登记并经 Lifan 确认。
>
> 命名前缀统一为 `--etmms-`，避免与第三方库样式冲突。

### 2.1 颜色

```css
:root {
  /* ===== 品牌色（Google 蓝）===== */
  --etmms-primary:              #0B57D0;  /* 主操作、链接、选中态、焦点环 */
  --etmms-on-primary:           #FFFFFF;  /* 主色之上的文字 */
  --etmms-primary-container:    #D3E3FD;  /* 选中背景、浅色强调底 */
  --etmms-on-primary-container: #041E49;  /* 浅色强调底之上的文字 */

  /* ===== 表面层（浅灰分层，替代阴影）===== */
  --etmms-surface:                 #FFFFFF;  /* 主表面：内容区、卡片 */
  --etmms-surface-container-low:   #F8FAFD;  /* 次级表面：页头、抽屉背景 */
  --etmms-surface-container:       #F0F4F9;  /* 三级表面：分组块、只读区块 */
  --etmms-surface-container-high:  #E9EEF6;  /* 悬停态表面 */

  /* ===== 文字层 ===== */
  --etmms-on-surface:          #1F1F1F;  /* 主文字：标题、关键结论 */
  --etmms-on-surface-variant:  #444746;  /* 次文字：说明、辅助信息、标签 */
  --etmms-on-surface-disabled: #8E918F;  /* 禁用态、占位符 */

  /* ===== 描边与分割线 ===== */
  --etmms-outline:         #747775;  /* 输入框描边、强调描边 */
  --etmms-outline-variant: #C4C7C5;  /* 卡片描边、常规分割线 */

  /* ===== 语义色（仅表达临床状态，不得用作装饰）===== */
  --etmms-success:              #146C2E;  /* 达标：满足缓解条件 */
  --etmms-success-container:    #C4EED0;
  --etmms-on-success-container: #072711;

  --etmms-warning:              #B06000;  /* 暂缓、需注意 */
  --etmms-warning-container:    #FEEFC3;
  --etmms-on-warning-container: #3E2C00;

  --etmms-error:              #B3261E;  /* 风险、急性不安全、不可逆操作 */
  --etmms-error-container:    #F9DEDC;
  --etmms-on-error-container: #410E0B;

  /* ===== 状态层（交互反馈，叠加在任意表面之上）===== */
  --etmms-state-hover:   rgba(31, 31, 31, 0.08);
  --etmms-state-focus:   rgba(11, 87, 208, 0.12);
  --etmms-state-pressed: rgba(31, 31, 31, 0.12);
}
```

**使用规则**

- 主文字一律 `--etmms-on-surface`；说明性文字用 `--etmms-on-surface-variant`；占位符与禁用态用 `--etmms-on-surface-disabled`。
- `--etmms-primary` **只**用于：主行动按钮、当前选中导航项、可点击链接、输入框焦点环。禁止大面积铺设。
- 语义色**只**用于临床状态标签与临床结论提示，不得用于普通装饰或图表配色。
- 语义色必须以「浅底 + 深字」组合使用（如 `success-container` + `on-success-container`），禁止纯色大字块。

### 2.2 圆角

```css
:root {
  --etmms-radius-xs:   4px;   /* 输入框、小块控件、图像缩略 */
  --etmms-radius-sm:   8px;   /* 卡片、分组块、菜单 */
  --etmms-radius-md:   12px;  /* 对话框、抽屉、大型面板 */
  --etmms-radius-full: 999px; /* 胶囊：按钮、导航选中项、状态徽章 */
}
```

**使用规则**：按钮、导航选中项、状态徽章一律胶囊形（`--etmms-radius-full`）；卡片与分组块用 `--etmms-radius-sm`；对话框与抽屉用 `--etmms-radius-md`。禁止直角（0px）与自由取值。

### 2.3 间距（4px 基数）

```css
:root {
  --etmms-space-1: 4px;   /* 图标与文字、紧贴元素 */
  --etmms-space-2: 8px;   /* 相关控件之间 */
  --etmms-space-3: 12px;  /* 行内控件组之间 */
  --etmms-space-4: 16px;  /* 区块内部留白（默认） */
  --etmms-space-5: 24px;  /* 区块之间 */
  --etmms-space-6: 32px;  /* 大区块之间 */
  --etmms-space-7: 40px;  /* 页面级留白 */
}
```

**使用规则**：只允许取上表 7 个值；禁止 7px、13px、22px 等非阶梯值。间距必须是 4 的倍数。

### 2.4 字体与字号

```css
:root {
  /* Chrome / Android 字体栈优先 Roboto；中文按系统回落 */
  --etmms-font-family: Roboto, "Google Sans", "Segoe UI",
                       "PingFang SC", "Microsoft YaHei", "Noto Sans SC",
                       "Helvetica Neue", Arial, sans-serif;
  --etmms-font-mono:   "Roboto Mono", Consolas, "Courier New", monospace;

  --etmms-text-page-title:    24px;  /* 页面主标题（行高 32px） */
  --etmms-text-section-title: 16px;  /* 小节标题、卡片标题（行高 24px） */
  --etmms-text-body:          14px;  /* 正文、表单项（行高 20px） */
  --etmms-text-label:         14px;  /* 表单标签、按钮（行高 20px） */
  --etmms-text-caption:       12px;  /* 辅助说明、字段提示（行高 16px） */

  --etmms-weight-regular:  400;
  --etmms-weight-medium:   500;  /* 标签、按钮、小节标题 */
  --etmms-weight-semibold: 600;  /* 关键临床结论（同屏最多一处） */

  --etmms-line-tight:  1.33;  /* 标题 32/24 */
  --etmms-line-normal: 1.43;  /* 正文 20/14（Material 标准） */
}
```

**使用规则**

- 正文固定 14px——这是临床信息密集场景的阅读字号，禁止随意放大。
- 关键临床结论可用 `--etmms-weight-semibold` + `--etmms-text-section-title`；同一界面最多一处。
- 所有数值（HbA1c、BMI、日期、剂量）使用等宽数字特性：`font-variant-numeric: tabular-nums;`（统一工具类 `.num`）。
- 中英混排：数字与单位（HbA1c、BMI、FPG、CGM、SGLT2）保留英文，其余一律中文。

### 2.5 层级与描边（替代阴影）

```css
:root {
  --etmms-border-width: 1px;
  --etmms-elevation-0: none;                           /* 常规内容：不用阴影 */
  --etmms-elevation-1: 0 1px 2px rgba(0, 0, 0, 0.06);  /* 极轻浮起：仅吸顶动作条 */
  --etmms-elevation-2: 0 2px 6px rgba(0, 0, 0, 0.10);  /* 浮层：对话框、抽屉 */
}
```

**使用规则**：层级由**表面色差 + 1px 描边**表达。阴影仅允许用于吸顶动作条与浮层（对话框、抽屉、菜单），禁止给普通卡片、文字、静态区块加阴影。禁止渐变、毛玻璃、发光效果。

### 2.6 尺寸常量

```css
:root {
  --etmms-sidebar-width:  240px;  /* 左侧导航宽度 */
  --etmms-content-max:    960px;  /* 内容区最大宽度 */
  --etmms-control-height: 40px;   /* 输入框、下拉框高度 */
  --etmms-button-height:  36px;   /* 按钮高度 */
  --etmms-row-height:     48px;   /* 行式设置项高度 */
  --etmms-appbar-height:  56px;   /* 顶栏高度 */
  --etmms-drawer-width:   420px;  /* 侧边抽屉宽度（依据查询） */
}
```

### 2.7 动效

```css
:root {
  --etmms-motion-fast: 120ms cubic-bezier(0.2, 0, 0, 1);  /* 悬停、按下 */
  --etmms-motion-base: 200ms cubic-bezier(0.2, 0, 0, 1);  /* 抽屉、菜单展开 */
}
```

**使用规则**：只允许颜色、透明度、位移的过渡。禁止装饰性动画、循环动画、弹跳效果。必须尊重 `prefers-reduced-motion: reduce`。

---

## 3. 组件规范

### 3.1 按钮

| 层级 | 样式 | 用途 | 示例文案 |
| --- | --- | --- | --- |
| 主按钮（filled） | `--etmms-primary` 底 + `on-primary` 字，胶囊形，高 36px，内边距 24px | 当前步骤**唯一**的主要行动 | "进入完整评估" |
| 次按钮（outlined） | 透明底 + 1px `--etmms-outline` 描边 + 主文字色 | 次要行动、并列多选场景 | "暂缓进入" |
| 文字按钮（text） | 无背景无描边，`--etmms-primary` 文字 | 低干扰辅助操作、行内操作 | "查看历史记录" |
| 危险按钮（danger） | `--etmms-error` 文字或填充 | 不可逆、高风险操作，使用前必须二次确认 | "结束主动管理" |

**规则**

- **一个界面最多一个主按钮**；多个并列操作一律用次按钮或文字按钮。
- 按钮文字必须是**动词短语**，说明点击后果；禁止"确定""提交""是/否""取消"。
- 禁用态：`--etmms-on-surface-disabled` 文字 + 降低底透明度；必须同时置灰并设 `cursor: not-allowed`，不得只靠颜色表达禁用。
- 异步提交中：文案改为进行时（如"正在核对客观条件…"）并禁用，不得添加装饰性动效。

### 3.2 行式设置项（本软件的核心控件形态）

Chrome 设置页的基本单元是"标签在左、控件在右、说明在下"。本软件全面采用该形态：

```txt
┌──────────────────────────────────────────────────────────┐
│ 标签文字（14px / 500）                        [ 控件 ]    │  ← 行高 48px
│ 说明文字（12px / on-surface-variant）                     │
└──────────────────────────────────────────────────────────┘
```

- 一行只表达一个临床信息，禁止把两个不相关字段塞进同一行。
- 说明文字只在"需要解释判定口径"时出现（例："BMI 正常、使用胰岛素或 C 肽缺失本身不能自动判为分型疑点"）。
- 行与行之间用 1px `--etmms-outline-variant` 分隔；同一分组的最后一行不加分隔线。

### 3.3 输入控件

| 控件 | 规格 |
| --- | --- |
| 文本框 / 下拉框 | 高 40px，圆角 4px，1px `--etmms-outline` 描边，内边距 12px；聚焦时描边改 `--etmms-primary` 并加 1px 内描边（不使用外发光） |
| 多行文本 | 最小高 80px，其余同上，允许纵向拉伸 |
| 数值输入 | 必须启用 `.num` 等宽数字 |
| 日期输入 | 使用浏览器原生日期控件，外观统一到 Token |
| 复选框 / 单选 | 18px，选中态用 `--etmms-primary`；**必须有关联标签**，点击标签即可切换 |
| 多选组 | 纵向排列，每项独立一行 |

**强制**：每个控件必须能被读屏识别（`<label for>` 或 `aria-label`）；禁止仅用占位符代替标签；禁止用复选框表达互斥选项（见 3.5）。

### 3.4 状态徽章与结论提示

| 语义 | 背景 | 文字 | 示例 |
| --- | --- | --- | --- |
| 达标/成功 | `--etmms-success-container` | `--etmms-on-success-container` | "满足缓解条件" |
| 暂缓/需注意 | `--etmms-warning-container` | `--etmms-on-warning-container` | "暂缓进入" |
| 风险/阻断 | `--etmms-error-container` | `--etmms-on-error-container` | "急性不安全" |
| 进行中/中性 | `--etmms-primary-container` | `--etmms-on-primary-container` | "缓解观察期" |

- 徽章胶囊形，高 24px，内边距 4px 12px，字号 12px。
- **结论提示区**（系统给医生看的自然语言结论）：`surface-container` 底 + 1px 描边 + 16px 内边距；正文 16px；禁止用语义色铺满整块底色。

### 3.5 分支选择控件（互斥性表达，V1.0 新增硬约束）

临床分支存在**优先级**（例如阶段复评：明显失控 > 治疗下达标用获益药 > 停用最后一种药 > 常规复评动作）。界面必须让优先级对医生可见：

1. **互斥分支一律用单选**，禁止用多个独立复选框表达可能互斥的临床分支。
2. 分支按优先级**自上而下排列**，每条分支自带一句"选了会发生什么"的说明。
3. 选中高优先级分支后，被覆盖的低优先级输入项必须**禁用并说明原因**（例："已选择明显血糖失控，停药记录不适用于本次复评"），禁止静默忽略用户已填内容。
4. 互斥校验由**后端与前端共享同一份分支定义**（`_SPEC/07` 定义的单一数据源），不允许前端硬编码一套、后端硬编码另一套。

### 3.6 卡片、分组与列表

- 卡片：`--etmms-surface` 底 + 1px `--etmms-outline-variant` 描边 + 8px 圆角 + 16~24px 内边距；**不加阴影**。
- 分组块：`--etmms-surface-container` 底，用于"只读信息""时间锚点"等次级内容。
- 表格：表头 12px `on-surface-variant`，行高 48px，行间 1px 分隔线；数字列右对齐并使用 `.num`。
- 卡片不得嵌套超过两层。

### 3.7 导航项

- 高 40px，胶囊形，内边距 0 16px；图标 20px 与文字间距 12px。
- 选中态：`--etmms-primary-container` 底 + `--etmms-on-primary-container` 文字。
- 悬停态：`--etmms-surface-container-high` 底。
- 已完成项必须**可点击回看**（禁止禁用）；未到达项置灰并标注"尚未到达"。
- 导航项文案携带状态语义（例：已完成打勾图标，当前项加粗），但**不得显示状态代码**（STxx）。

### 3.8 抽屉（医学依据查询）

- 从右侧滑出，宽 420px，`--etmms-surface-container-low` 底，`--etmms-elevation-2`，左侧 1px 描边。
- 结构：标题栏（标题 + 关闭按钮）→ 检索输入 → 结果列表（命中的依据条目 + 出处）。
- 检索结果必须显示**出处**（材料名 + 页码/章节），供医生核对；材料未录入时显示明确占位文案。

### 3.9 状态页（加载 / 空 / 错误）

| 状态 | 呈现 |
| --- | --- |
| 加载中 | 居中文字说明（"正在读取患者信息…"）+ 骨架行；禁止转圈超过 1 处的重复提示 |
| 空态 | 一句说明 + 一个明确动作（如"暂无患者档案" + "建立患者档案"） |
| 错误 | `--etmms-error-container` 底提示条，含自然语言原因与可执行动作（"重试""返回患者列表"） |

---

## 4. 布局规范

### 4.1 总体布局（双栏 + 底部动作条）

```txt
┌───────────────┬────────────────────────────────────────────┐
│               │  页头：页面标题 + 一句话说明 + 患者上下文      │
│  左侧导航      ├────────────────────────────────────────────┤
│  （6 个流程    │                                            │
│   单元 +       │  内容区：当前步骤的设置行 / 决策表单          │
│   医学依据）   │        （最大宽度 960px，纵向滚动）           │
│               │                                            │
│               ├────────────────────────────────────────────┤
│               │  底部动作条：主按钮（右对齐）+ 次按钮         │
└───────────────┴────────────────────────────────────────────┘
```

**硬约束（针对 V0.1 缺陷的直接修正）**

- **只保留一套流程导航**：流程进度只在左侧导航表达；**禁止**再在页头放横向步骤条（重复表达会分散注意力并造成折行）。
- **底部动作条是真实的组件**，不是只定义不使用的样式类；每个决策页的主按钮必须放在动作条内。
- 左侧导航固定宽度 240px，不随滚动移动；内容区独立滚动。

### 4.2 页头

- 高 56px，`--etmms-surface-container-low` 底，底部 1px 描边。
- 左侧：页面标题（16px/500）+ 当前患者姓名与病历号（12px/`on-surface-variant`）。
- 右侧：全局入口——"医学依据"按钮、账号菜单（当前登录医生 + 退出）。
- **禁止**在页头显示状态代码；当前阶段用自然语言徽章表达（如"主动管理—缓解诱导阶段"）。

### 4.3 内容区

- 内边距 24px；内容最大宽度 960px。
- 页面结构固定为：`页面说明 → 分组设置行 → （结果区）`。
- 结果区（系统结论）必须紧跟触发它的操作，不得跳到页面另一端。

### 4.4 响应式

- 最小支持宽度 1024px（门诊台式机/笔记本）。
- 低于 1024px 时左侧导航折叠为 56px 图标模式；本软件**不面向手机端**，无需移动端适配。

---

## 5. 反模式清单（一律禁止）

1. ❌ **禁止 inline style**：页面/组件中不得出现 `style={{ ... }}` 静态样式（仅允许由数据计算出的动态数值，如进度条宽度）；样式一律写在样式文件里。
2. ❌ **禁止"确定/提交/是/否/取消"等含糊按钮文案**：必须写明动作后果。
3. ❌ **禁止自定义非 Token 的颜色、圆角、间距、字号、阴影**。
4. ❌ **禁止大面积阴影、渐变、毛玻璃、发光**。
5. ❌ **禁止装饰性图标、循环动画、无功能含义的动效**。
6. ❌ **禁止前台出现状态代码（STxx）、规则 ID（E1-B01）、字段 ID（F001）或工程术语**。
7. ❌ **禁止同一界面出现两个及以上主按钮**。
8. ❌ **禁止重复收集已录入字段**（病程、BMI、分型、C 肽、并发症只在一处采集，后续只更新变化）。
9. ❌ **禁止未登记的 Token**：新增 Token 必须先登记（附录 B）再使用。
10. ❌ **禁止未使用的 Token 长期留存**：定义即须使用，否则删除。
11. ❌ **禁止同一语义出现两套导航**（页头步骤条 + 侧边导航并存）。
12. ❌ **禁止用复选框表达互斥临床分支**，禁止静默忽略医生已填内容。
13. ❌ **禁止中文界面混入英文标签**（医学缩写 HbA1c、BMI、FPG、CGM、SGLT2 除外）。
14. ❌ **禁止状态标签用于装饰**：语义色必须与临床状态严格对应。

---

## 6. Token 使用率自查机制（强制）

V0.1 的教训：规范里定义了 `--surface-glass`、`.glass-panel` 等一整套 Liquid Glass，代码里**零使用**，导致"规范很漂亮、界面很难看"。

因此 V1.0 建立以下机制：

1. **定义即须使用**：本文件第 2 节任一定义的 Token，必须在 `frontend/src/styles/` 中至少被引用一次。
2. **自动自查**：`scripts/check_docs.py` 扫描 Token 定义与实际引用，输出"未使用 Token 清单"。
3. **过门条件**：每个里程碑的合并前提是"未使用 Token 数 = 0"；确实为未来预留的 Token 必须删除，等需要时再登记。
4. **登记回填**：自查结果回填到附录 B 的"使用位置"列。

---

# 第二部分 前端工程规范

## 7. 组件库与目录约定

### 7.1 先建组件库，再写页面

V0.1 的问题是 8 个页面各自用 inline style 拼界面，风格无法统一、改一处要改八处。V1.0 的顺序是**先组件库、后页面**，页面只做组装。

必备组件（命名固定，实现于 `frontend/src/components/`）：

| 组件 | 职责 |
| --- | --- |
| `PageHeader` | 页面标题 + 一句话说明 + 患者上下文 |
| `ActionBar` | 底部动作条：主按钮 + 次按钮 |
| `SettingsRow` | 行式设置项：标签 + 控件 + 说明 |
| `FieldRow` | 表单字段行（标签 + 输入控件 + 校验提示） |
| `ChoiceGroup` | 单选/多选组，支持"互斥 + 优先级"模式（3.5） |
| `ResultBanner` | 系统自然语言结论提示区 |
| `StatusBadge` | 临床状态徽章 |
| `SideNav` | 左侧流程导航 |
| `EvidenceDrawer` | 医学依据检索抽屉 |
| `EmptyState` / `ErrorBanner` / `LoadingBlock` | 空态 / 错误 / 加载 |
| `ConfirmDialog` | 不可逆操作二次确认 |

### 7.2 目录约定

```txt
frontend/src/
├─ components/     通用组件（上表）
├─ pages/          页面（只做组装，不写样式细节）
├─ features/       按流程单元划分的业务逻辑与表单状态
├─ styles/         tokens.css（Token 唯一来源）、base.css、组件样式
├─ api/            后端接口封装
├─ types/          与后端对齐的类型定义
└─ hooks/          自定义 Hook（如 usePatient、useOperator）
```

### 7.3 样式规则

- `styles/tokens.css` 是 Token 的**唯一来源**，与本文第 2 节逐字对应；修改 Token 必须同时改本文与 `mapping.md`。
- 组件样式使用 CSS 文件 + 语义类名（BEM 风格，如 `.settings-row__label`），禁止 CSS-in-JS 与 inline style。
- 禁止 `!important`（第三方库覆盖除外，且必须写明原因注释）。

---

## 8. 交互与无障碍

### 8.1 交互铁律

1. **提交前校验**：必填缺失、互斥冲突、数值异常必须在提交前就地提示，不得只依赖后端报错。
2. **不可逆操作二次确认**：结束主动管理、关闭缓解路径、停用最后一种降糖药等操作必须弹出确认，确认文案写明后果。
3. **结果必须可追溯**：任何决策提交后，页面必须显示该次决策的自然语言结论（`ResultBanner`），并可在事件历史中回看。
4. **禁止静默失败**：接口失败必须显示自然语言原因 + 可执行动作（重试/返回）。
5. **禁止静默覆盖**：分支优先级覆盖医生已填内容时，必须显式说明（见 3.5）。
6. **网络健壮性**：请求必须有超时与取消机制；重复点击不得产生重复提交（按钮禁用 + 幂等标识）。

### 8.2 无障碍

- 所有表单控件必须有可读标签；错误提示与控件用 `aria-describedby` 关联。
- 焦点可见：聚焦时必须有 2px `--etmms-primary` 内描边（不得仅靠 `box-shadow` 外发光）。
- 键盘可达：全部交互元素可用 Tab 遍历，对话框需支持 Esc 关闭与焦点圈定。
- 颜色不得作为唯一信息载体：状态必须同时有文字或图标。
- 对比度：正文文字与背景对比度 ≥ 4.5:1；大字与图形 ≥ 3:1。

---

# 第三部分 代码注释规范

## 9. 注释总原则

1. **简体中文优先**：所有注释使用简体中文。医学专业术语（HbA1c、BMI、FPG、CGM、SGLT2 等）与代码标识符保留英文，解释性文字用中文。
2. **每个文件、每个函数必须有关联块注释**：无块注释的代码视为未完成。
3. **重要步骤逐行注释**：临床分支判断、状态转换、日期计算、数据持久化、审计记录，必须逐行说明"为什么这样做"。
4. **解释"为什么"，不解释"是什么"**：`x = x + 1` 不写"x 加 1"，而应写业务含义。
5. **注释与代码同步**：改代码必须改注释；过期注释比无注释危害更大。

---

## 10. 文件头与函数块模板

### 10.1 Python 后端文件

```python
"""
模块名称：pre_assessment.py
所属层级：临床逻辑服务层（services）
功能说明：实现"单元1｜60秒缓解预评估"的业务逻辑。
          根据医生输入判断患者应进入完整评估、暂缓进入还是当前不启动。

主要函数：
    - evaluate_pre_assessment()：核心决策函数，返回三类主结论之一。

临床依据：《临床流程锁定稿 v1.0》第五节；规则 E1-B01…E1-B05。
修改历史：
    - 2026-09-19  v1.0  自 V0.1 继承并按 V1.0 架构重构
"""
```

### 10.2 Python 函数

```python
def evaluate_pre_assessment(
    patient: PatientContext,
    data: PreAssessmentInput,
    today: date,
) -> PreAssessmentResult:
    """
    执行 60 秒预评估的核心决策逻辑。

    只判断患者是否值得进入完整评估，不判断最终能否缓解。

    参数:
        patient (PatientContext): 患者上下文（仅提供必要字段，避免重复录入）。
        data (PreAssessmentInput): 医生填写的预评估输入，含核心五问与机会信息。
        today (date): 决策当天（由 Clock 注入，便于测试时间边界）。

    返回:
        PreAssessmentResult: 三类主结论之一（进入完整评估 / 暂缓进入 / 当前不启动）
                             及其原因、前置任务、返回位置与输出模板。

    异常:
        BusinessRuleError: 输入组合不构成任何合法分支时抛出（属工程缺陷，不应发生在外层）。

    临床依据:
        《临床流程锁定稿 v1.0》第五节；规则 E1-B01…E1-B05。
    """
```

### 10.3 TypeScript / TSX 文件与函数

```tsx
/**
 * 组件名称：PreAssessmentPage.tsx
 * 所属层级：页面组件（pages）
 * 功能说明：渲染"60秒缓解预评估"页面，收集医生输入并调用后端决策接口。
 *
 * 交互流程：
 *   1. 医生回答核心五问（机会信息可不填，不阻断）；
 *   2. 点击"完成预评估并查看结论"调用 POST /api/patients/{id}/pre-assessment；
 *   3. 按三类主结论展示自然语言结论与后续入口。
 *
 * 临床依据：《临床流程锁定稿 v1.0》第五节。
 * 修改历史：
 *   - 2026-09-19  v1.0  自 V0.1 继承并按 V1.0 组件库重构
 */
```

```tsx
/**
 * 提交预评估并跳转到对应下一步。
 *
 * @param patientId 患者主键
 * @param payload 医生填写的预评估表单数据
 * @returns 后端返回的三类主结论对象
 *
 * @throws ApiError 当后端返回非 2xx 时抛出，message 为医生可读的自然语言说明
 *
 * 临床依据：《临床流程锁定稿 v1.0》第五节
 */
async function submitPreAssessment(
  patientId: number,
  payload: PreAssessmentForm,
): Promise<PreAssessmentResult> { ... }
```

---

## 11. 逐行注释规则

以下四类代码**每一行**都必须有中文注释说明业务含义：

### 11.1 临床分支判断

```python
# 根据病程是否超过 5 年，仅作机会分层，不得作为排除条件
if duration_years > 5:
    # 病程长只是提示缓解机会较低，仍可进入完整评估
    opportunity_level = "较低"
else:
    # 病程短提示缓解机会较高
    opportunity_level = "较高"
```

### 11.2 状态转换

```python
# 若停用了最后一种具有降糖作用的药物
if remaining_glucose_lowering_drugs == 0:
    # 系统自动进入缓解观察期，无需医生确认
    # 记录停药日期作为观察期的时间锚点
    patient.last_med_stop_date = today
    # 计算最早可判定日期（停药满 3 个日历月）
    patient.earliest_judge_date = add_months_clamped(today, 3)
```

### 11.3 日期与时间计算

```python
# 缓解判定需同时满足：停药满 3 个月 且 生活方式干预满 6 个月（或代谢手术满 3 个月）
# 取两者中较晚的日期作为最早判定日，空缺锚点不参与 MAX
earliest_judge = max(
    add_months_clamped(drug_stop_date, 3),   # 停药满 3 个日历月
    add_months_clamped(lifestyle_start_date, 6),  # 生活方式干预满 6 个日历月
)
```

### 11.4 数据持久化与审计

```python
# 将本次决策写入事件流水，保证临床可追溯
db_session.add(event)
# 同时写入审计日志，记录操作者与动作来源
db_session.add(audit_entry)
# 提交事务，确保事件与审计原子写入
db_session.commit()
```

### 11.5 无需逐行注释的代码

- 简单变量赋值、对象构造、模板渲染等自明代码不写逐行注释。
- 纯样式代码（CSS/className）不写逐行注释，除非涉及特殊视觉处理。

---

## 12. 注释禁用项

1. ❌ 禁止英文注释（医学缩写与代码标识符除外）。
2. ❌ 禁止无主 TODO：格式必须为 `# TODO(Lifan): 2026-10-01 前补充 C 肽缺失分支处理`。
3. ❌ 禁止注释掉的死代码：直接删除，Git 历史可追溯。
4. ❌ 禁止无意义注释（`# 赋值`、`# 返回结果`）。
5. ❌ 禁止注释与代码不一致。
6. ❌ 禁止在注释中写临床结论：注释只能说明"代码如何处理某类输入"，不得出现"该患者不适合缓解"等判断。

---

# 附录 A：TypeScript / CSS 常量

```ts
// 颜色 token（与 CSS 变量一一对应，供需要动态取色的场景使用）
export const colors = {
  primary: '#0B57D0',
  onPrimary: '#FFFFFF',
  primaryContainer: '#D3E3FD',
  onPrimaryContainer: '#041E49',
  surface: '#FFFFFF',
  surfaceContainerLow: '#F8FAFD',
  surfaceContainer: '#F0F4F9',
  surfaceContainerHigh: '#E9EEF6',
  onSurface: '#1F1F1F',
  onSurfaceVariant: '#444746',
  onSurfaceDisabled: '#8E918F',
  outline: '#747775',
  outlineVariant: '#C4C7C5',
  success: '#146C2E',
  successContainer: '#C4EED0',
  warning: '#B06000',
  warningContainer: '#FEEFC3',
  error: '#B3261E',
  errorContainer: '#F9DEDC',
} as const
```

CSS 变量完整定义见本文件第 2 节，直接复制到 `frontend/src/styles/tokens.css`。

---

# 附录 B：Token 使用登记表

> **维护规则**：任何 Token 的新增、修改、删除都必须在此登记；每次里程碑由 `scripts/check_docs.py` 回填"使用位置"与"使用次数"。
> **过门条件**：未使用 Token 数必须为 0。

| Token 组 | Token 数量 | 使用位置（由自查脚本回填） | 状态 |
| --- | --- | --- | --- |
| 品牌色（primary / on-primary / primary-container / on-primary-container） | 4 | 待 M1 回填 | 已定义 |
| 表面层（surface / surface-container-low / surface-container / surface-container-high） | 4 | 待 M1 回填 | 已定义 |
| 文字层（on-surface / on-surface-variant / on-surface-disabled） | 3 | 待 M1 回填 | 已定义 |
| 描边（outline / outline-variant） | 2 | 待 M1 回填 | 已定义 |
| 语义色（success / warning / error 三组各 3 个） | 9 | 待 M1 回填 | 已定义 |
| 状态层（hover / focus / pressed） | 3 | 待 M1 回填 | 已定义 |
| 圆角（xs / sm / md / full） | 4 | 待 M1 回填 | 已定义 |
| 间距（space-1 … space-7） | 7 | 待 M1 回填 | 已定义 |
| 字体（family / mono / 5 个字号 / 3 个字重 / 2 个行高） | 11 | 待 M1 回填 | 已定义 |
| 层级与描边（border-width / elevation-0…2） | 4 | 待 M1 回填 | 已定义 |
| 尺寸常量（sidebar-width … drawer-width） | 7 | 待 M1 回填 | 已定义 |
| 动效（motion-fast / motion-base） | 2 | 待 M1 回填 | 已定义 |

## 修订记录

| 版本 | 日期 | 修订内容 | 修订者 |
| --- | --- | --- | --- |
| v1.0 | 2026-09-19 | 全面重写：由 macOS Liquid Glass 体系改为 Google Chrome / Material Design 3 体系；新增 Token 使用率自查机制、分支互斥规范、前端工程规范、无障碍规范 | spec 工程侧（经 Lifan 批准） |
| v0.x | 2026-08-22 | 历史版本（macOS 26 Liquid Glass），留存于 `_DEV\历史参考\UI设计规范_macOS版_v1.0_历史版本.md` | 历史 |
