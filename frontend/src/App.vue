<template>
  <div v-if="$route.meta.noAuth">
    <router-view></router-view>
  </div>
  <el-container v-else class="app-container">
    <el-header class="app-header">
      <div class="logo">🚀 个人量化分析系统</div>
      <div class="user-info">
        <el-avatar size="small" icon="UserFilled" />
        <span class="username">{{ currentUsername }}</span>
        <el-tag v-if="currentRole === 'superadmin'" size="small" type="danger" style="margin-left: 5px;">管理员</el-tag>
        <el-button type="danger" link @click="handleLogout" style="margin-left: 10px;">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" class="app-aside">
        <el-menu
          :default-active="$route.path"
          class="el-menu-vertical"
          background-color="#fff"
          text-color="#303133"
          active-text-color="#409EFF"
          router
        >
          <el-menu-item index="/">
            <el-icon><DataLine /></el-icon>
            <span>量化回测总览</span>
          </el-menu-item>
          <el-menu-item index="/stocks">
            <el-icon><Wallet /></el-icon>
            <span>股票池管理</span>
          </el-menu-item>
          <el-menu-item index="/config">
            <el-icon><Setting /></el-icon>
            <span>个人配置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="app-main">
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { DataLine, Wallet, Setting, UserFilled } from '@element-plus/icons-vue'

const router = useRouter();

const currentUsername = computed(() => localStorage.getItem('username') || 'User');
const currentRole = computed(() => localStorage.getItem('role') || 'user');

const handleLogout = () => {
  localStorage.removeItem('user_id');
  localStorage.removeItem('admin_id');
  localStorage.removeItem('username');
  localStorage.removeItem('role');
  router.push('/login');
};
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f5f7fa; }
.app-container { min-height: 100vh; }
.app-header {
  background-color: #545c64;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
}
.logo { font-size: 18px; font-weight: bold; }
.user-info { display: flex; align-items: center; gap: 10px; }
.app-aside {
  background-color: #fff;
  border-right: solid 1px #e6e6e6;
}
.el-menu-vertical { border-right: none; height: 100%; }
.app-main {
  padding: 20px;
  background-color: #f0f2f5;
}
</style>