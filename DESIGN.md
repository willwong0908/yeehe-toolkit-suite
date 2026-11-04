---
name: 译禾工具合集 · 中性工作台
description: 面向中文用户的本地翻译工作台，以清晰对话、列映射和克制的明暗界面组织工作。
colors:
  bg: "#212121"
  panel: "#252525"
  panel-soft: "#2c2c2c"
  sidebar-bg: "#191919"
  ink: "#ededed"
  muted: "#adadad"
  line: "#424242"
  line-strong: "#707070"
  primary: "#ededed"
  primary-strong: "#fff"
  button-ink: "#202020"
  selected-bg: "#383838"
  selected-border: "#888"
  danger: "#f2a29c"
  danger-bg: "#372827"
  danger-line: "#77504d"
  success: "#9bceae"
  success-bg: "#26362c"
  success-line: "#4a7057"
  warning: "#dfc48b"
  warning-bg: "#393225"
  warning-line: "#776441"
  focus: "#6393bd"
  selection: "#b6d4ed"
  light-bg: "#fff"
  light-panel: "#fff"
  light-panel-soft: "#f6f6f5"
  light-sidebar-bg: "#f6f6f5"
  light-ink: "#252525"
  light-muted: "#666"
  light-line: "#dededb"
  light-line-strong: "#999"
  light-primary: "#262626"
  light-primary-strong: "#111"
  light-button-ink: "#fff"
  light-selected-bg: "#eeedeb"
  light-selected-border: "#888"
  light-danger: "#a52e29"
  light-danger-bg: "#fbefed"
  light-danger-line: "#dcb6b3"
  light-success: "#28623e"
  light-success-bg: "#eef6f0"
  light-success-line: "#b7d1c0"
  light-warning: "#775315"
  light-warning-bg: "#faf4e7"
  light-warning-line: "#dcc995"
  selection-ink: "#111"
  backdrop: "#0006"
typography:
  headline:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "27px"
    fontWeight: 600
    letterSpacing: "-.02em"
  dialog-title:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "21px"
    fontWeight: 600
  title:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "17px"
    fontWeight: 600
  body:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  control:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "13px"
    fontWeight: 500
  chip:
    fontFamily: '"Segoe UI", "Microsoft YaHei UI", sans-serif'
    fontSize: "12px"
  code:
    fontFamily: '"Cascadia Mono", Consolas, monospace'
  stream:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"
    fontSize: "12px"
    lineHeight: 1.55
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  overlay: "14px"
spacing:
  option-gap: "6px"
  chip-gap: "7px"
  row-gap: "10px"
  composer: "14px"
  sidebar: "16px"
  compact: "18px"
  card: "22px"
  message: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.button-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.lg}"
    padding: "0 13px"
  button-primary-hover:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.button-ink}"
  button-neutral:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.md}"
    padding: "0 13px"
  button-disabled:
    backgroundColor: "{colors.panel-soft}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
  nav:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 10px"
  nav-selected:
    backgroundColor: "{colors.selected-bg}"
    textColor: "{colors.ink}"
  chip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.chip}"
    rounded: "{rounded.md}"
    padding: "7px 10px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "22px"
  composer:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.overlay}"
    padding: "14px"
  dialog:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.overlay}"
    padding: "22px"
  clickable-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "24px"
  button-danger:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.danger}"
    rounded: "{rounded.md}"
---

# Design System: 译禾工具合集 · 中性工作台

## Overview

**Creative North Star: "克制的对话工作台"**

用户选定的方案 A 采用接近 Codex 使用感的中性界面：简洁侧栏、宽松正文和集中弹窗。该系统覆盖工具合集全部页面、表单、任务状态、生成结果与弹窗，中文长文件名、自定义语种和多译文列保持可辨认。

`term_extractor_app/workspace_ui.py` 是唯一调色板与组件角色来源；`term_extractor_app/workspace_layout.py` 承载各页与弹窗布局，所有颜色引用语义变量；`web_app.py` 先加载布局，再追加主题。切换明暗主题只改变 token，不更换布局或启用独立旧主题规则。概念 A 只提供方向，实际源码提供数值。

**Key Characteristics:**
- 所有页面与控件共享同一套明暗语义色。
- 普通按钮保持中性，仅显式主操作使用反差填色。
- 可点击卡片仍是内容表面，使用细边框与局部悬停反馈。
- 语种、列映射与任务状态依靠清晰文字和有限功能色表达。

## Colors

### Primary

primary／primary-strong 是显式主按钮的默认／悬停填色，文字为 button-ink。普通按钮使用 panel、ink 和 line，悬停使用 selected-bg 与 line-strong；选中按钮使用 selected-border。

### Neutral

bg 承载页面，sidebar-bg 区分导航，panel 承载主要容器，panel-soft 承载辅助卡片、表头、日志、用户消息及状态底层。ink 为正文，muted 为说明；一般边线为 line，表单边框与输入区外框为 line-strong。浅色主题逐项覆盖同名变量；文档中的 light-* 只记录对应值，不是第二套组件规则。

兼容别名不建立独立颜色：text、accent → ink；panel-solid、surface-raised、glass、glass-strong → panel；surface-inset、panel-subtle → panel-soft；surface-hover、primary-soft → selected-bg；selected-line → selected-border；glass-border → line。保留 glass 名称只为兼容，实际表面不采用玻璃效果。

危险／失败／删除差异使用 danger、danger-bg、danger-line；成功／完成／新增差异使用 success 三元组；警告／暂停／已修改等使用 warning 三元组。状态同时保留文字。一般进行中的预处理状态和当前文件使用中性选中态。focus 和 selection 只用于焦点及文本选区。

**The Shared Palette Rule.** 全部页面、控件与弹窗引用同一语义调色板；禁止页面级旧主题配色分支。

**The Explicit Primary Rule.** 默认按钮为中性色面；只有明确标记的主操作使用反差填色，可点击卡片保持内容表面。

## Typography

Windows 与中文正文使用 font-ui。正文（14px／1.5），页面标题（27px／600），弹窗标题（21px／600），章节及卡片标题（17px／600）。按钮与表单（13px），按钮字重（500）；工具标签（12px），品牌（18px／600）。导航主项与子项保留（13px／12px）及缩进关系。数字指标采用等宽数字。

代码说明与正则内容有意使用 `"Cascadia Mono", Consolas, monospace`；流式输出使用 `ui-monospace, SFMono-Regular, Consolas, monospace`。这两类内容字体是功能例外，表单文本区仍服从 font-ui 覆盖。布局文件中的旧字级和圆角字面量不作为额外批准的设计 token。

## Layout

桌面外壳为（222px）侧栏加弹性主区域，主区域内边距（28px 32px），侧栏（24px 16px）。对话为（190px）会话栏加正文；正文水平留白为 `clamp(18px, 5%, 64px)`，垂直内边距（24px）。输入区与正文水平对齐。

（1100px）以内外侧栏／会话栏缩为（190px／160px），主区域内边距（22px），预处理任务布局改为单列。列映射从六列改为三列，语种按钮从第二网格列延伸至末尾。

（760px）以内外壳与对话均改为单列，主区域和消息区内边距（18px 14px），输入区外边距（10px 12px 16px）。会话侧栏最大高度（200px），内部列表最大高度（110px）并滚动。普通双列、预处理文件列表、密钥字段、请求队列与学习示例改为单列。弹窗内边距（18px），底部操作允许换行。布局文件保留各工具局部断点，服从最终主题覆盖。

标准／宽／紧凑／附件映射弹窗最大内容宽度分别为（760px／1120px／460px／640px），实际宽度限制为 `calc(100vw - 32px)`，最大高度为 `calc(100dvh - 32px)`，内容滚动。遮罩内边距（16px）。

桌面列映射为 `32px minmax(120px,1fr) 75px minmax(135px,1fr) minmax(135px,1fr) 100px`，间距（10px），行内边距（12px 0），语种按钮从第三网格列跨至末尾。窄屏为 `28px minmax(80px,1fr) 75px`，译文关系、参考信息和语种控件从第二列跨至末尾。预处理列选择使用自身三列结构。

## Elevation & Depth

普通卡片、结果、日志、预览、进度与导航均无投影。弹窗和语种／术语库浮层共同使用 shadow（值见 sidecar），遮罩使用 backdrop 且不模糊背景。滚动条使用 line-strong；进度填充为 ink，不添加发光或渐变。

**The Quiet Depth Rule.** 普通内容保持平面；弹窗与浮层共享通用阴影。

## Shapes

sm 用于状态标签与进度轨道；md 用于按钮、表单、导航和辅助容器；lg 用于主要卡片、可点击工具卡片及用户消息。输入区和弹窗使用 overlay 圆角（14px），与 lg（12px）区分。列映射保持直角、透明背景和单条底边线。

## Components

### Actions & Clickable Cards

默认按钮为 panel 背景、ink 文字和 line 边框，悬停为 selected-bg 与 line-strong。仅 `button.primary` 使用反差填色。通用按钮最小高度（36px），水平内边距（13px），悬停无位移、无阴影，颜色过渡（0.12s）。危险操作使用 danger 文字与 danger-line，悬停为 danger-bg。选中或 aria-pressed=true 使用选中背景和边框。

可点击工具卡片采用 panel 背景、ink 正文、muted 说明、lg 圆角、内边距（24px）、最小高度（180px）；悬停或键盘焦点使用 panel-soft 与 line-strong，不能采用主按钮整块反差填色。普通卡片内边距（22px）。

### Fields, Focus & Disabled States

输入框、下拉框、文本区使用 panel、ink、line-strong 和 md 圆角。单行控件最小高度（36px），内边距（8px 10px）；文本区（9px 10px）。复选／单选框（16px），颜色和范围输入最小高度（28px）。

按钮、输入框、下拉框、文本区禁用时统一为 muted 文字、panel-soft 背景、line 边框、透明度（0.65）与不可用指针。按钮、表单、summary、链接的键盘焦点共用（2px）focus 轮廓与（3px）外偏移。减少动态效果偏好会停用动画和过渡。

### Navigation, Tables & Status

导航和会话操作以透明底、无边线作为例外，当前页与会话行使用 selected-bg。表格和预览容器使用 panel，表头与行悬停使用 panel-soft。日志、辅助摘要与任务队列使用相同语义表面。状态标签和文本差异使用对应的功能色三元组，不另设页面配色。

### Conversation & Column Language

助手正文透明；用户消息为 panel-soft，工作报告为带边框的 panel。输入区使用 line-strong 外框和（14px）内边距，内部文本区无边框、透明底、最小高度（64px）。工具、附件与语种标签采用 panel 和 md 圆角；拖入状态使用 selected-bg／selected-border。

每个原文／译文列保留语种按钮；设置角色或译文关系后打开该列语种弹窗。标题明确列名与角色。候选为两列、间距（6px）、最大高度（300px）并滚动；选中项具有勾号、aria-pressed 与统一选中样式；自定义操作跨整行。搜索、已选实时说明和确认／取消保持可见。默认语种与单列覆盖明确区分，多个译文列可以对应同一个原文列。

## Do's and Don'ts

### Do:
- Do 从 workspace_ui.py 的语义 token 取色，布局文件只引用这些变量。
- Do 同时检查明暗主题中的页面、生成结果、表格、表单和弹窗。
- Do 明确区分默认按钮、显式主操作与可点击卡片。
- Do 保留键盘焦点、长文本换行、单列语种及多译文映射。

### Don't:
- Don't 为任何页面保留独立的深蓝、玻璃或硬编码旧主题颜色。
- Don't 将所有 button 元素绘制成反差主按钮。
- Don't 将工具入口卡片当作放大的主按钮。
- Don't 用装饰色混淆任务状态，或在明暗主题间更换布局。
