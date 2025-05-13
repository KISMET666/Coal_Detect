import Vue from 'vue'
import App from './App.vue'
import router from './router'
import store from './store' // 引入Vuex
import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';
import axios from 'axios'
import { apiService } from './services/api' // 导入API服务

// 注册全局API服务
Vue.prototype.$api = apiService;
Vue.prototype.$axios = axios
Vue.config.productionTip = false

Vue.use(ElementUI);

new Vue({
  router,
  store,
  render: h => h(App)
}).$mount('#app')
