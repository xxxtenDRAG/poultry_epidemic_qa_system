import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/index.css'
import './styles/desktop.css'
import './styles/mobile.css'

const app = createApp(App)
// 全局注册 Element Plus 图标（模板中直接使用 <Delete /> 等）
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, comp)
}
app.use(ElementPlus)
app.use(router)
app.mount('#app')
