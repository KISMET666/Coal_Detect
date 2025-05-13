import axios from 'axios';

const API_URL = process.env.VUE_APP_API_URL || 'http://localhost:5000';

class AuthService {
  // 登录
  async login(username, password) {
    // 移除不必要的 try/catch
    const response = await axios.post(`${API_URL}/api/auth/login`, {
      username,
      password
    });
    
    if (response.data.token) {
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    
    return response.data;
  }
  
  // 注册
  async register(username, email, password) {
    return axios.post(`${API_URL}/api/auth/register`, {
      username,
      email,
      password
    });
  }
  
  // 登出
  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
  
  // 获取当前用户
  getCurrentUser() {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      return JSON.parse(userStr);
    }
    return null;
  }
  
  // 检查是否登录
  isLoggedIn() {
    return !!localStorage.getItem('token');
  }
  
  // 获取存储的token
  getToken() {
    return localStorage.getItem('token');
  }
}

export default new AuthService();