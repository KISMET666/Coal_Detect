import axios from 'axios';
import authService from './auth';
import router from '../router';

// 创建axios实例
const instance = axios.create({
  baseURL: process.env.VUE_APP_API_URL || 'http://localhost:5000',
  timeout: 30000 // 30秒超时
});

// 请求拦截器
instance.interceptors.request.use(
  config => {
    const token = authService.getToken();
    if (token) {
      // 添加authorization头
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 响应拦截器
instance.interceptors.response.use(
  response => {
    return response;
  },
  error => {
    // 处理401错误（未授权）
    if (error.response && error.response.status === 401) {
      console.log('Token验证失败，重定向到登录页面');
      authService.logout();
      router.push('/login');
      return Promise.reject(new Error('会话已过期，请重新登录'));
    }
    
    // 处理403错误（权限不足）
    if (error.response && error.response.status === 403) {
      return Promise.reject(new Error('权限不足，无法执行此操作'));
    }
    
    return Promise.reject(error);
  }
);

// 导出默认实例
export default instance;

// 为了方便使用，也提供常用的请求方法
export const apiService = {
  get(url, params = {}) {
    return instance.get(url, { params });
  },
  
  post(url, data = {}) {
    return instance.post(url, data);
  },
  
  put(url, data = {}) {
    return instance.put(url, data);
  },
  
  delete(url) {
    return instance.delete(url);
  }
};