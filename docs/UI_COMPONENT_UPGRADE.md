# UI 组件库升级与多模型并行支持

## 📋 更新日期
2026-01-31

## 🎯 更新目标

1. ✅ 会话设置支持并行多个模型选择
2. ✅ 可以设置并行模型的从左到右排列顺序
3. ✅ 每个消息展示时显示模型名称
4. ✅ 新建对话按钮不再使用紫色
5. ✅ 使用知名 UI 组件库（Element Plus）
6. ✅ 折叠导航栏按钮移到底部，不与新建会话按钮在一起

## 📦 安装的依赖

```bash
npm install element-plus @element-plus/icons-vue vuedraggable@next
```

- **Element Plus**: Vue 3 最流行的 UI 组件库
- **@element-plus/icons-vue**: Element Plus 图标库
- **vuedraggable**: 支持拖拽排序功能

## 🔧 修改的文件

### 1. `/frontend/src/main.js`
- ✅ 引入 Element Plus 和全局注册图标组件
- ✅ 配置 Element Plus 样式

### 2. `/frontend/src/components/SessionSettingsSidebar.vue`
**主要改进：**
- ✅ 使用 Element Plus 的 `el-select` 组件支持多模型选择
- ✅ 添加 `vuedraggable` 组件支持拖拽排序模型
- ✅ 使用 `el-input-number` 替代原生数字输入框
- ✅ 使用 `el-button` 和 `el-tag` 等 Element Plus 组件
- ✅ 添加模型顺序调整区域，用户可以拖拽标签调整从左到右的显示顺序
- ✅ 后端 API 现在发送 `models` 数组而不是单个 `model`

**新增功能：**
```javascript
// 支持多模型选择
selectedModels: ref([])  // 数组支持多选

// 拖拽排序
<draggable v-model="selectedModels" ...>
```

### 3. `/frontend/src/components/MessageList.vue`
**主要改进：**
- ✅ AI 消息顶部显示模型标识徽章
- ✅ 使用 Element Plus 的 `el-tag` 组件显示模型名称
- ✅ 根据不同 provider 显示不同颜色的标签
  - OpenAI: 绿色 (success)
  - OpenRouter: 蓝色 (primary)
  - Anthropic: 橙色 (warning)
  - Google: 红色 (danger)
  - 其他: 灰色 (info)

**新增 UI 元素：**
```vue
<div class="model-badge">
  <el-tag size="small" effect="plain" :type="getModelTagType(msg.model_info.provider)">
    <el-icon><Cpu /></el-icon>
    {{ msg.model_info.name }}
  </el-tag>
</div>
```

### 4. `/frontend/src/components/SessionSidebar.vue`
**主要改进：**
- ✅ 新建对话按钮改用 Element Plus 的 `el-button` 主题色（蓝色而非紫色）
- ✅ 折叠按钮移到侧边栏底部，与滚动条区域对齐
- ✅ 会话操作按钮（编辑、删除）使用 Element Plus 的 text 按钮
- ✅ 折叠状态下显示圆形按钮

**布局结构：**
```
┌────────────────────┐
│  [新建对话]        │  ← 顶部 header
├────────────────────┤
│  会话列表 (可滚动)  │
│  - 会话1           │
│  - 会话2           │
│  ...               │
├────────────────────┤
│  [折叠]            │  ← 底部固定
└────────────────────┘
```

### 5. `/frontend/src/components/NavBar.vue`
**主要改进：**
- ✅ 使用 Element Plus 的 `el-button` 组件
- ✅ 使用 `el-tag` 显示当前配置和模型
- ✅ 使用 Element Plus 图标替代 FontAwesome
- ✅ 清空按钮使用 danger 类型（红色）

## 🎨 UI 改进效果

### 会话设置界面
- **多模型选择**: 下拉框支持多选，显示 "支持多选并行" 提示
- **模型排序**: 选择多个模型后，可以拖拽标签调整顺序
- **更现代的输入控件**: 使用 Element Plus 的数字输入框，带有增减按钮
- **统一的按钮样式**: 所有按钮使用 Element Plus 组件

### 消息列表
- **模型标识**: AI 消息顶部显示模型名称和 provider 徽章
- **颜色区分**: 不同的 AI provider 使用不同颜色的标签
- **更好的可读性**: 用户可以清楚地知道每条消息是哪个模型生成的

### 侧边栏
- **新建按钮**: 从紫色渐变改为 Element Plus 主题蓝色
- **折叠按钮**: 移到底部，更符合用户习惯
- **会话操作**: 使用 text 按钮，更简洁

## 🔄 后端兼容性

后端已经支持多模型配置：
```python
class SessionConfig(BaseModel):
    source_name: Optional[str] = None
    models: List[str] = Field(default_factory=list)  # 支持多个模型
    temperature: float = 0.7
    top_p: float = 1.0
    system_prompt: Optional[str] = None
```

前端会话设置现在发送：
```javascript
{
  source_name: "OpenRouter",
  models: ["gpt-3.5-turbo", "claude-3-opus"],  // 模型数组
  temperature: 0.7,
  top_p: 1.0
}
```

## 📝 使用说明

### 如何设置多模型并行

1. 点击顶部导航栏的 "会话设置" 按钮
2. 在 "模型选择" 下拉框中选择多个模型
3. 如果选择了多个模型，会出现 "模型顺序" 区域
4. 拖拽标签可以调整模型从左到右的显示顺序
5. 点击 "保存会话配置" 按钮

### 如何查看消息的模型信息

- 每条 AI 回复的顶部会显示一个带颜色的标签
- 标签上显示模型名称和图标
- 不同的 AI provider 有不同的颜色

### 如何折叠/展开侧边栏

- 点击侧边栏底部的 "折叠" 按钮
- 折叠后点击展开按钮恢复

## 🎯 下一步改进建议

1. **并行响应实现**: 
   - 后端需要实现真正的并行调用多个模型
   - 返回时需要标识每个响应来自哪个模型
   - 前端需要支持同时显示多个 AI 响应

2. **性能优化**:
   - 考虑使用代码分割减少首次加载大小
   - 当前构建文件较大 (2.3MB)

3. **响应式布局**:
   - 优化移动端显示
   - 添加断点适配不同屏幕尺寸

## ✅ 测试清单

- [x] 前端构建成功
- [ ] 单模型选择正常工作
- [ ] 多模型选择正常工作
- [ ] 拖拽排序功能正常
- [ ] 模型标识正确显示
- [ ] 新建按钮颜色正确
- [ ] 折叠按钮位置正确
- [ ] 所有 Element Plus 组件样式正常

## 🚀 启动测试

```bash
# 前端开发模式
cd frontend
npm run dev

# 后端启动
cd ..
python backend/main.py
```

## 📚 参考文档

- [Element Plus 官方文档](https://element-plus.org/)
- [Vue Draggable Next](https://github.com/SortableJS/vue.draggable.next)
- [Element Plus Icons](https://element-plus.org/en-US/component/icon.html)
