<template>
    <div class="login-container">
      <el-card class="login-card">
        <div class="logo-container">
          <h2>煤块检测系统</h2>
        </div>
        
        <el-form ref="loginForm" :model="loginForm" :rules="rules" label-width="0px">
          <el-form-item prop="username">
            <el-input 
              v-model="loginForm.username" 
              prefix-icon="el-icon-user" 
              placeholder="用户名"
              @keyup.enter.native="handleLogin"
            ></el-input>
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input 
              v-model="loginForm.password" 
              prefix-icon="el-icon-lock" 
              placeholder="密码" 
              show-password
              @keyup.enter.native="handleLogin"
            ></el-input>
          </el-form-item>
          
          <el-form-item>
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <el-button type="text" class="forget-password" @click="forgetPassword">忘记密码?</el-button>
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="primary" 
              class="login-button" 
              :loading="loading"
              @click="handleLogin"
            >登录</el-button>
          </el-form-item>
          
          <div class="register-link">
            <span>还没有账号?</span>
            <el-button type="text" @click="goToRegister">立即注册</el-button>
          </div>
        </el-form>
      </el-card>
    </div>
  </template>
  
  <script>
  import axios from 'axios';
  
  export default {
    name: 'LoginView',
    data() {
      return {
        loginForm: {
          username: '',
          password: ''
        },
        rules: {
          username: [
            { required: true, message: '请输入用户名', trigger: 'blur' },
            { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' }
          ],
          password: [
            { required: true, message: '请输入密码', trigger: 'blur' },
            { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
          ]
        },
        loading: false,
        rememberMe: false,
        baseUrl: process.env.VUE_APP_API_URL || 'http://localhost:5000'
      };
    },
    created() {
      // 检查本地存储的登录信息
      const savedUsername = localStorage.getItem('username');
      if (savedUsername) {
        this.loginForm.username = savedUsername;
        this.rememberMe = true;
      }
    },
    methods: {
      handleLogin() {
        this.$refs.loginForm.validate(async (valid) => {
          if (valid) {
            this.loading = true;
            
            try {
              const response = await axios.post(`${this.baseUrl}/api/auth/login`, this.loginForm);
              
              if (response.data.token) {
                // 保存token和用户信息
                localStorage.setItem('token', response.data.token);
                localStorage.setItem('user', JSON.stringify(response.data.user));
                
                // 如果勾选了"记住我"，保存用户名
                if (this.rememberMe) {
                  localStorage.setItem('username', this.loginForm.username);
                } else {
                  localStorage.removeItem('username');
                }
                
                this.$message.success('登录成功');
                
                // 跳转到首页
                this.$router.push('/Monitor');
              } else {
                this.$message.error(response.data.message || '登录失败');
              }
            } catch (error) {
              console.error('登录错误:', error);
              this.$message.error(error.response?.data?.message || '登录失败，请检查网络连接');
            } finally {
              this.loading = false;
            }
          } else {
            return false;
          }
        });
      },
      goToRegister() {
        this.$router.push('/register');
      },
      forgetPassword() {
        this.$message.info('请联系系统管理员重置密码');
      }
    }
  }
  </script>
  
  <style scoped>
  .login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    background-color: #f5f7fa;
  }
  
  .login-card {
    width: 400px;
    padding: 20px;
  }
  
  .logo-container {
    text-align: center;
    margin-bottom: 30px;
  }
  
  .logo-container h2 {
    font-size: 24px;
    color: #409EFF;
    margin: 0;
  }
  
  .login-button {
    width: 100%;
  }
  
  .register-link {
    text-align: center;
    margin-top: 20px;
    font-size: 14px;
    color: #606266;
  }
  
  .forget-password {
    float: right;
  }
  </style>