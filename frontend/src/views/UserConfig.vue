<template>
  <div class="user-config">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>⚙️ 个人配置管理</span>
          <el-button type="primary" @click="saveConfig" :loading="loading">保存配置</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="账户基础配置" name="account">
          <el-form :model="config.account" label-width="120px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="初始本金">
              <el-input-number v-model="config.account.initial_cash" :min="1000" :step="10000" />
            </el-form-item>
            <el-form-item label="券商佣金率">
              <el-input-number v-model="config.account.commission_rate" :min="0" :max="0.01" :step="0.0001" :precision="5" />
              <span class="tip">例如: 万分之2.5 为 0.00025</span>
            </el-form-item>
            <el-form-item label="印花税率">
              <el-input-number v-model="config.account.tax_rate" :min="0" :max="0.01" :step="0.0001" :precision="4" />
              <span class="tip">例如: 千分之0.5 为 0.0005 (仅卖出收取)</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="量化策略参数" name="strategy">
          <el-form :model="config.strategy" label-width="120px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="策略名称">
              <el-select v-model="config.strategy.name" placeholder="选择策略">
                <el-option label="经典双均线策略" value="dual_ma" />
                <el-option label="布林带震荡策略" value="bollinger_bands" />
                <el-option label="RSI 抄底逃顶策略" value="rsi_reversal" />
              </el-select>
            </el-form-item>
            
            <div v-if="config.strategy.name === 'dual_ma'">
              <el-form-item label="短期均线">
                <el-input-number v-model="config.strategy.parameters.fast_period" :min="2" :max="120" />
              </el-form-item>
              <el-form-item label="长期均线">
                <el-input-number v-model="config.strategy.parameters.slow_period" :min="5" :max="250" />
              </el-form-item>
            </div>
            
            <!-- Other strategy parameters can be added here -->
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="大模型(LLM)配置" name="llm">
          <el-form :model="config.llm" label-width="120px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="提供商">
              <el-input v-model="config.llm.provider" disabled />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="config.llm.api_key" type="password" show-password />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="config.llm.base_url" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="config.llm.model" />
            </el-form-item>
            <el-form-item label="预测天数">
              <el-input-number v-model="config.llm.predict_days" :min="10" :max="250" />
              <span class="tip">喂给大模型预测用的最近交易日天数</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { getUserConfig, updateUserConfig } from '../api';

const activeTab = ref('account');
const loading = ref(false);

const config = ref({
  account: {
    initial_cash: 100000,
    commission_rate: 0.00025,
    tax_rate: 0.0005
  },
  strategy: {
    name: 'dual_ma',
    parameters: {
      fast_period: 5,
      slow_period: 20
    }
  },
  llm: {
    provider: 'deepseek',
    api_key: '',
    base_url: 'https://api.deepseek.com',
    model: 'deepseek-chat',
    predict_days: 60
  }
});

const loadConfig = async () => {
  try {
    const res = await getUserConfig();
    if (res.data.status === 'success') {
      config.value = { ...config.value, ...res.data.data };
    }
  } catch (error) {
    ElMessage.error('加载配置失败');
  }
};

const saveConfig = async () => {
  loading.value = true;
  try {
    const res = await updateUserConfig(config.value);
    if (res.data.status === 'success') {
      ElMessage.success('配置保存成功');
    }
  } catch (error) {
    ElMessage.error('保存配置失败');
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadConfig();
});
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>