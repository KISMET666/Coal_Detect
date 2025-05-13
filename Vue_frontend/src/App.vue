<template>
  <div>
    <!-- 如果是登录/注册页面，直接显示路由内容 -->
    <template v-if="isAuthPage">
      <router-view></router-view>
    </template>
    
    <!-- 否则显示带侧边栏的布局 -->
    <template v-else>
      <el-container style="height: 715px; border: 1px solid #eee">
        <el-aside width="205px" style="border: 1px solid #eee">
          <div class="user-info">
            <el-avatar :size="50" icon="el-icon-user-solid" :src="userAvatar"></el-avatar>
            <div class="user-details">
              <div class="username">{{ currentUser ? currentUser.username : '未登录' }}</div>
              <div class="actions">
                <el-dropdown @command="handleCommand">
                  <span class="el-dropdown-link">
                    操作<i class="el-icon-arrow-down el-icon--right"></i>
                  </span>
                  <el-dropdown-menu slot="dropdown">
                    <el-dropdown-item  command="logout">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </el-dropdown>
              </div>
            </div>
          </div>
          
          <el-menu router>
            <el-menu-item index="/Monitor" style="font-size:18px;text-align: center">
              <span>
                实时监测
                <el-badge v-if="isDetecting" value="录制中" class="recording-badge"></el-badge>
              </span>
            </el-menu-item>

            <el-submenu index="2" style="text-align: center">
              <template slot="title">
                <div style="font-size:18px">本地检测</div>
              </template>
              <el-menu-item index="/VDetect">
                视频检测
              </el-menu-item>  
              <el-menu-item index="/PDetect">
                图片检测
              </el-menu-item>  
            </el-submenu>
            
            <el-submenu index="3" style="text-align: center">
              <template slot="title">
                <div style="font-size:18px">日志</div>
              </template>
              <el-menu-item index="/MLog">
                监控回放
              </el-menu-item>
              <el-menu-item index="/DLogEnhanced">
                检测日志
              </el-menu-item>
            </el-submenu>
          </el-menu>
        </el-aside>
        
        <el-main>
          <!-- 路由 -->
          <router-view></router-view>
        </el-main>
      </el-container>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex';
import authService from './services/auth';

export default {
  data() {
    return {
      currentUser: null,
      userAvatar: ''
    };
  },
  computed: {
    ...mapGetters([
      'isDetecting'
    ]),
    isAuthPage() {
      return this.$route.path === '/login' || this.$route.path === '/register';
    }
  },
  created() {
    // 获取当前用户信息
    this.currentUser = authService.getCurrentUser();
    
    // 如果有用户信息，可以设置头像
    if (this.currentUser && this.currentUser.avatar) {
      this.userAvatar = this.currentUser.avatar;
    }
  },
  methods: {
    handleCommand(command) {
      switch(command) {
        case 'logout':
          this.logout();
          break;
      }
    },
    logout() {
      this.$confirm('确定要退出登录吗?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        // 执行登出逻辑
        authService.logout();
        this.$message.success('已成功退出登录');
        this.$router.push('/login');
      }).catch(() => {});
    }
  }
}
</script>

<style>
.user-info {
  display: flex;
  align-items: center;
  padding: 15px;
  border-bottom: 1px solid #ebeef5;
  background-color: #f5f7fa;
}

.user-details {
  margin-left: 10px;
  flex: 1;
}

.username {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 5px;
}

.actions {
  font-size: 12px;
  color: #409EFF;
}

.el-dropdown-link {
  cursor: pointer;
}

.recording-badge >>> .el-badge__content {
  background-color: #f56c6c;
}
</style>