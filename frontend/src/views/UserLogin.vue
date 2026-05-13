<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>用户登录</h2>
        </div>
      </template>
      <el-form :model="form" @keyup.enter="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="请输入用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="login-button" @click="handleLogin" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>
      <div class="switch-role">
        <el-link type="info" @click="$router.push('/admin/login')">管理员登录入口</el-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { userLogin } from '../api';

const router = useRouter();
const form = ref({ username: '', password: '' });
const loading = ref(false);

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码');
    return;
  }
  loading.value = true;
  try {
    const res = await userLogin(form.value.username, form.value.password);
    if (res.data.status === 'success') {
      ElMessage.success('登录成功');
      localStorage.setItem('user_id', res.data.user_id);
      localStorage.setItem('username', res.data.username);
      localStorage.setItem('role', res.data.role);
      router.push('/');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败，请检查网络或账号密码');
  } finally {
    loading.value = false;
  }
};
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
}
.card-header h2 {
  margin: 0;
  text-align: center;
  color: #409EFF;
}
.login-button {
  width: 100%;
}
.switch-role {
  text-align: right;
  margin-top: 10px;
}
</style>
