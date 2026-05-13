<template>
  <div class="detail-container">
    <div class="header">
      <div class="header-top">
        <div class="left-controls">
          <el-button @click="goBack" type="info" plain icon="ArrowLeft">返回总览</el-button>
          <el-date-picker
            v-model="startDate"
            type="date"
            placeholder="开始日期"
            value-format="YYYYMMDD"
            :clearable="false"
            style="width: 130px;"
            @change="handleSearch"
            size="default"
          />
          <span style="color: #606266;">至</span>
          <el-date-picker
            v-model="endDate"
            type="date"
            placeholder="结束日期"
            value-format="YYYYMMDD"
            :clearable="false"
            style="width: 130px;"
            @change="handleSearch"
            size="default"
          />
        </div>
        <div class="right-controls">
          <h2 class="ticker-title" :title="`标的详情: ${ticker}${metadata.stock_name ? ' (' + metadata.stock_name + ')' : ''}`">
            标的详情: {{ ticker }}{{ metadata.stock_name ? ' (' + metadata.stock_name + ')' : '' }}
          </h2>
          <div class="predict-buttons">
            <el-button type="danger" @click="handlePredict" :loading="predicting" :disabled="loading || visibleCount === 0">行情预测</el-button>
            <el-button type="warning" @click="handleOpenPredictList" plain>历史预测列表</el-button>
            <el-button type="primary" plain @click="handleRefresh" :disabled="loading">刷新数据</el-button>
            <span class="progress-text" style="margin-left: 0; background: #131722; padding: 0 15px; height: 32px; border-radius: 8px; border: 1px solid #2B3139;">数据天数: {{ totalDays }} 天</span>
          </div>
        </div>
      </div>
    </div>

    <div class="stats-panel" v-if="metadata.total_return !== undefined" v-loading="loading">
      <div class="stat-box"><div class="stat-label">期末净值</div><div class="stat-value" :class="metadata.final_equity >= metadata.initial_cash ? 'red' : 'green'">¥{{ metadata.final_equity }}</div></div>
      <div class="stat-box"><div class="stat-label">累计收益率</div><div class="stat-value" :class="metadata.total_return >= 0 ? 'red' : 'green'">{{ metadata.total_return }}%</div></div>
      <div class="stat-box"><div class="stat-label">最大回撤</div><div class="stat-value green">{{ metadata.max_drawdown }}%</div></div>
      <div class="stat-box"><div class="stat-label">夏普比率</div><div class="stat-value">{{ metadata.sharpe_ratio }}</div></div>
      <div class="stat-box"><div class="stat-label">交易胜率</div><div class="stat-value">{{ metadata.win_rate }}%</div></div>
      <div class="stat-box"><div class="stat-label">盈亏比</div><div class="stat-value">{{ metadata.pnl_ratio }}</div></div>
    </div>

    <div class="charts-wrapper" v-loading="loading" style="position: relative;">
      <!-- K线信息悬浮窗 -->
      <div v-show="crosshairInfo" class="crosshair-tooltip">
        <div class="tooltip-date">{{ crosshairInfo?.time }}</div>
        <div class="tooltip-grid">
          <div class="tooltip-item">
            <span class="label">开盘</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.open?.toFixed(2) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">收盘</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.close?.toFixed(2) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">最高</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.high?.toFixed(2) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">最低</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.low?.toFixed(2) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">涨跌幅</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.pct_change > 0 ? '+' : '' }}{{ crosshairInfo?.pct_change?.toFixed(2) }}%</span>
          </div>
          <div class="tooltip-item">
            <span class="label">涨跌额</span>
            <span class="value" :class="getPriceColor(crosshairInfo?.pct_change)">{{ crosshairInfo?.change_amount > 0 ? '+' : '' }}{{ crosshairInfo?.change_amount?.toFixed(2) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">成交额</span>
            <span class="value text-white">{{ formatAmount(crosshairInfo?.amount) }}</span>
          </div>
          <div class="tooltip-item">
            <span class="label">换手率</span>
            <span class="value text-white">{{ crosshairInfo?.turnover?.toFixed(2) }}%</span>
          </div>
          <div class="tooltip-item">
            <span class="label">振幅</span>
            <span class="value text-white">{{ crosshairInfo?.amplitude?.toFixed(2) }}%</span>
          </div>
        </div>
      </div>

      <div ref="klineChartRef" class="main-chart"></div>
      <div ref="equityChartRef" class="sub-chart"></div>
    </div>

    <div class="logs-wrapper" v-loading="loading">
      <h3 class="logs-title">📝 已触发交易日志 ({{ visibleLogs.length }} 笔操作)</h3>
      <el-table :data="visibleLogs" style="width: 100%" height="250" class="dark-table" size="small">
        <el-table-column prop="timestamp" label="交易时间" width="120" />
        <el-table-column prop="action" label="动作" width="80">
          <template #default="scope">
            <span :class="scope.row.action === '买入' ? 'text-red' : 'text-green'">{{ scope.row.action }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="成交价" />
        <el-table-column prop="shares" label="股数" />
        <el-table-column prop="fee" label="摩擦成本" />
        <el-table-column prop="reason" label="触发原因" />
      </el-table>
    </div>

    <!-- 预测结果与对话弹窗 -->
    <el-dialog v-model="predictDialogVisible" title="大模型预测分析与问答" width="840px">
      <div v-loading="predicting" class="chat-container">
        <el-alert v-if="isCached" title="⚡ 首次预测结果已从本地数据库缓存加载" type="success" :closable="false" style="margin-bottom: 15px;" />
        
        <div class="chat-messages" ref="chatMessagesRef">
          <div v-for="(msg, index) in chatMessages" :key="index" :class="['chat-message', msg.role]">
            <div class="message-avatar">{{ msg.role === 'assistant' ? '🤖' : '👤' }}</div>
            <div class="message-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
          </div>
          
          <div v-if="chatting" class="chat-message assistant">
            <div class="message-avatar">🤖</div>
            <div class="message-content">思考中...</div>
          </div>
          
          <div v-if="!predicting && chatMessages.length === 0" style="color: #999; text-align: center; padding: 40px 20px;">
            预测中，请稍候...
          </div>
        </div>

        <div class="chat-input-area" v-if="chatMessages.length > 0">
          <el-input 
            v-model="chatInput" 
            type="textarea" 
            :rows="2" 
            placeholder="关于该标的的预测，有什么想问的？(按 Ctrl+Enter 发送)" 
            @keydown.ctrl.enter="sendChatMessage"
          />
          <el-button type="primary" @click="sendChatMessage" :loading="chatting" style="margin-left: 10px; height: 52px;">
            发送
          </el-button>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="predictDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 历史预测列表弹窗 -->
    <el-dialog v-model="predictListDialogVisible" title="历史预测列表" width="500px">
      <el-table :data="predictList" v-loading="loadingPredictList" height="400" border stripe style="width: 100%">
        <el-table-column prop="date" label="预测日期" min-width="130" sortable align="center" />
        <el-table-column prop="advice" label="预测建议" min-width="120" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.advice.includes('买入') ? 'danger' : (scope.row.advice.includes('卖出') || scope.row.advice.includes('减仓') ? 'success' : 'info')">
              {{ scope.row.advice }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" link @click="viewFullPrediction(scope.row)">查看完整</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 查看完整预测弹窗 -->
    <el-dialog v-model="fullPredictDialogVisible" title="完整预测内容" width="600px">
      <div class="markdown-body" v-html="parsedFullPredictResult"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { getStockDetail, predictStock, getPredictList, chatWithLLM } from '../api';
import { createChart } from 'lightweight-charts';
import { ElMessage } from 'element-plus';
import dayjs from 'dayjs';
import { marked } from 'marked';

const props = defineProps(['ticker']);
const router = useRouter();
const route = useRoute();

const loading = ref(true);
const metadata = ref({});

const startOfMonth = dayjs().startOf('month').format('YYYYMMDD');
const endOfMonth = dayjs().endOf('month').format('YYYYMMDD');
const startDate = ref(route.query.start || startOfMonth);
const endDate = ref(route.query.end || endOfMonth);

// 🌟 核心引擎内存：存放后端的全量数据
let fullKlineData = [];
let fullEquityData = [];
let fullMarkers = [];
let fullLogs = [];

// 🌟 十字光标（鼠标悬浮）数据
const crosshairInfo = ref(null);

const getPriceColor = (pct_change) => {
  if (!pct_change) return 'text-white';
  return pct_change >= 0 ? 'text-red' : 'text-green';
};

const formatAmount = (val) => {
  if (!val) return '0';
  if (val >= 100000000) return (val / 100000000).toFixed(2) + '亿';
  if (val >= 10000) return (val / 10000).toFixed(2) + '万';
  return val.toFixed(2);
};

// 🌟 时空游标：当前展示的数据量
const visibleCount = ref(0);
const totalDays = ref(0);
const visibleLogs = ref([]); // 动态显示的日志

// 🌟 预测相关状态
const predicting = ref(false);
const predictDialogVisible = ref(false);
const predictResult = ref('');
const isCached = ref(false);

// 🌟 对话相关状态
const chatMessages = ref([]);
const chatInput = ref('');
const chatting = ref(false);
const chatMessagesRef = ref(null);

const renderMarkdown = (text) => {
  return text ? marked(text) : '';
};

const scrollToBottom = async () => {
  await nextTick();
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight;
  }
};

const scrollToTop = async () => {
  await nextTick();
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = 0;
  }
};

const sendChatMessage = async () => {
  const content = chatInput.value.trim();
  if (!content || chatting.value) return;

  chatMessages.value.push({ role: 'user', content });
  chatInput.value = '';
  chatting.value = true;
  await scrollToBottom();

  try {
    const res = await chatWithLLM(props.ticker, chatMessages.value);
    if (res.data.status === 'success') {
      chatMessages.value.push({ role: 'assistant', content: res.data.reply });
    } else {
      ElMessage.error('对话失败：' + res.data.detail);
      chatMessages.value.pop(); // 回退用户的消息
    }
  } catch (error) {
    console.error(error);
    ElMessage.error('请求接口异常：' + (error.response?.data?.detail || error.message));
    chatMessages.value.pop();
  } finally {
    chatting.value = false;
    await scrollToBottom();
  }
};

// 🌟 预测列表相关状态
const predictListDialogVisible = ref(false);
const predictList = ref([]);
const loadingPredictList = ref(false);
const fullPredictDialogVisible = ref(false);
const currentFullPrediction = ref('');

const parsedPredictResult = computed(() => {
  return predictResult.value ? marked(predictResult.value) : '';
});

const parsedFullPredictResult = computed(() => {
  return currentFullPrediction.value ? marked(currentFullPrediction.value) : '';
});

const handleOpenPredictList = async () => {
  predictListDialogVisible.value = true;
  loadingPredictList.value = true;
  try {
    const res = await getPredictList(props.ticker);
    if (res.data.status === 'success') {
      predictList.value = res.data.data;
    } else {
      ElMessage.error('获取预测列表失败：' + res.data.detail);
    }
  } catch (error) {
    console.error(error);
    ElMessage.error('请求接口异常：' + (error.response?.data?.detail || error.message));
  } finally {
    loadingPredictList.value = false;
  }
};

const viewFullPrediction = (row) => {
  currentFullPrediction.value = row.full_prediction;
  fullPredictDialogVisible.value = true;
};

const handlePredict = async () => {
  if (visibleCount.value === 0 || fullKlineData.length === 0) {
    ElMessage.warning('当前暂无K线数据，无法预测');
    return;
  }
  
  const currentEndDate = endDate.value;
  const currentStartDate = startDate.value; 

  predictDialogVisible.value = true;
  predicting.value = true;
  predictResult.value = '';
  isCached.value = false;
  chatMessages.value = [];
  chatInput.value = '';

  try {
    const res = await predictStock(props.ticker, currentStartDate, currentEndDate);
    if (res.data.status === 'success') {
      predictResult.value = res.data.prediction;
      isCached.value = res.data.cached || false;
      // 将初始预测报告作为对话的起始内容
      chatMessages.value.push({ role: 'assistant', content: res.data.prediction });
      await scrollToTop();
    } else {
      predictResult.value = '预测失败：' + res.data.detail;
    }
  } catch (error) {
    console.error(error);
    predictResult.value = '请求大模型异常：' + (error.response?.data?.detail || error.message);
  } finally {
    predicting.value = false;
  }
};

const klineChartRef = ref(null);
const equityChartRef = ref(null);
let klineChart = null;
let equityChart = null;
let candlestickSeries = null;
let areaSeries = null;

const goBack = () => router.push('/');

const darkThemeOptions = {
  layout: { background: { color: '#131722' }, textColor: '#d1d4dc' },
  grid: { vertLines: { color: '#2B3139' }, horzLines: { color: '#2B3139' } },
  timeScale: { borderColor: '#2B3139' },
  rightPriceScale: { borderColor: '#2B3139' },
  localization: {
    dateFormat: 'yyyy-MM-dd',
  },
};

// 🌟 数据切片渲染引擎
const renderSlice = () => {
  if (!candlestickSeries || !areaSeries) return;

  // 1. 切割图表数据
  const currentKlines = fullKlineData.slice(0, visibleCount.value);
  const currentEquity = fullEquityData.slice(0, visibleCount.value);
  
  // 2. 切割 Markers（只显示在当前时间轴内的箭头）
  if (currentKlines.length > 0) {
    const lastVisibleDate = new Date(currentKlines[currentKlines.length - 1].time).getTime();
    const currentMarkers = fullMarkers.filter(m => new Date(m.time).getTime() <= lastVisibleDate);
    candlestickSeries.setMarkers(currentMarkers);
    
    // 3. 动态更新日志表格
    visibleLogs.value = fullLogs.filter(log => new Date(log.timestamp).getTime() <= lastVisibleDate);
  }

  // 4. 将切片推入图表
  candlestickSeries.setData(currentKlines);
  areaSeries.setData(currentEquity);

  // 5. 让时间轴自动跟随最新的一根 K 线
  klineChart.timeScale().fitContent();
};

// 🌟 交互控制器
const handleSearch = () => {
  router.replace({
    query: {
      ...route.query,
      start: startDate.value,
      end: endDate.value
    }
  });
  initChartAndData();
};

const initChartAndData = async (refresh = false) => {
  loading.value = true;
  try {
    // 每次重新搜索时清理旧数据和图表
    fullKlineData = [];
    fullEquityData = [];
    fullMarkers = [];
    fullLogs = [];
    metadata.value = {};
    visibleCount.value = 0;
    totalDays.value = 0;
    visibleLogs.value = [];
    
    if (klineChart) {
      klineChart.remove();
      klineChart = null;
    }
    if (equityChart) {
      equityChart.remove();
      equityChart = null;
    }

    const start = startDate.value;
    const end = endDate.value;
    
    const res = await getStockDetail(props.ticker, start, end, refresh);
    const data = res.data;
    metadata.value = data.metadata;
    fullLogs = data.logs;

    const seenDates = new Set();
    data.klines.forEach(item => {
      if (item.date && !seenDates.has(item.date)) {
        seenDates.add(item.date);
        fullKlineData.push({ 
          time: item.date, 
          open: Number(item.open), 
          high: Number(item.high), 
          low: Number(item.low), 
          close: Number(item.close),
          volume: Number(item.volume || 0),
          amount: Number(item.amount || 0),
          amplitude: Number(item.amplitude || 0),
          pct_change: Number(item.pct_change || 0),
          change_amount: Number(item.change_amount || 0),
          turnover: Number(item.turnover || 0)
        });
        fullEquityData.push({ time: item.date, value: Number(item.total_equity) });
      }
    });

    data.logs.forEach(log => {
      if (seenDates.has(log.timestamp)) {
        fullMarkers.push({
          time: log.timestamp, position: log.action === '买入' ? 'belowBar' : 'aboveBar',
          color: log.action === '买入' ? '#F6465D' : '#0ECB81', shape: log.action === '买入' ? 'arrowUp' : 'arrowDown',
          text: log.action === '买入' ? '买入' : '卖出',
        });
      }
    });

    fullKlineData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
    fullEquityData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
    fullMarkers.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

    totalDays.value = fullKlineData.length;
    visibleCount.value = totalDays.value; // 初始加载全部数据

    await nextTick();
    
    klineChart = createChart(klineChartRef.value, { ...darkThemeOptions, width: klineChartRef.value.clientWidth, height: 400 });
    candlestickSeries = klineChart.addCandlestickSeries({ upColor: '#F6465D', downColor: '#0ECB81', borderVisible: false, wickUpColor: '#F6465D', wickDownColor: '#0ECB81' });

    equityChart = createChart(equityChartRef.value, { ...darkThemeOptions, width: equityChartRef.value.clientWidth, height: 200 });
    areaSeries = equityChart.addAreaSeries({ topColor: 'rgba(245, 158, 11, 0.4)', bottomColor: 'rgba(245, 158, 11, 0.0)', lineColor: '#f59e0b', lineWidth: 2 });

    klineChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
      if (timeRange) equityChart.timeScale().setVisibleLogicalRange(timeRange);
    });
    equityChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
      if (timeRange) klineChart.timeScale().setVisibleLogicalRange(timeRange);
    });

    // 十字光标事件监听
    klineChart.subscribeCrosshairMove(param => {
      if (
        param.point === undefined ||
        !param.time ||
        param.point.x < 0 ||
        param.point.x > klineChartRef.value.clientWidth ||
        param.point.y < 0 ||
        param.point.y > klineChartRef.value.clientHeight
      ) {
        crosshairInfo.value = null;
      } else {
        const data = param.seriesData.get(candlestickSeries);
        if (data && data.time) {
          // 为了确保获取到自定义指标(成交额/换手率等)，通过 time 去全量数据里查
          const matchData = fullKlineData.find(k => k.time === data.time);
          crosshairInfo.value = matchData || null;
        } else {
          crosshairInfo.value = null;
        }
      }
    });

    // 首次渲染切片
    renderSlice();

  } catch (error) {
    ElMessage.error('图表渲染失败，请检查控制台报错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const handleRefresh = () => initChartAndData(true);

onMounted(() => {
  window.scrollTo(0, 0); // 默认滚动到顶部
  initChartAndData();
});

onUnmounted(() => {
  if (klineChart) klineChart.remove();
  if (equityChart) equityChart.remove();
});
</script>

<style scoped>
/* 样式新增了时空控制台的排版，其余保持不变 */
.detail-container { background-color: #0b0e14; min-height: 100vh; padding: 20px; color: #d1d4dc; }
.header { display: flex; flex-direction: column; gap: 15px; margin-bottom: 15px; }
.header-top { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
.header-bottom { display: flex; justify-content: flex-start; }
.left-controls { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
.right-controls { display: flex; align-items: center; gap: 20px; flex: 1; min-width: 0; justify-content: flex-end; }
.predict-buttons { display: flex; gap: 10px; flex-shrink: 0; align-items: center; }
.ticker-title { margin: 0; color: #fff; font-size: 24px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.time-controls { display: inline-flex; align-items: center; gap: 15px; background: #131722; padding: 5px 15px; border-radius: 8px; border: 1px solid #2B3139;}
.progress-text { font-size: 14px; font-weight: bold; color: #f59e0b; display: flex; align-items: center; }
.stats-panel { display: flex; flex-wrap: wrap; gap: 15px; background-color: #131722; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #2B3139; }
.stat-box { flex: 1; min-width: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center;}
.stat-label { font-size: 12px; color: #8a919e; margin-bottom: 5px; }
.stat-value { font-size: 18px; font-weight: bold; color: #fff; }
.charts-wrapper { background-color: #131722; border: 1px solid #2B3139; border-radius: 8px; padding: 10px; margin-bottom: 20px; position: relative; }
.main-chart { width: 100%; border-bottom: 1px solid #2B3139; margin-bottom: 10px; padding-bottom: 10px;}
.sub-chart { width: 100%; }

/* 十字光标信息浮窗样式 */
.crosshair-tooltip {
  position: absolute;
  top: 15px;
  left: 15px;
  z-index: 10;
  background-color: rgba(19, 23, 34, 0.85);
  border: 1px solid #2B3139;
  border-radius: 6px;
  padding: 10px 15px;
  color: #d1d4dc;
  font-size: 12px;
  pointer-events: none;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
.tooltip-date {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 8px;
  color: #fff;
  border-bottom: 1px solid #2B3139;
  padding-bottom: 5px;
}
.tooltip-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  column-gap: 15px;
  row-gap: 5px;
}
.tooltip-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 80px;
}
.tooltip-item .label {
  color: #8a919e;
  margin-right: 10px;
}
.tooltip-item .value {
  font-family: monospace;
  font-weight: bold;
}
.text-white { color: #fff !important; }
.logs-wrapper { background-color: #131722; border-radius: 8px; padding: 15px; border: 1px solid #2B3139;}
.logs-title { margin-top: 0; margin-bottom: 15px; font-size: 16px; color: #fff; }
.red { color: #F6465D !important; }
.green { color: #0ECB81 !important; }
.text-red { color: #F6465D; font-weight: bold; }
.text-green { color: #0ECB81; font-weight: bold; }
:deep(.el-table) { background-color: transparent !important; --el-table-border-color: #2B3139; --el-table-header-bg-color: #1a1e29; --el-table-tr-bg-color: #131722; --el-table-text-color: #d1d4dc; --el-table-header-text-color: #8a919e;}
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { border-bottom: 1px solid #2B3139; }
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) { background-color: #1a1e29; }

/* 弹窗暗黑模式样式 */
:deep(.el-dialog) {
  background-color: #131722;
  border: 1px solid #2B3139;
}
:deep(.el-dialog__title) {
  color: #d1d4dc;
}
:deep(.el-dialog__header) {
  border-bottom: 1px solid #2B3139;
  margin-right: 0;
  padding-bottom: 15px;
}
:deep(.el-dialog__body) {
  color: #d1d4dc;
  padding: 15px 20px;
}

/* 聊天窗口样式 */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 72vh;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  background: #0b0e14;
  border-radius: 8px;
  border: 1px solid #2B3139;
  margin-bottom: 15px;
}
.chat-message {
  display: flex;
  margin-bottom: 20px;
}
.chat-message.user {
  flex-direction: row-reverse;
}
.message-avatar {
  font-size: 24px;
  margin: 0 10px;
}
.message-content {
  background: #1a1e29;
  padding: 12px 16px;
  border-radius: 8px;
  max-width: 80%;
  border: 1px solid #2B3139;
}
.chat-message.user .message-content {
  background: #2b3139;
  color: #fff;
}
.chat-input-area {
  display: flex;
  align-items: flex-start;
}
:deep(.chat-input-area .el-textarea__inner) {
  background-color: #0b0e14;
  border-color: #2B3139;
  color: #d1d4dc;
}
:deep(.chat-input-area .el-textarea__inner:focus) {
  border-color: #409eff;
}

/* Markdown 样式 */
.markdown-body {
  font-size: 14px;
  line-height: 1.6;
  color: #d1d4dc;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: #e2e8f0;
}
.markdown-body :deep(h3) { font-size: 1.25em; border-bottom: 1px solid #2B3139; padding-bottom: 8px; }
.markdown-body :deep(h4) { font-size: 1em; }
.markdown-body :deep(p) {
  margin-top: 0;
  margin-bottom: 16px;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-top: 0;
  margin-bottom: 16px;
  padding-left: 2em;
}
.markdown-body :deep(li) {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}
.markdown-body :deep(strong) {
  font-weight: 600;
  color: #e2e8f0;
}
.markdown-body :deep(hr) {
  height: 1px;
  background-color: #2B3139;
  border: none;
  margin: 24px 0;
}
</style>
