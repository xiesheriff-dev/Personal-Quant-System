<template>
  <div class="stock-manager">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>🗂️ 股票池管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="dialogVisible = true" plain>AI选股推荐</el-button>
            <el-button type="primary" @click="manualDialogVisible = true" plain>手动添加股票</el-button>
          </div>
        </div>
      </template>

      <el-table :data="paginatedData" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="ticker" label="股票代码" width="120" />
        <el-table-column prop="name" label="股票名称" width="150" />
        <el-table-column prop="purchase_amount" label="购买金额">
          <template #default="scope">
            ¥ {{ scope.row.purchase_amount }}
          </template>
        </el-table-column>
        <el-table-column prop="profit_amount" label="收益金额">
          <template #default="scope">
            <span :style="{ color: scope.row.profit_amount >= 0 ? '#f56c6c' : '#67c23a' }">
              ¥ {{ scope.row.profit_amount }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="profit_rate" label="收益率">
          <template #default="scope">
            <span :style="{ color: scope.row.profit_rate >= 0 ? '#f56c6c' : '#67c23a' }">
              {{ (scope.row.profit_rate * 100).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="added_at" label="添加时间" width="160">
          <template #default="scope">
            {{ scope.row.added_at ? dayjs(scope.row.added_at).format('YYYY-MM-DD HH:mm') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="420">
          <template #default="scope">
            <el-button size="small" type="info" plain @click="handleCalculateProfit(scope.row)" :loading="calculatingTickers.has(scope.row.ticker)">计算收益</el-button>
            <el-button size="small" type="primary" plain @click="openEditStatsDialog(scope.row)">编辑统计</el-button>
            <el-button size="small" type="success" plain @click="openOperationDialog(scope.row, 'BUY')">买入</el-button>
            <el-button size="small" type="warning" plain @click="openOperationDialog(scope.row, 'SELL')">卖出</el-button>
            <el-button size="small" @click="viewOperations(scope.row)">操作记录</el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(scope.row)">删除</el-button>
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
          :total="tableData.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 编辑统计弹窗 -->
    <el-dialog v-model="editStatsDialogVisible" title="编辑股票统计信息" width="400px">
      <el-form :model="editStatsForm" label-width="100px">
        <el-form-item label="股票">
          <el-input :value="currentStock?.name + ' (' + currentStock?.ticker + ')'" disabled />
        </el-form-item>
        <el-form-item label="购买金额(元)">
          <el-input-number v-model="editStatsForm.purchase_amount" :min="0" :precision="2" :step="1000" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="收益金额(元)">
          <el-input-number v-model="editStatsForm.profit_amount" :precision="2" :step="100" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="收益率">
          <el-input-number v-model="editStatsForm.profit_rate" :precision="4" :step="0.01" style="width: 100%;" />
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">例如: 0.15 表示 15%</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editStatsDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitEditStats" :loading="submittingStats">确认修改</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- AI选股弹窗 -->
    <el-dialog v-model="dialogVisible" title="AI选股推荐" width="500px" @open="fetchSectors">
      <el-form label-width="100px">
        <el-form-item label="期望价格(元)">
          <el-input-number v-model="targetPrice" :min="1" :max="2000" />
        </el-form-item>
        <el-form-item label="推荐数量(只)">
          <el-input-number v-model="recommendCount" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="偏好板块">
          <el-select
            v-model="selectedSectors"
            multiple
            filterable
            placeholder="请选择板块 (可选)"
            style="width: 100%"
            :loading="sectorsLoading"
          >
            <el-option
              v-for="item in sectorOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div style="font-size: 12px; color: #909399; margin-left: 100px;">
        AI 将根据目标价格和所选板块推荐 {{ recommendCount }} 只优质 A 股，并自动添加到股票池中。
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleRecommend" :loading="recommending">确认推荐并添加</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 手动添加弹窗 -->
    <el-dialog v-model="manualDialogVisible" title="手动添加股票" width="400px">
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="股票代码">
          <el-input v-model="manualCode" placeholder="例如: 601006" maxlength="6" />
        </el-form-item>
      </el-form>
      <div style="font-size: 12px; color: #909399; margin-left: 100px;">
        输入6位数字代码即可，系统将自动补全前缀和股票名称。
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="manualDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleManualAdd" :loading="adding">确认添加</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 股票操作记录添加弹窗 -->
    <el-dialog v-model="operationDialogVisible" :title="operationType === 'BUY' ? '买入股票' : '卖出股票'" width="400px">
      <el-form :model="operationForm" label-width="100px">
        <el-form-item label="股票">
          <el-input :value="currentStock?.name + ' (' + currentStock?.ticker + ')'" disabled />
        </el-form-item>
        <el-form-item label="操作日期">
          <el-date-picker v-model="operationForm.date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="价格(元)">
          <el-input-number v-model="operationForm.price" :min="0.01" :precision="2" :step="0.1" style="width: 100%;" @change="calcAmount" />
        </el-form-item>
        <el-form-item label="数量(股)">
          <el-input-number v-model="operationForm.quantity" :min="100" :step="100" style="width: 100%;" @change="calcAmount" />
        </el-form-item>
        <el-form-item label="总金额(元)">
          <el-input-number v-model="operationForm.amount" :min="0" :precision="2" disabled style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="operationDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitOperation" :loading="submittingOp">确认提交</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 股票操作记录列表弹窗 -->
    <el-dialog v-model="historyDialogVisible" title="操作记录" width="700px">
      <el-table :data="operationHistory" style="width: 100%" v-loading="loadingHistory">
        <el-table-column prop="operation_date" label="操作日期" width="120" />
        <el-table-column prop="operation_type" label="类型" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.operation_type === 'BUY' ? 'danger' : 'success'">
              {{ scope.row.operation_type === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格(元)" width="100" />
        <el-table-column prop="quantity" label="数量(股)" width="100" />
        <el-table-column prop="amount" label="总金额(元)" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { recommendStocks, addStock, deleteStock, getUserStocks, addStockOperation, getStockOperations, updateStockStats, calculateStockProfit, getSectors } from '../api';
import dayjs from 'dayjs';

const tableData = ref([]);
const loading = ref(false);
const calculatingTickers = ref(new Set());

// 分页相关
const currentPage = ref(1);
const pageSize = ref(10);

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return tableData.value.slice(start, end);
});

const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1;
};

const handleCurrentChange = (val) => {
  currentPage.value = val;
};

const dialogVisible = ref(false);
const targetPrice = ref(20);
const recommendCount = ref(5);
const recommending = ref(false);

const sectorOptions = ref([]);
const selectedSectors = ref([]);
const sectorsLoading = ref(false);

const fetchSectors = async () => {
  if (sectorOptions.value.length > 0) return; // 已经加载过了就不再加载
  sectorsLoading.value = true;
  try {
    const res = await getSectors();
    if (res.data.status === 'success') {
      sectorOptions.value = res.data.data;
    }
  } catch (error) {
    ElMessage.error('获取板块列表失败');
  } finally {
    sectorsLoading.value = false;
  }
};

const manualDialogVisible = ref(false);
const manualCode = ref('');
const adding = ref(false);

const editStatsDialogVisible = ref(false);
const submittingStats = ref(false);
const editStatsForm = ref({
  purchase_amount: 0,
  profit_amount: 0,
  profit_rate: 0
});

// 操作记录相关
const operationDialogVisible = ref(false);
const operationType = ref('BUY');
const currentStock = ref(null);
const submittingOp = ref(false);
const operationForm = ref({
  date: dayjs().format('YYYY-MM-DD'),
  price: 10.00,
  quantity: 100,
  amount: 1000.00
});

const historyDialogVisible = ref(false);
const operationHistory = ref([]);
const loadingHistory = ref(false);

const fetchStocks = async () => {
  loading.value = true;
  try {
    const res = await getUserStocks();
    if (res.data.status === 'success') {
      tableData.value = res.data.data;
    }
  } catch (error) {
    ElMessage.error('获取股票池失败');
  } finally {
    loading.value = false;
  }
};

const handleRecommend = async () => {
  if (!targetPrice.value) return ElMessage.warning('请输入期望价格');
  recommending.value = true;
  try {
    const res = await recommendStocks(targetPrice.value, recommendCount.value, selectedSectors.value);
    if (res.data.status === 'success') {
      ElMessage.success('推荐并添加成功！');
      dialogVisible.value = false;
      fetchStocks();
    } else {
      ElMessage.error(res.data.detail || '推荐失败');
    }
  } catch (error) {
    ElMessage.error('大模型接口请求失败');
  } finally {
    recommending.value = false;
  }
};

const handleManualAdd = async () => {
  if (!manualCode.value || manualCode.value.length !== 6) return ElMessage.warning('请输入6位正确代码');
  adding.value = true;
  try {
    const res = await addStock(manualCode.value);
    if (res.data.status === 'success') {
      ElMessage.success(res.data.detail || `成功添加: ${res.data.name}`);
      manualDialogVisible.value = false;
      manualCode.value = '';
      fetchStocks();
    } else {
      ElMessage.error(res.data.detail || '添加失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加股票失败');
  } finally {
    adding.value = false;
  }
};

const handleCalculateProfit = async (row) => {
  calculatingTickers.value.add(row.ticker);
  try {
    const res = await calculateStockProfit(row.ticker);
    if (res.data.status === 'success') {
      ElMessage.success(`计算完成: ${row.name}`);
      row.profit_amount = res.data.data.profit_amount;
      row.profit_rate = res.data.data.profit_rate;
    } else {
      ElMessage.error(res.data.detail || '计算失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '计算收益请求失败');
  } finally {
    calculatingTickers.value.delete(row.ticker);
  }
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要从股票池中删除 ${row.name}(${row.ticker}) 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await deleteStock(row.ticker);
      if (res.data.status === 'success') {
        ElMessage.success('删除成功');
        fetchStocks();
      }
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => {});
};

const openEditStatsDialog = (row) => {
  currentStock.value = row;
  editStatsForm.value = {
    purchase_amount: Number(row.purchase_amount) || 0,
    profit_amount: Number(row.profit_amount) || 0,
    profit_rate: Number(row.profit_rate) || 0
  };
  editStatsDialogVisible.value = true;
};

const submitEditStats = async () => {
  submittingStats.value = true;
  try {
    const payload = {
      purchase_amount: editStatsForm.value.purchase_amount,
      profit_amount: editStatsForm.value.profit_amount,
      profit_rate: editStatsForm.value.profit_rate,
      user_id: localStorage.getItem('user_id') || 1
    };
    const res = await updateStockStats(currentStock.value.ticker, payload);
    if (res.data.status === 'success') {
      ElMessage.success('统计信息更新成功');
      editStatsDialogVisible.value = false;
      fetchStocks();
    }
  } catch (error) {
    ElMessage.error('统计信息更新失败');
  } finally {
    submittingStats.value = false;
  }
};

const openOperationDialog = (row, type) => {
  currentStock.value = row;
  operationType.value = type;
  operationForm.value = {
    date: dayjs().format('YYYY-MM-DD'),
    price: 10.00,
    quantity: 100,
    amount: 1000.00
  };
  operationDialogVisible.value = true;
};

const calcAmount = () => {
  operationForm.value.amount = operationForm.value.price * operationForm.value.quantity;
};

const submitOperation = async () => {
  if (!operationForm.value.price || !operationForm.value.quantity) {
    return ElMessage.warning('请填写完整的操作信息');
  }
  submittingOp.value = true;
  try {
    const payload = {
      ticker: currentStock.value.ticker,
      operation_type: operationType.value,
      price: operationForm.value.price,
      quantity: operationForm.value.quantity,
      amount: operationForm.value.amount,
      operation_date: operationForm.value.date,
      user_id: localStorage.getItem('user_id') || 1
    };
    const res = await addStockOperation(payload);
    if (res.data.status === 'success') {
      ElMessage.success('操作记录添加成功');
      operationDialogVisible.value = false;
      fetchStocks(); // 刷新列表以同步最新的购买金额
    }
  } catch (error) {
    ElMessage.error('操作记录添加失败');
  } finally {
    submittingOp.value = false;
  }
};

const viewOperations = async (row) => {
  historyDialogVisible.value = true;
  loadingHistory.value = true;
  try {
    const res = await getStockOperations(row.ticker);
    if (res.data.status === 'success') {
      operationHistory.value = res.data.data;
    }
  } catch (error) {
    ElMessage.error('获取操作记录失败');
  } finally {
    loadingHistory.value = false;
  }
};

onMounted(() => {
  fetchStocks();
});
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>