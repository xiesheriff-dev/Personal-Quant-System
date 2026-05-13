<template>
  <div class="dashboard">
    <el-card class="box-card">
      <template #header>
        <div class="controls">
          <div class="date-picker-group">
            <span class="label">模拟区间:</span>
            <el-date-picker
              v-model="startDate"
              type="date"
              placeholder="开始日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              :clearable="false"
              style="width: 140px;"
            />
            <span style="margin: 0 5px; color: #606266;">至</span>
            <el-date-picker
              v-model="endDate"
              type="date"
              placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              :clearable="false"
              style="width: 140px;"
            />
            <el-button type="primary" @click="fetchData" :loading="loading" style="padding: 8px 15px;">搜索</el-button>
          </div>
          <div class="button-group">
            <el-button type="success" @click="advance30Days">前进 30 天 ⏩</el-button>
            <el-button type="warning" :loading="loading" @click="fetchData(true)">刷新数据</el-button>
          </div>
        </div>
      </template>

      <el-table :data="tableData" style="width: 100%" v-loading="loading" @row-click="goToDetail" stripe>
        <el-table-column prop="ticker" label="股票代码" width="120" />
        <el-table-column prop="name" label="股票名称" width="180" />
        <el-table-column prop="strategy" label="量化策略" width="120" />
        <el-table-column prop="final_equity" label="期末净值">
          <template #default="scope">
            <span style="font-weight: bold">{{ scope.row.final_equity }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="return_rate" label="收益率">
          <template #default="scope">
            <span :style="{ color: scope.row.return_rate >= 0 ? '#f56c6c' : '#67c23a' }">
              {{ scope.row.return_rate }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="trade_count" label="交易次数" width="100" />
        <el-table-column prop="advice" label="购买建议" width="240">
          <template #default="scope">
            <div class="advice-cell" v-if="scope.row.advice !== '暂无建议'">
              <el-tag :type="getAdviceType(scope.row.advice)" size="small" effect="plain">
                {{ scope.row.advice }}
              </el-tag>
            </div>
            <span v-else style="color: #999; font-size: 12px;">暂无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button size="small" @click.stop="goToDetail(scope.row)">详情下钻</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :default-page-size="10"
          layout="total, sizes, prev, pager, next, jumper"
          :total="totalCount"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
      
      <div class="tip">💡 提示：点击行可进入该股票的详细 K 线回测页面</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getSummary } from '../api';
import { ElMessage } from 'element-plus';
import dayjs from 'dayjs';

const router = useRouter();
const initialEndDate = dayjs().format('YYYYMMDD');
const initialStartDate = dayjs().subtract(30, 'day').format('YYYYMMDD');
const startDate = ref(initialStartDate);
const endDate = ref(initialEndDate);
const loading = ref(false);
const tableData = ref([]);
const totalCount = ref(0);

// 分页相关
const currentPage = ref(1);
const pageSize = ref(10);

const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1;
  fetchData();
};

const handleCurrentChange = (val) => {
  currentPage.value = val;
  fetchData();
};

const getAdviceType = (advice) => {
  if (advice.includes('强烈买入') || advice.includes('建议买入')) return 'danger';
  if (advice.includes('谨慎买入') || advice.includes('持有')) return 'warning';
  if (advice.includes('减仓') || advice.includes('清仓') || advice.includes('卖出')) return 'success';
  return 'info';
};

// 核心逻辑：时间轴一次前进 30 天
const advance30Days = () => {
  const currentEnd = dayjs(endDate.value);
  // 起始日期变为上次的结束日期 + 1天
  const nextStart = currentEnd.add(1, 'day');
  // 结束日期往后推 30 天
  const nextEnd = nextStart.add(30, 'day');
  
  startDate.value = nextStart.format('YYYYMMDD');
  endDate.value = nextEnd.format('YYYYMMDD');
  fetchData(); // 自动触发回测
};

const fetchData = async (refresh = false) => {
  loading.value = true;
  try {
    // 调用 api/index.js 中修改好的方法，并传入日期和分页参数
    const res = await getSummary(startDate.value, endDate.value, refresh, currentPage.value, pageSize.value);
    
    // 如果该时间段内完全没有符合条件的数据，清空表格
    if (!res.data.data || res.data.data.length === 0) {
      tableData.value = [];
      totalCount.value = 0;
      ElMessage.warning('当前时间区间内数据不足或无交易记录');
    } else {
      tableData.value = res.data.data;
      totalCount.value = res.data.total || 0;
    }
  } catch (error) {
    ElMessage.error('获取后端数据失败，请检查 Python 服务是否运行');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const goToDetail = (row) => {
  router.push({
    path: `/stock/${row.ticker}`,
    query: { start: startDate.value, end: endDate.value } // 新增 query 传参
  });
};

onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.dashboard { padding: 20px; max-width: 1400px; margin: 0 auto; }
.controls { display: flex; justify-content: space-between; align-items: center; }
.date-picker-group { display: flex; align-items: center; gap: 10px; }
.label { font-size: 14px; font-weight: bold; color: #606266; }
.button-group { display: flex; gap: 10px; }
.pagination-container { display: flex; justify-content: flex-end; margin-top: 20px; }
.tip { margin-top: 15px; font-size: 13px; color: #909399; text-align: center; }
.advice-cell { white-space: nowrap; }
:deep(.el-table__row) { cursor: pointer; }
</style>
