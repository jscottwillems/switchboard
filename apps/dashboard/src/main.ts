import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { registerOpsServiceWorker } from './pwa'
import { router } from './router'
import './styles/ops.css'

registerOpsServiceWorker()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
