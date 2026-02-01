# 新 UI 快速参考

## 🎨 配色速查

### 主色调
```css
/* 紫色渐变 - 主要强调色 */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* 深色渐变 - 专业感 */
background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
```

### 中性色
```css
/* 背景 */
background: #f8f9fa;

/* 边框 */
border-color: #e2e8f0;

/* 文字 */
color: #2d3748;
```

## 🎭 头像样式

### 用户头像
```css
width: 40px;
height: 40px;
border-radius: 12px;
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
box-shadow: 0 4px 12px rgba(102, 126, 234, 0.25);
```

### AI 头像
```css
width: 40px;
height: 40px;
border-radius: 12px;
background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
border: 2px solid #4a5568;
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
/* + 右上角绿色在线指示灯 */
```

## 💬 消息气泡

### 用户消息
```css
background: transparent;
color: #1a1a1a;
border: 2px solid #e5e7eb;
font-weight: 500;
/* 无背景色，仅边框 */
```

### AI 消息
```css
background: white;
color: #2d3748;
border: 1px solid #e2e8f0;
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
```

## 🎴 卡片样式

### 默认状态
```css
border-radius: 16px;
border: 1px solid #e2e8f0;
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
/* + 顶部 3px 紫色渐变条（悬停显示）*/
```

### 悬停状态
```css
transform: translateY(-3px);
box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
border-color: #cbd5e0;
```

### 全屏状态
```css
border: 2px solid #667eea;
box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1), 0 6px 12px rgba(0, 0, 0, 0.06);
/* 顶部 4px 紫色渐变条常驻 */
```

## 🔘 按钮样式

### 模型选择按钮（激活）
```css
border: 2px solid #667eea;
background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
color: #667eea;
box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
```

### 退出全屏按钮
```css
background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
color: white;
border: 2px solid #2d3748;
```

### 操作按钮
```css
width: 32px;
height: 32px;
border-radius: 8px;
background: rgba(255, 255, 255, 0.95);
backdrop-filter: blur(10px);
```

### 保存按钮
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
color: white;
box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
```

### 取消按钮
```css
background: #e2e8f0;
color: #475569;
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
```

## ✨ 动画参数

### 标准过渡
```css
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
```

### 悬停位移
```css
/* 按钮 */
transform: translateY(-2px);

/* 卡片 */
transform: translateY(-3px);
```

## 🌈 阴影层级

### 轻阴影（默认）
```css
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
```

### 中阴影（悬停）
```css
box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
```

### 强阴影（全屏）
```css
box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1), 0 6px 12px rgba(0, 0, 0, 0.06);
```

### 彩色阴影（紫色）
```css
box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
```

## 🎯 圆角规范

- **小圆角**：8px（操作按钮）
- **中圆角**：10px（模型按钮）、12px（头像、卡片）
- **大圆角**：16px（多模型卡片）
- **气泡圆角**：18px（消息气泡）

## 📐 间距规范

- **最小间距**：4px
- **小间距**：6px、8px
- **中间距**：12px
- **大间距**：16px、24px

## 🎨 特殊效果

### 毛玻璃
```css
backdrop-filter: blur(10px);
background: rgba(255, 255, 255, 0.95);
```

### 渐变边框（伪元素）
```css
.element::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 12px;
  padding: 2px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0.3;
}
```

### 发光效果
```css
box-shadow: 0 0 8px rgba(72, 187, 120, 0.6);
```

### 顶部装饰条
```css
.card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  opacity: 0;
  transition: opacity 0.3s;
}

.card:hover::before {
  opacity: 1;
}
```

## 🎪 使用示例

### 创建紫色主题按钮
```css
.my-button {
  padding: 8px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.my-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}
```

### 创建高级卡片
```css
.my-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.my-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  opacity: 0;
  transition: opacity 0.3s;
}

.my-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04);
  border-color: #cbd5e0;
}

.my-card:hover::before {
  opacity: 1;
}
```

## 🔍 调试技巧

### 检查阴影层次
在浏览器开发者工具中，使用 3D 视图可以清楚看到阴影的层次效果。

### 验证渐变
使用 CSS 渐变生成器验证渐变颜色是否正确。

### 测试动画
调整 `transition-duration` 到 1s 或 2s 来慢速查看动画效果。

### 对比颜色
使用在线对比度检查工具确保文字可读性。

## 💡 最佳实践

1. **保持一致性**：使用统一的圆角、间距、阴影
2. **适度使用动画**：不要过度使用，保持流畅
3. **注意性能**：使用 transform 而非 position
4. **考虑可访问性**：确保足够的对比度
5. **响应式设计**：在不同屏幕尺寸下测试
