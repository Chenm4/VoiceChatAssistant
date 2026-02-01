# 代码块空白间距修复

## 📋 更新日期
2026-01-31

## 🐛 问题描述

### 用户反馈
代码块上下有很多空白间距，HTML结构出现嵌套问题：

```html
<!-- 错误的嵌套结构 ❌ -->
<pre><code class="language-python">
  <div class="code-block-wrapper">
    <button class="copy-button">...</button>
    <pre class="hljs"><code>...</code></pre>
  </div>
</code></pre>
```

**问题**：
- 外层有 `<pre><code>`（markdown-it 自动添加）
- 内层又有 `<pre><code>`（highlight 函数返回）
- 导致嵌套和额外空白

## 🔍 根本原因

### 旧实现（错误）❌

```javascript
const md = new MarkdownIt({
  highlight: function (str, lang) {
    // 返回完整的 HTML 结构
    return `<div class="code-block-wrapper">
      <button class="copy-button">...</button>
      <pre class="hljs"><code>${highlighted}</code></pre>
    </div>`
  }
})
```

**问题**：
1. `highlight` 函数返回完整 HTML
2. markdown-it **自动包装**返回值在 `<pre><code>` 中
3. 结果：双层 `<pre><code>` 嵌套 ❌

### markdown-it 的默认行为

```javascript
// markdown-it 内部逻辑（简化）
function renderCodeBlock(code, lang) {
  const highlighted = options.highlight(code, lang)  // 调用我们的函数
  return `<pre><code class="${lang}">${highlighted}</code></pre>`  // 自动包装！
}
```

所以我们的返回值被包装成：
```html
<pre><code class="language-python">
  <!-- 我们返回的 HTML -->
  <div class="code-block-wrapper">
    <pre class="hljs"><code>...</code></pre>
  </div>
</code></pre>
```

## ✅ 修复方案

### 自定义 fence 渲染规则

不使用 `highlight` 选项，而是直接覆盖 `fence` 渲染规则：

```javascript
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
  // ❌ 不再使用 highlight 选项
})

// ✅ 自定义 fence 渲染规则（完全控制输出）
md.renderer.rules.fence = function (tokens, idx) {
  const token = tokens[idx]
  const code = token.content
  const lang = token.info.trim()
  
  // 高亮代码
  let highlighted
  if (lang && hljs.getLanguage(lang)) {
    try {
      highlighted = hljs.highlight(code, { language: lang }).value
    } catch (__) {
      highlighted = md.utils.escapeHtml(code)
    }
  } else {
    highlighted = md.utils.escapeHtml(code)
  }
  
  // 直接返回完整的 HTML 结构（不会被再次包装）
  return `<div class="code-block-wrapper">
  <button class="copy-button" onclick="copyCode(event)"><i class="fas fa-copy"></i></button>
  <pre class="hljs"><code>${highlighted}</code></pre>
</div>`
}
```

### 新的 HTML 结构（正确）✅

```html
<!-- 单层结构，没有嵌套 ✅ -->
<div class="code-block-wrapper">
  <button class="copy-button">
    <i class="fas fa-copy"></i>
  </button>
  <pre class="hljs">
    <code>
      <span class="hljs-keyword">def</span> ...
    </code>
  </pre>
</div>
```

## 🆚 对比

### 修复前（嵌套）❌

```html
<pre><code class="language-python">
  <div class="code-block-wrapper">
    <button class="copy-button">...</button>
    <pre class="hljs"><code>
      <span class="hljs-keyword">def</span> ...
    </code></pre>
  </div>
</code></pre>
```

**问题**：
- 双层 `<pre>` 和 `<code>` 标签
- 外层 `<pre><code>` 的默认样式导致额外空白
- CSS 样式冲突

### 修复后（扁平）✅

```html
<div class="code-block-wrapper">
  <button class="copy-button">...</button>
  <pre class="hljs"><code>
    <span class="hljs-keyword">def</span> ...
  </code></pre>
</div>
```

**优势**：
- ✅ 单层结构，干净清晰
- ✅ 没有额外空白
- ✅ CSS 样式完全可控

## 🔧 技术细节

### markdown-it 渲染器规则

markdown-it 使用 **渲染器规则** 来控制不同 token 的 HTML 输出：

```javascript
// fence = 代码块
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  // tokens: 所有 token 列表
  // idx: 当前 token 的索引
  return '<your-html>'
}
```

**关键**：
- 直接覆盖 `fence` 规则 = 完全控制输出
- 不会被 markdown-it 再次包装
- 避免嵌套问题

### Token 结构

```javascript
token = {
  type: 'fence',
  content: 'def hello():\n    print("world")',  // 原始代码
  info: 'python',  // 语言标识
  // ...
}
```

### 高亮逻辑

```javascript
// 1. 检查语言是否支持
if (lang && hljs.getLanguage(lang)) {
  // 2. 尝试高亮
  try {
    highlighted = hljs.highlight(code, { language: lang }).value
  } catch (__) {
    // 3. 失败则转义
    highlighted = md.utils.escapeHtml(code)
  }
} else {
  // 4. 不支持的语言，直接转义
  highlighted = md.utils.escapeHtml(code)
}
```

## 📊 CSS 影响

### 之前的样式问题

```css
/* 外层 <pre> 的默认样式 */
pre {
  margin: 1em 0;  /* 上下外边距 */
  padding: 1em;   /* 内边距 */
}

/* 内层 <pre class="hljs"> 的样式 */
.hljs {
  background: #1e1e1e;
  padding: 1rem;
}

/* 结果：双倍 padding 和 margin！❌ */
```

### 现在的样式（正常）

```css
/* 只有一个 <pre class="hljs"> */
.hljs {
  background: #1e1e1e;
  padding: 0.75rem;  /* 按预期工作 ✅ */
}

.code-block-wrapper {
  position: relative;
  margin: 0.5rem 0;  /* 控制代码块间距 ✅ */
}
```

## 🚀 测试验证

### 1. 启动应用
```bash
./start.sh
```

### 2. 发送包含代码的消息
```markdown
请展示一个 Python 排序算法：

​```python
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
​```
```

### 3. 检查渲染结果

#### ✅ 应该看到：
- 代码块上下空白适中（0.5rem）
- 代码与边框距离正常（0.75rem）
- 复制按钮正确定位在右上角
- 语法高亮正常显示

#### ❌ 不应该看到：
- 代码块上下大量空白
- 代码被多层边框包围
- 奇怪的缩进或对齐问题

### 4. 检查 HTML 结构

在浏览器开发者工具中：
1. 右键点击代码块 → "检查元素"
2. 查看 HTML 结构

**应该看到**：
```html
<div class="code-block-wrapper">
  <button class="copy-button">...</button>
  <pre class="hljs"><code>...</code></pre>
</div>
```

**不应该看到**：
```html
<pre><code>
  <div class="code-block-wrapper">...</div>
</code></pre>
```

## 📝 修改文件

- `/frontend/src/utils/markdown.js` - Markdown 渲染逻辑

### 关键改动

```diff
- const md = new MarkdownIt({
-   highlight: function (str, lang) {
-     return `<div>...</div>`  // ❌ 会被包装
-   }
- })

+ const md = new MarkdownIt({
+   html: true,
+   linkify: true,
+   typographer: true
+ })
+ 
+ md.renderer.rules.fence = function (tokens, idx) {
+   return `<div>...</div>`  // ✅ 不会被包装
+ }
```

## 💡 经验总结

### 1. markdown-it 的陷阱
- `highlight` 选项返回的内容**会被包装**
- 使用自定义渲染规则可以**完全控制输出**

### 2. 调试方法
- 检查 HTML 结构（开发者工具）
- 查看是否有意外的嵌套
- 检查 CSS 样式是否被覆盖

### 3. 最佳实践
- 需要完全控制输出 → 自定义渲染规则
- 只需要语法高亮 → 使用 `highlight` 选项
- 复杂的 HTML 结构 → 必须用自定义规则

## 🔗 相关资源

- [markdown-it 文档](https://github.com/markdown-it/markdown-it)
- [highlight.js 文档](https://highlightjs.org/)
- [自定义渲染器规则](https://github.com/markdown-it/markdown-it/blob/master/docs/architecture.md#renderer)

## 🎉 总结

**问题**：`highlight` 函数返回的 HTML 被 markdown-it 自动包装，导致嵌套和额外空白 ❌

**修复**：使用 `md.renderer.rules.fence` 自定义渲染规则，完全控制输出 ✅

**结果**：
- ✅ 干净的 HTML 结构
- ✅ 没有额外空白
- ✅ CSS 样式按预期工作
- ✅ 代码块显示正常

现在代码块的空白间距完全正常了！🎉
