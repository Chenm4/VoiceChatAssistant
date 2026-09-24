import { createApp } from 'vue'
import App from './App.vue'
import AppIcon from './components/AppIcon.vue'
import './assets/main.css'

// 引入 Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'highlight.js/styles/github.css'
import './assets/theme.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.component('AppIcon', AppIcon)
app.use(ElementPlus)
app.mount('#app')
