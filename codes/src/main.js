import { createApp } from 'vue'
import './assets/style.css'
import 'nprogress/nprogress.css'
import './assets/nprogress-mistral.css'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
