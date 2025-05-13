import Vue from 'vue'
import VueRouter from 'vue-router'
import authService from '../services/auth'  // 确保路径正确
Vue.use(VueRouter)

const routes = [
  // 登录和注册路由
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/auth/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/auth/RegisterView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/Monitor',
    name: 'monitor',
    
    component: () => import('../views/monitor/MonitorView.vue')
  },
  {
    path: '/VDetect',
    name: 'videodetect',
    component: () => import('../views/detect/VideoDetect.vue')
  },
  {
    path: '/PDetect',
    name: 'photodetect',
    component: () => import('../views/detect/PhotoDetect.vue')
  },
  {
    path: '/DLogEnhanced',
    name: 'detectlogenhanced',
    component: () => import('../views/log/DetectLogEnhanced.vue')
  },
  {
    path: '/MLog',
    name: 'mlog',
    component: () => import('../views/log/MonitorLog.vue')
  },
  {
    path: '/',
    redirect: '/login'
  }
]

const router = new VueRouter({
  routes
})

// 全局前置守卫，进行登录验证
router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  const isLoggedIn = authService.isLoggedIn();
  
  // 如果需要认证且未登录，重定向到登录页
  if (requiresAuth && !isLoggedIn) {
    next('/login');
  }
  // 如果已登录，尝试访问登录或注册页，重定向到首页
  else if (isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    next('/Monitor');
  }
  // 其他情况正常跳转
  else {
    next();
  }
});

export default router
