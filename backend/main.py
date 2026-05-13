import os
import json
import re

import yaml
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

# 彻底禁用 requests 的代理行为，防止 ProxyError
import requests
import urllib.request
os.environ['NO_PROXY'] = '*'
requests.utils.should_bypass_proxies = lambda url, no_proxy: True
urllib.request.getproxies = lambda: {}

from backend.core.data_center import DataCenter
from backend.core.engine import BacktestEngine
from backend.core.strategy import StrategyFactory 
from backend.core.db import prediction_db, user_db

app = FastAPI(title="Quant Simulate System API")

# 配置 CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 实例化数据中心
dc = DataCenter()

def load_config():
    """加载 YAML 配置文件"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def clean_nan(df: pd.DataFrame) -> list:
    """清理 DataFrame 中的 NaN 值，防止 JSON 序列化报错"""
    return df.fillna("").to_dict(orient="records")

def format_prediction_date(date_str: str) -> str:
    if not date_str:
        return ""
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s

def get_stock_names_from_config():
    """解析 config.yaml 提取股票中文名注释"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config.yaml"))
    names_map = {}
    import re
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                match = re.search(r'-\s+([a-zA-Z0-9]+)\s*#\s*(.+)', line)
                if match:
                    ticker = match.group(1).strip()
                    name = match.group(2).strip()
                    names_map[ticker] = name
    return names_map

def get_user_full_config(user_id: int = 1):
    config = user_db.get_user_config(user_id)
    default_config = load_config()
    if not config:
        return default_config
    
    return {
        "account": json.loads(config["account_config"]) if config.get("account_config") else default_config.get("account", {}),
        "strategy": json.loads(config["strategy_config"]) if config.get("strategy_config") else default_config.get("strategy", {}),
        "llm": json.loads(config["llm_config"]) if config.get("llm_config") else default_config.get("llm", {})
    }

@app.get("/api/summary", summary="获取大盘总览数据")
async def get_summary(start_date: str = "20240101", end_date: str = "20240201", refresh: bool = False, page: int = 1, page_size: int = 10, user_id: int = 1):
    config = get_user_full_config(user_id)
    
    user_stocks = user_db.get_user_stocks(user_id)
    pool = [stock['ticker'] for stock in user_stocks]
    names_map = {stock['ticker']: stock['name'] for stock in user_stocks}
    
    # Fallback to default if empty
    if not pool:
        default_config = load_config()
        pool = default_config.get('stock_pool', [])
        names_map = get_stock_names_from_config()
        
    total_count = len(pool)
    
    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_pool = pool[start_idx:end_idx]
    
    results = []
    for ticker in paginated_pool:
        try:
            # 1. 抓取数据
            raw_data = dc.fetch_stock_data(ticker, start_date="20230101", end_date=end_date, force_update=refresh)
            
            df_signals = StrategyFactory.generate_signals(
                raw_data, 
                config['strategy']['name'], 
                config['strategy']['parameters']
            )
            
            # 2. 严格按时间切片
            mask = (df_signals['date'] >= pd.to_datetime(start_date)) & \
                   (df_signals['date'] <= pd.to_datetime(end_date))
            df_slice = df_signals.loc[mask].copy().reset_index(drop=True)
            
            if df_slice.empty:
                continue

            # 3. 运行新版引擎
            engine = BacktestEngine(
                initial_cash=config['account']['initial_cash'],
                commission_rate=config['account']['commission_rate'],
                tax_rate=config['account']['tax_rate']
            )
            res = engine.run(df_slice, ticker)
            meta = res['metadata']
            
            # 4. 获取本地大模型预测结论
            import re
            advice = "暂无建议"
            latest_row = prediction_db.get_latest_prediction(ticker)
            if latest_row and latest_row.get("prediction"):
                # 兼容可能的 Markdown 格式，例如 "**明确结论**：谨慎买入" 或 "1. 明确结论: 持有"
                match = re.search(r"明确结论\**[：:]\s*\**([^\n\*]+)", latest_row["prediction"])
                advice_text = match.group(1).strip() if match else "暂无建议"
                
                # 去除可能的括号内容，例如 "谨慎买入 (短期反弹)" -> "谨慎买入"
                advice_text = re.sub(r"（.*?）|\(.*?\)", "", advice_text).strip()
                
                if advice_text != "暂无建议":
                    pred_date = format_prediction_date(latest_row.get("date"))
                    advice = f"{advice_text}({pred_date})" if pred_date else advice_text
            
            results.append({
                "ticker": ticker,
                "name": names_map.get(ticker, "-"),
                "strategy": config['strategy']['name'],
                "final_equity": meta['final_equity'],
                "return_rate": meta['total_return'], 
                "trade_count": meta['trade_count'],
                "advice": advice
            })
        except Exception as e:
            print(f"处理 {ticker} 失败: {e}")
            
    return {"status": "success", "data": results, "total": total_count}


@app.get("/api/detail/{ticker}", summary="获取单票详细数据")
async def get_detail(ticker: str, start_date: str = "20240101", end_date: str = "20240131", refresh: bool = False, user_id: int = 1):
    config = get_user_full_config(user_id)
    
    try:
        raw_data = dc.fetch_stock_data(ticker, start_date="20230101", end_date=end_date, force_update=refresh)
        
        df_signals = StrategyFactory.generate_signals(
            raw_data, 
            config['strategy']['name'], 
            config['strategy']['parameters']
        )
        
        mask = (df_signals['date'] >= pd.to_datetime(start_date)) & \
               (df_signals['date'] <= pd.to_datetime(end_date))
        df_slice = df_signals.loc[mask].copy().reset_index(drop=True)
        
        if df_slice.empty:
            raise ValueError("该时间区间内没有交易数据")

        engine = BacktestEngine(
            initial_cash=config['account']['initial_cash'],
            commission_rate=config['account']['commission_rate'],
            tax_rate=config['account']['tax_rate']
        )
        res = engine.run(df_slice, ticker)
        
        res['data']['date'] = res['data']['date'].dt.strftime('%Y-%m-%d')
        
        # 获取股票名称
        try:
            names_map = get_stock_names_from_config()
            if ticker in names_map:
                stock_name = names_map[ticker]
            else:
                import akshare as ak
                if not hasattr(app, "stock_info_cache"):
                    app.stock_info_cache = ak.stock_info_a_code_name()
                stock_info = app.stock_info_cache
                clean_ticker = ticker[2:] if ticker.startswith(('sh', 'sz')) else ticker
                name_row = stock_info[stock_info['code'] == clean_ticker]
                stock_name = name_row['name'].values[0] if not name_row.empty else ticker
        except Exception:
            stock_name = ticker
            
        res['metadata']['stock_name'] = stock_name
        
        return {
            "status": "success",
            "metadata": res['metadata'], 
            "klines": clean_nan(res['data']), 
            "logs": res['logs']
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/predict/{ticker}", summary="基于大模型预测股票走势")
async def predict_stock(ticker: str, start_date: str = "20240101", end_date: str = "20240131", user_id: int = 1):
    config = get_user_full_config(user_id)
    
    # 检查大模型配置
    if 'llm' not in config:
        raise HTTPException(status_code=500, detail="未配置大模型信息，请检查 config.yaml")
    llm_config = config['llm']
    api_key = llm_config.get('api_key')
    base_url = llm_config.get('base_url', 'https://api.deepseek.com')
    model_name = llm_config.get('model', 'deepseek-chat')
    predict_days = llm_config.get('predict_days', 60)

    if not api_key or api_key == "YOUR_DEEPSEEK_API_KEY":
        raise HTTPException(status_code=400, detail="请在 config.yaml 中填入有效的 DeepSeek API Key")

    # 先检查数据库缓存
    cached_prediction = prediction_db.get_prediction(ticker, end_date)
    if cached_prediction:
        return {
            "status": "success",
            "prediction": cached_prediction,
            "cached": True
        }

    try:
        # 获取当前可视时间段的股票数据
        # 往前回溯一段时间确保有足够数据
        raw_data = dc.fetch_stock_data(ticker, start_date="20230101", end_date=end_date)
        
        # 确保只使用 end_date 之前的数据进行预测，避免未来函数
        mask = (raw_data['date'] <= pd.to_datetime(end_date))
        historical_data = raw_data.loc[mask].copy().reset_index(drop=True)
        
        if historical_data.empty:
            raise ValueError("无足够的历史数据供模型分析")
            
        # 取最近的一段时间数据给大模型（默认60个交易日）
        recent_data = historical_data.tail(predict_days).copy()
        
        # 将日期格式化为字符串，方便大模型阅读
        recent_data['date'] = recent_data['date'].dt.strftime('%Y-%m-%d')
        
        # 提取关键字段构建简化的文本数据
        selected_cols = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount']
        data_str = recent_data[selected_cols].to_csv(index=False)
        
        prompt = (
            f"你是专业的量化股票分析师。以下是A股标的 {ticker} 截至 {end_date} 之前最近{predict_days}个交易日的日K线数据：\n"
            f"{data_str}\n\n"
            "请根据上述数据，深入分析该股票的后市走势，并以专业投资者的口吻给出以下建议。\n"
            "请务必确保严格按照以下Markdown格式和结构输出你的分析报告：\n\n"
            "### 专业量化股票分析报告\n\n"
            f"**标的：** {ticker}\n"
            f"**数据截止：** {end_date}\n"
            "**分析结论：** [一句话总结你的核心观点，例如：谨慎买入（短期反弹机会，但需控制风险）]\n\n"
            "---\n\n"
            "### 1. 明确结论：[强烈建议买入/谨慎买入/持有/减仓/清仓卖出]\n\n"
            "- **理由概述**：[简明扼要地概括你的核心判断依据]\n\n"
            "---\n\n"
            "### 2. 操作点位\n\n"
            "- **买入区间**：[具体价格或区间，并附带简短说明]\n"
            "- **止损位**：[具体价格，并附带简短说明]\n"
            "- **目标位**：[具体价格或区间，并附带简短说明]\n\n"
            "---\n\n"
            "### 3. 核心逻辑\n\n"
            "**(1) 趋势分析：[用一句话概括趋势，例如：中期下行，短期反弹]**\n\n"
            "- **中期趋势**：[详细分析中期趋势]\n"
            "- **短期趋势**：[详细分析短期趋势]\n\n"
            "**(2) 量价配合：[用一句话概括量价，例如：底部放量，资金介入]**\n\n"
            "- [详细分析量价配合情况]\n\n"
            "**(3) 支撑阻力：[用一句话概括关键点位]**\n\n"
            "- [详细分析支撑位和阻力位的情况]\n"
        )
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一个专业的量化股票分析师，提供精准的股票预测和买卖点建议。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        url = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"大模型 API 请求失败: {response.text}")
            
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # 存入数据库
        prediction_db.save_prediction(ticker, end_date, content)
        
        return {
            "status": "success",
            "prediction": content,
            "cached": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    ticker: str
    messages: list[ChatMessage]
    user_id: int = 1

@app.post("/api/chat", summary="大模型多轮对话")
async def chat_api(req: ChatRequest):
    config = get_user_full_config(req.user_id)
    if 'llm' not in config:
        raise HTTPException(status_code=500, detail="未配置大模型信息")
    
    llm_config = config['llm']
    api_key = llm_config.get('api_key')
    base_url = llm_config.get('base_url', 'https://api.deepseek.com')
    model_name = llm_config.get('model', 'deepseek-chat')

    if not api_key or api_key == "YOUR_DEEPSEEK_API_KEY":
        raise HTTPException(status_code=400, detail="请在 config.yaml 中填入有效的 DeepSeek API Key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 构造请求给大模型
    # 加入 system prompt
    system_msg = {
        "role": "system", 
        "content": f"你是一个专业的量化股票分析师，当前正在分析A股标的 {req.ticker}。请基于之前的分析报告和用户的提问，给出专业、简明扼要的回答。使用Markdown格式排版。"
    }
    
    api_messages = [system_msg] + [{"role": m.role, "content": m.content} for m in req.messages]

    payload = {
        "model": model_name,
        "messages": api_messages,
        "temperature": 0.7
    }

    try:
        url = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"大模型 API 请求失败: {response.text}")
            
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        return {
            "status": "success",
            "reply": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================
# Admin & User Management APIs
# ==============================

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/user/login", summary="用户登录")
async def user_login(req: LoginRequest):
    user = user_db.get_user(req.username)
    if not user or user["password_hash"] != req.password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "status": "success",
        "user_id": user["id"],
        "username": user["username"],
        "role": "user"
    }

@app.post("/api/admin/login", summary="管理员登录")
async def admin_login(req: LoginRequest):
    admin = user_db.get_admin(req.username)
    if not admin or admin["password_hash"] != req.password:
        raise HTTPException(status_code=401, detail="管理员用户名或密码错误")
    return {
        "status": "success",
        "admin_id": admin["id"],
        "username": admin["username"],
        "role": admin["role"]
    }

class UserCreateRequest(BaseModel):
    username: str
    password: str
    permissions: Optional[Dict[str, Any]] = None

class UserPermissionUpdateRequest(BaseModel):
    permissions: Dict[str, Any]

@app.post("/api/admin/users", summary="管理员创建用户")
async def create_user(req: UserCreateRequest):
    # Check if user exists
    existing = user_db.get_user(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
        
    permissions_str = json.dumps(req.permissions) if req.permissions else None
    user_id = user_db.create_user(req.username, req.password, permissions_str)
    return {"status": "success", "user_id": user_id}

@app.get("/api/admin/users", summary="管理员获取所有用户")
async def get_all_users():
    users = user_db.get_all_users()
    for user in users:
        user['permissions'] = json.loads(user['permissions']) if user['permissions'] else {}
    return {"status": "success", "data": users}

@app.put("/api/admin/users/{user_id}/permissions", summary="管理员设置用户权限")
async def update_user_permissions(user_id: int, req: UserPermissionUpdateRequest):
    user_db.update_user_permissions(user_id, json.dumps(req.permissions))
    return {"status": "success"}

@app.delete("/api/admin/users/{user_id}", summary="管理员删除用户")
async def delete_user(user_id: int):
    user_db.delete_user(user_id)
    return {"status": "success"}

# ==============================
# User Config APIs
# ==============================

class UserConfigRequest(BaseModel):
    account: Optional[Dict[str, Any]] = None
    strategy: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None

@app.get("/api/user/config", summary="获取用户配置")
async def get_user_config_api(user_id: int = 1):
    config = get_user_full_config(user_id)
    return {"status": "success", "data": config}

@app.put("/api/user/config", summary="更新用户配置")
async def update_user_config_api(req: UserConfigRequest, user_id: int = 1):
    account_str = json.dumps(req.account) if req.account is not None else None
    strategy_str = json.dumps(req.strategy) if req.strategy is not None else None
    llm_str = json.dumps(req.llm) if req.llm is not None else None
    
    # Retrieve existing config to merge
    existing = user_db.get_user_config(user_id)
    if existing:
        if account_str is None: account_str = existing.get("account_config")
        if strategy_str is None: strategy_str = existing.get("strategy_config")
        if llm_str is None: llm_str = existing.get("llm_config")
        
    user_db.save_user_config(user_id, account_str, strategy_str, llm_str)
    return {"status": "success"}

@app.get("/api/predict_list/{ticker}", summary="获取某股票所有历史预测列表")
async def get_predict_list(ticker: str):
    try:
        records = prediction_db.get_predictions_by_ticker(ticker)
        
        results = []
        import re
        for row in records:
            pred_text = row['prediction']
            advice = "暂无建议"
            reason = pred_text
            
            # 提取明确结论
            match_advice = re.search(r"明确结论\**[：:]\s*\**([^\n\*]+)", pred_text)
            if match_advice:
                advice = match_advice.group(1).strip()
                advice = re.sub(r"（.*?）|\(.*?\)", "", advice).strip()
                
            # 提取理由概述作为建议依据 (可选，或者直接显示全部 markdown，但前端要求单独成列)
            match_reason = re.search(r"理由概述\**[：:]\s*(.*?)(?=\n-|\n\*\*|---|$)", pred_text, re.DOTALL)
            if match_reason:
                reason = match_reason.group(1).strip()
            
            results.append({
                "date": row['date'],
                "advice": advice,
                "reason": reason,
                "full_prediction": pred_text,
                "created_at": row['created_at'].strftime("%Y-%m-%d %H:%M:%S") if row.get('created_at') else None
            })
            
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import time

@app.get("/api/user/stocks", summary="获取用户股票池列表")
async def get_user_stocks_api(user_id: int = 1):
    stocks = user_db.get_user_stocks(user_id)
    # Convert Decimals to float for JSON serialization
    for stock in stocks:
        if 'purchase_amount' in stock and stock['purchase_amount'] is not None:
            stock['purchase_amount'] = float(stock['purchase_amount'])
        if 'profit_amount' in stock and stock['profit_amount'] is not None:
            stock['profit_amount'] = float(stock['profit_amount'])
        if 'profit_rate' in stock and stock['profit_rate'] is not None:
            stock['profit_rate'] = float(stock['profit_rate'])
    return {"status": "success", "data": stocks}

class AddStockRequest(BaseModel):
    code: str
    user_id: int = 1

@app.post("/api/stock_pool/add", summary="手动添加股票")
async def add_stock_api(req: AddStockRequest):
    code = req.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="请输入6位数字股票代码")
        
    import akshare as ak
    if not hasattr(app, "stock_info_cache"):
        app.stock_info_cache = ak.stock_info_a_code_name()
    stock_info = app.stock_info_cache
    
    row = stock_info[stock_info['code'] == code]
    
    if row.empty:
        # 如果普通A股没找到，尝试在ETF列表里找
        if not hasattr(app, "etf_info_cache"):
            try:
                app.etf_info_cache = ak.fund_etf_category_sina(symbol="ETF基金")
            except:
                app.etf_info_cache = pd.DataFrame()
        
        etf_info = app.etf_info_cache
        if not etf_info.empty and '代码' in etf_info.columns:
            # 兼容带有 sh/sz 前缀的情况
            etf_row = etf_info[etf_info['代码'].str.endswith(code)]
            if not etf_row.empty:
                name = etf_row['名称'].values[0]
                prefix = 'sh' if code.startswith(('5', '6')) else 'sz'
                ticker = f"{prefix}{code}"
                
                user_stocks = user_db.get_user_stocks(req.user_id)
                if any(s['ticker'] == ticker for s in user_stocks):
                    return {"status": "success", "detail": "ETF已存在", "ticker": ticker, "name": name}
                    
                user_db.add_user_stock(req.user_id, ticker, name)
                return {"status": "success", "ticker": ticker, "name": name}
                
        # 如果依然没找到，最后尝试从全部开放式基金里查找 (比如场外混合型基金 025209)
        if not hasattr(app, "all_fund_info_cache"):
            try:
                app.all_fund_info_cache = ak.fund_name_em()
            except:
                app.all_fund_info_cache = pd.DataFrame()
                
        all_fund_info = app.all_fund_info_cache
        if not all_fund_info.empty and '基金代码' in all_fund_info.columns:
            fund_row = all_fund_info[all_fund_info['基金代码'] == code]
            if not fund_row.empty:
                name = fund_row['基金简称'].values[0]
                # 场外基金统一加上 'of' 前缀 (Open Fund) 或者其他自定义前缀，这里用 'of' 避免和场内 sh/sz 冲突
                ticker = f"of{code}"
                
                user_stocks = user_db.get_user_stocks(req.user_id)
                if any(s['ticker'] == ticker for s in user_stocks):
                    return {"status": "success", "detail": "基金已存在", "ticker": ticker, "name": name}
                    
                user_db.add_user_stock(req.user_id, ticker, name)
                return {"status": "success", "ticker": ticker, "name": name}

        raise HTTPException(status_code=404, detail=f"未找到代码为 {code} 的股票或ETF/基金")
        
    name = row['name'].values[0]
    prefix = 'sh' if code.startswith(('5', '6', '9')) else 'sz'
    ticker = f"{prefix}{code}"
    
    user_stocks = user_db.get_user_stocks(req.user_id)
    if any(s['ticker'] == ticker for s in user_stocks):
        return {"status": "success", "detail": "股票已存在", "ticker": ticker, "name": name}
        
    user_db.add_user_stock(req.user_id, ticker, name)
    return {"status": "success", "ticker": ticker, "name": name}

@app.delete("/api/stock_pool/{ticker}", summary="删除股票")
async def delete_stock_api(ticker: str, user_id: int = 1):
    user_stocks = user_db.get_user_stocks(user_id)
    if not any(s['ticker'] == ticker for s in user_stocks):
        raise HTTPException(status_code=404, detail="股票不在股票池中")
        
    user_db.remove_user_stock(user_id, ticker)
    return {"status": "success"}

class UpdateStockStatsRequest(BaseModel):
    purchase_amount: float
    profit_amount: float
    profit_rate: float
    user_id: int = 1

@app.put("/api/stock_pool/{ticker}/stats", summary="更新股票收益统计信息")
async def update_stock_stats_api(ticker: str, req: UpdateStockStatsRequest):
    user_stocks = user_db.get_user_stocks(req.user_id)
    if not any(s['ticker'] == ticker for s in user_stocks):
        raise HTTPException(status_code=404, detail="股票不在股票池中")
        
    user_db.update_user_stock_stats(req.user_id, ticker, req.purchase_amount, req.profit_amount, req.profit_rate)
    return {"status": "success"}

@app.post("/api/stock_pool/{ticker}/calculate_profit", summary="计算股票收益")
async def calculate_stock_profit_api(ticker: str, user_id: int = 1):
    user_stocks = user_db.get_user_stocks(user_id)
    stock = next((s for s in user_stocks if s['ticker'] == ticker), None)
    if not stock:
        raise HTTPException(status_code=404, detail="股票不在股票池中")

    operations = user_db.get_stock_operations(user_id, ticker)
    purchase_amount = float(stock.get('purchase_amount') or 0)
    
    if purchase_amount <= 0:
        return {"status": "success", "data": {"profit_amount": 0, "profit_rate": 0}}
        
    total_buy_qty = sum(op['quantity'] for op in operations if op['operation_type'] == 'BUY')
    total_sell_qty = sum(op['quantity'] for op in operations if op['operation_type'] == 'SELL')
    current_qty = total_buy_qty - total_sell_qty
    
    if current_qty <= 0:
        return {"status": "success", "data": {"profit_amount": 0, "profit_rate": 0}}

    import akshare as ak
    import pandas as pd
    
    current_price = 0.0
    clean_ticker = ticker[2:] if ticker.startswith(('sh', 'sz', 'bj')) else ticker
    
    try:
        hist = ak.stock_zh_a_hist(symbol=clean_ticker, period="daily", start_date="20200101", adjust="")
        if not hist.empty:
            current_price = float(hist.iloc[-1]['收盘'])
        else:
            hist = ak.fund_etf_hist_em(symbol=clean_ticker, period="daily", start_date="20200101", adjust="")
            if not hist.empty:
                current_price = float(hist.iloc[-1]['收盘'])
    except:
        pass
        
    if current_price > 0:
        current_value = current_qty * current_price
        profit_amount = round(current_value - purchase_amount, 2)
        profit_rate = round(profit_amount / purchase_amount, 4)
        
        user_db.update_user_stock_stats(user_id, ticker, purchase_amount, profit_amount, profit_rate)
        return {"status": "success", "data": {"profit_amount": profit_amount, "profit_rate": profit_rate}}
        
    return {"status": "success", "data": {"profit_amount": float(stock.get('profit_amount') or 0), "profit_rate": float(stock.get('profit_rate') or 0)}}

class StockOperationRequest(BaseModel):
    ticker: str
    operation_type: str # 'BUY' or 'SELL'
    price: float
    quantity: int
    amount: float
    operation_date: str # YYYY-MM-DD
    user_id: int = 1

@app.post("/api/stock_operations", summary="添加股票操作记录")
async def add_stock_operation_api(req: StockOperationRequest):
    if req.operation_type not in ('BUY', 'SELL'):
        raise HTTPException(status_code=400, detail="操作类型必须为 BUY 或 SELL")
        
    user_db.add_stock_operation(
        req.user_id, 
        req.ticker, 
        req.operation_type, 
        req.price, 
        req.quantity, 
        req.amount, 
        req.operation_date
    )
    return {"status": "success"}

@app.get("/api/stock_operations", summary="获取股票操作记录")
async def get_stock_operations_api(ticker: Optional[str] = None, user_id: int = 1):
    operations = user_db.get_stock_operations(user_id, ticker)
    # Convert dates to string for JSON serialization
    for op in operations:
        if op.get('operation_date'):
            op['operation_date'] = str(op['operation_date'])
        if op.get('created_at'):
            op['created_at'] = op['created_at'].strftime("%Y-%m-%d %H:%M:%S")
    return {"status": "success", "data": operations}

class RecommendRequest(BaseModel):
    price: float
    count: int = 5
    user_id: int = 1

@app.post("/api/recommend_stocks", summary="AI根据价格推荐股票")
async def recommend_stocks_api(req: RecommendRequest):
    config = get_user_full_config(req.user_id)
    if 'llm' not in config:
        raise HTTPException(status_code=500, detail="未配置大模型信息")
    
    llm_config = config['llm']
    api_key = llm_config.get('api_key')
    base_url = llm_config.get('base_url', 'https://api.deepseek.com')
    model_name = llm_config.get('model', 'deepseek-chat')

    if not api_key or api_key == "YOUR_DEEPSEEK_API_KEY":
        raise HTTPException(status_code=400, detail="请在 config.yaml 中填入有效的 DeepSeek API Key")

    # === 进阶优化：通过 akshare 获取全市场数据并初步过滤 ===
    import akshare as ak
    import pandas as pd
    candidates_str = ""
    try:
        # 尝试获取东方财富实时行情（包含市盈率）
        df_spot = ak.stock_zh_a_spot_em()
        
        # 预处理数据
        df_spot = df_spot.dropna(subset=['最新价', '市盈率-动态'])
        df_spot['最新价'] = pd.to_numeric(df_spot['最新价'], errors='coerce')
        df_spot['市盈率-动态'] = pd.to_numeric(df_spot['市盈率-动态'], errors='coerce')
        df_spot = df_spot.dropna(subset=['最新价', '市盈率-动态'])
        
        # 过滤条件：价格区间 ±20%，PE 0-30，剔除ST/退市，仅限沪深A股
        min_price = req.price * 0.8
        max_price = req.price * 1.2
        
        mask = (
            (df_spot['最新价'] >= min_price) & 
            (df_spot['最新价'] <= max_price) & 
            (df_spot['市盈率-动态'] > 0) & 
            (df_spot['市盈率-动态'] < 30) &
            (~df_spot['名称'].str.contains('ST|退', na=False)) &
            (df_spot['代码'].str.startswith(('60', '00', '30')))
        )
        filtered_df = df_spot.loc[mask].copy()
        
        # 按成交额排序选取流动性最好的前 50 只
        if '成交额' in filtered_df.columns:
            filtered_df['成交额'] = pd.to_numeric(filtered_df['成交额'], errors='coerce')
            filtered_df = filtered_df.sort_values(by='成交额', ascending=False)
            
        candidate_list = filtered_df.head(50)[['代码', '名称', '最新价', '市盈率-动态']].to_dict('records')
        if candidate_list:
            candidates_str = "【实时初筛股票池】（已过滤价格、低估值PE<30及高流动性）：\n"
            candidates_str += "\n".join([f"{row['代码']} ({row['名称']}) - 现价: {row['最新价']}, 动态PE: {row['市盈率-动态']}" for row in candidate_list])
        else:
            candidates_str = "（未找到符合量化初筛条件的实时股票数据，请根据自身知识库推荐）"
    except Exception as e:
        print(f"获取实时数据失败: {e}")
        # 备用方案：仅通过新浪获取价格数据
        try:
            df_spot = ak.stock_zh_a_spot()
            df_spot['最新价'] = pd.to_numeric(df_spot['最新价'], errors='coerce')
            df_spot = df_spot.dropna(subset=['最新价'])
            min_price = req.price * 0.8
            max_price = req.price * 1.2
            # 新浪API的A股代码带有sh/sz前缀或者bj前缀，或者纯数字？Sina通常是sh/sz前缀
            mask = (
                (df_spot['最新价'] >= min_price) & 
                (df_spot['最新价'] <= max_price) & 
                (~df_spot['名称'].str.contains('ST|退', na=False)) &
                (df_spot['代码'].str.startswith(('sh60', 'sz00', 'sz30')))
            )
            filtered_df = df_spot.loc[mask].copy()
            if '成交额' in filtered_df.columns:
                filtered_df['成交额'] = pd.to_numeric(filtered_df['成交额'], errors='coerce')
                filtered_df = filtered_df.sort_values(by='成交额', ascending=False)
            candidate_list = filtered_df.head(50)[['代码', '名称', '最新价']].to_dict('records')
            if candidate_list:
                candidates_str = "【实时初筛股票池】（仅包含价格过滤及高流动性）：\n"
                candidates_str += "\n".join([f"{row['代码']} ({row['名称']}) - 现价: {row['最新价']}" for row in candidate_list])
            else:
                candidates_str = "（未找到符合量化初筛条件的实时股票数据，请根据自身知识库推荐）"
        except Exception as fallback_e:
            print(f"备用行情获取也失败: {fallback_e}")
            candidates_str = "（实时行情服务暂时不可用，请完全根据自身知识库推荐）"

    prompt = (
        f"作为专业的A股量化投资顾问，请从以下【实时初筛股票池】中精选出 {req.count} 只最优质的A股股票推荐给我。\n\n"
        f"{candidates_str}\n\n"
        "为了保证推荐质量，请遵循以下选股标准对候选股票进行二次深度过滤（如果候选池不足，可补充你认为符合条件的股票）：\n"
        "1. 行业地位：优先选择行业龙头或具有宽广护城河的公司。\n"
        "2. 财务健康：具有稳定的盈利能力，ROE（净资产收益率）常年保持在10%以上。\n"
        "3. 估值合理：结合候选池中的PE数据（如有），避免推荐被严重爆炒、估值过高的题材股。\n\n"
        "输出要求：\n"
        "1. 仅返回纯JSON格式数组，不要任何其他解释性文本，不要markdown代码块。\n"
        "2. JSON数组中每个对象包含两个字段：'ticker'（代码，必须以sh或sz开头，如 sh600036）和 'name'（股票中文名）。\n"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一个只输出JSON的股票推荐助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        url = f"{base_url.rstrip('/')}/chat/completions"
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"大模型 API 请求失败: {response.text}")
            
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # 尝试解析JSON
        # 清理可能包含的markdown标记
        content = content.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            content = match.group(0)
        stocks = json.loads(content)
        
        if not isinstance(stocks, list) or len(stocks) == 0:
            raise Exception("大模型返回的数据格式不正确")
            
        # 写入数据库
        user_stocks = user_db.get_user_stocks(req.user_id)
        existing_tickers = {s['ticker'] for s in user_stocks}
        
        for stock in stocks:
            ticker = stock.get("ticker", "").lower()
            name = stock.get("name", "")
            if ticker and name and ticker not in existing_tickers:
                user_db.add_user_stock(req.user_id, ticker, name)
                
        return {
            "status": "success",
            "data": stocks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
