<template>
    <div class="register-container">
      <el-card class="register-card">
        <div class="logo-container">
          <h2>煤块检测系统</h2>
          <p>用户注册</p>
        </div>
        
        <el-form ref="registerForm" :model="registerForm" :rules="rules" label-width="0px">
          <el-form-item prop="username">
            <el-input 
              v-model="registerForm.username" 
              prefix-icon="el-icon-user" 
              placeholder="用户名"
            ></el-input>
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input 
              v-model="registerForm.password" 
              prefix-icon="el-icon-lock" 
              placeholder="密码" 
              show-password
            ></el-input>
          </el-form-item>
          
          <el-form-item prop="confirmPassword">
            <el-input 
              v-model="registerForm.confirmPassword" 
              prefix-icon="el-icon-lock" 
              placeholder="确认密码" 
              show-password
            ></el-input>
          </el-form-item>
          
          <el-form-item prop="email">
            <el-input 
              v-model="registerForm.email" 
              prefix-icon="el-icon-message" 
              placeholder="电子邮箱"
            ></el-input>
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="primary" 
              class="register-button" 
              :loading="loading"
              @click="handleRegister"
            >注册</el-button>
          </el-form-item>
          
          <div class="login-link">
            <span>已有账号?</span>
            <el-button type="text" @click="goToLogin">返回登录</el-button>
          </div>
        </el-form>
      </el-card>
    </div>
  </template>
  
  <script>
  import axios from 'axios';
  
  export default {
    name: 'RegisterView',
    data() {
      // 自定义验证器：确认密码
      const validateConfirmPassword = (rule, value, callback) => {
        if (value !== this.registerForm.password) {
          callback(new Error('两次输入的密码不一致'));
        } else {
          callback();
        }
      };
      
      return {
        registerForm: {
          username: '',
          password: '',
          confirmPassword: '',
          email: ''
        },
        rules: {
          username: [
            { required: true, message: '请输入用户名', trigger: 'blur' },
            { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' }
          ],
          password: [
            { required: true, message: '请输入密码', trigger: 'blur' },
            { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
          ],
          confirmPassword: [
            { required: true, message: '请确认密码', trigger: 'blur' },
            { validator: validateConfirmPassword, trigger: 'blur' }
          ],
          email: [
            { required: true, message: '请输入电子邮箱', trigger: 'blur' },
            { type: 'email', message: '请输入有效的电子邮箱地址', trigger: 'blur' }
          ]
        },
        loading: false,
        baseUrl: process.env.VUE_APP_API_URL || 'http://localhost:5000'
      };
    },
    methods: {
      handleRegister() {
        this.$refs.registerForm.validate(async (valid) => {
          if (valid) {
            this.loading = true;
            
            try {
              // 准备注册数据，忽略确认密码字段
              const { confirmPassword, ...registerData } = this.registerForm;
              
              const response = await axios.post(`${this.baseUrl}/api/auth/register`, registerData);
              
              if (response.data.success) {
                this.$message.success('注册成功，请登录');
                this.$router.push('/login');
              } else {
                this.$message.error(response.data.message || '注册失败');
              }
            } catch (error) {
              console.error('注册错误:', error);
              this.$message.error(error.response?.data?.message || '注册失败，请检查网络连接');
            } finally {
              this.loading = false;
            }
          } else {
            return false;
          }
        });
      },
      goToLogin() {
        this.$router.push('/login');
      }
    }
  }
  </script>
  
  <style scoped>
  .register-container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    background-color: #f5f7fa;
  }
  
  .register-card {
    width: 400px;
    padding: 20px;
  }
  
  .logo-container {
    text-align: center;
    margin-bottom: 20px;
  }
  
  .logo-container h2 {
    font-size: 24px;
    color: #409EFF;
    margin: 0;
  }
  
  .logo-container p {
    margin: 5px 0 0;
    color: #606266;
  }
  
  .register-button {
    width: 100%;
  }
  
  .login-link {
    text-align: center;
    margin-top: 20px;
    font-size: 14px;
    color: #606266;
  }
  </style>