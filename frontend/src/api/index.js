import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api', 
  timeout: 60000,
});

export const userLogin = (username, password) => {
  return api.post('/user/login', { username, password });
};

export const adminLogin = (username, password) => {
  return api.post('/admin/login', { username, password });
};

export const getSummary = (startDate, endDate, refresh = false, page = 1, pageSize = 10) => {
  return api.get('/summary', {
    params: { start_date: startDate, end_date: endDate, refresh, page, page_size: pageSize }
  });
};

export const getStockDetail = (ticker, startDate, endDate, refresh = false) => {
  return api.get(`/detail/${ticker}`, {
    params: { start_date: startDate, end_date: endDate, refresh }
  });
};

export const predictStock = (ticker, startDate, endDate) => {
  return api.get(`/predict/${ticker}`, {
    params: { start_date: startDate, end_date: endDate }
  });
};

export const getPredictList = (ticker) => {
  return api.get(`/predict_list/${ticker}`);
};

export const chatWithLLM = (ticker, messages, userId = getUserId()) => {
  return api.post('/chat', {
    ticker,
    messages,
    user_id: userId
  });
};

const getUserId = () => localStorage.getItem('user_id') || 1;

export const recommendStocks = (price, count, sectors, userId = getUserId()) => {
  return api.post('/recommend_stocks', { price, count, sectors, user_id: userId });
};

export const getSectors = () => {
  return api.get('/sectors');
};

export const addStock = (code, userId = getUserId()) => {
  return api.post('/stock_pool/add', { code, user_id: userId });
};

export const deleteStock = (ticker, userId = getUserId()) => {
  return api.delete(`/stock_pool/${ticker}`, { params: { user_id: userId } });
};

export const getUserStocks = (userId = getUserId()) => {
  return api.get('/user/stocks', { params: { user_id: userId } });
};

export const calculateStockProfit = (ticker, userId = getUserId()) => {
  return api.post(`/stock_pool/${ticker}/calculate_profit`, null, { params: { user_id: userId } });
};

export const updateStockStats = (ticker, stats) => {
  return api.put(`/stock_pool/${ticker}/stats`, stats);
};

export const addStockOperation = (operation) => {
  return api.post('/stock_operations', operation);
};

export const getStockOperations = (ticker = null, userId = getUserId()) => {
  return api.get('/stock_operations', { params: { ticker, user_id: userId } });
};

export const getUserConfig = (userId = getUserId()) => {
  return api.get('/user/config', { params: { user_id: userId } });
};

export const updateUserConfig = (config, userId = getUserId()) => {
  return api.put('/user/config', config, { params: { user_id: userId } });
};

export default api;
