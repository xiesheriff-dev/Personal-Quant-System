import os
import time
import random  # 新增：引入随机数模块
import glob
import re
import pandas as pd
import akshare as ak
import requests
from datetime import datetime

# ==========================================
# 🐵 Monkey Patch: 动态替换 requests 的 User-Agent
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
]

# 保存原始的 requests.request 方法
_original_request = requests.request

def _patched_request(method, url, **kwargs):
    """拦截所有 requests 请求，动态注入随机的 User-Agent"""
    headers = kwargs.get('headers', {})
    if 'User-Agent' not in headers and 'user-agent' not in headers:
        headers['User-Agent'] = random.choice(USER_AGENTS)
        kwargs['headers'] = headers
    return _original_request(method, url, **kwargs)

# 替换 requests.request
requests.request = _patched_request
requests.api.request = _patched_request

# ==========================================

class DataCenter:
    """
    量化系统的数据神经中枢
    负责调用 akshare 获取 A 股历史数据，并进行本地高速缓存
    """
    def __init__(self, cache_dir: str = "data/cache"):
        self.base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self.cache_dir = os.path.join(self.base_path, cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.columns_map = {
            "日期": "date", "开盘": "open", "收盘": "close", 
            "最高": "high", "最低": "low", "成交量": "volume", 
            "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change", 
            "涨跌额": "change_amount", "换手率": "turnover"
        }

    def _clean_symbol(self, symbol: str) -> str:
        if symbol.startswith(("sh", "sz")):
            return symbol[2:]
        return symbol

    def fetch_stock_data(self, 
                         symbol: str, 
                         start_date: str = "20240101", 
                         end_date: str = "20260421", 
                         force_update: bool = False) -> pd.DataFrame:
        
        # 1. 智能模糊匹配：查找本地是否包含该股票代码的任何 parquet 文件（已恢复并保留本地缓存逻辑）
        search_pattern = os.path.join(self.cache_dir, f"{symbol}_*.parquet")
        existing_caches = glob.glob(search_pattern)

        requested_start = pd.to_datetime(start_date)
        requested_end = pd.to_datetime(end_date)
        cache_end_yyyymmdd = datetime.now().strftime("%Y%m%d")

        def _parse_cache_dates(cache_path: str) -> tuple[str | None, str | None]:
            basename = os.path.basename(cache_path)
            pattern = rf"^{re.escape(symbol)}_(\d{{8}})_(\d{{8}})\.parquet$"
            m = re.match(pattern, basename)
            if not m:
                return None, None
            return m.group(1), m.group(2)

        def _pick_cache_by_end_date(cache_paths: list[str], end_yyyymmdd: str) -> str | None:
            candidates: list[tuple[str, str, float]] = []
            for p in cache_paths:
                s, e = _parse_cache_dates(p)
                if e != end_yyyymmdd:
                    continue
                try:
                    mtime = os.path.getmtime(p)
                except OSError:
                    mtime = 0.0
                candidates.append((p, s or "99999999", mtime))

            if not candidates:
                return None
            candidates.sort(key=lambda x: (x[1], -x[2]))
            return candidates[0][0]

        # 如果找到了缓存文件，且没有强制要求更新
        if not force_update and existing_caches:
            cache_file = _pick_cache_by_end_date(existing_caches, cache_end_yyyymmdd)
            if cache_file:
                try:
                    print(f"📦 [DataCenter] 命中本地缓存(按文件日期): {os.path.basename(cache_file)}")
                    df = pd.read_parquet(cache_file)
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                    mask = (df['date'] >= requested_start) & (df['date'] <= requested_end)
                    return df.loc[mask].copy().reset_index(drop=True)
                except Exception:
                    pass

        # 2. 如果本地彻底没有这只股票，再走网络下载逻辑
        clean_code = self._clean_symbol(symbol)
        print(f"🌐 [DataCenter] 正在从东财下载新数据: {symbol}...")
        
        download_end_date = cache_end_yyyymmdd
        cache_file = os.path.join(self.cache_dir, f"{symbol}_{start_date}_{download_end_date}.parquet")
        max_retries = 5  
        df = pd.DataFrame()
        
        for attempt in range(max_retries):
            try:
                # 1. 首先尝试作为普通 A 股股票获取数据
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=clean_code, 
                        period="daily", 
                        start_date=start_date, 
                        end_date=download_end_date, 
                        adjust="qfq"
                    )
                except Exception:
                    df = pd.DataFrame() # 发生异常时设为空，以便进入下面的 ETF 逻辑
                
                # 2. 如果返回数据为空（可能是 ETF 或场内基金），则尝试使用 ETF 接口获取
                if df is None or df.empty:
                    df = ak.fund_etf_hist_em(
                        symbol=clean_code,
                        period="daily",
                        start_date=start_date,
                        end_date=download_end_date,
                        adjust="qfq"
                    )

                # 成功后加入随机休眠，避免高频请求被封
                time.sleep(random.uniform(2.5, 5.0)) 
                break 
                
            except Exception as e:
                if attempt < max_retries - 1:
                    # 优化防爬限制：增加基础等待时间，使用更陡峭的指数退避
                    # 第一次尝试失败等待约 10-15 秒，第二次约 20-25 秒，以此类推
                    base_wait = 10 * (2 ** attempt)
                    wait_time = base_wait + random.uniform(2.0, 5.0)
                    error_msg = str(e).replace("\n", " ")[:80] # 截取部分错误信息
                    print(f"⚠️ 抓取异常/防爬限制 ({type(e).__name__}: {error_msg}...)。等待 {wait_time:.2f} 秒后进行第 {attempt + 1} 次重试...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"❌ 下载 {symbol} 失败，已达最大重试次数。错误: {e}")

        if df.empty:
            raise ValueError(f"⚠️ {symbol} 返回数据为空，可能退市或停牌。")

        df.rename(columns=self.columns_map, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df.sort_values(by='date', ascending=True, inplace=True)
        df.reset_index(drop=True, inplace=True)

        df.to_parquet(cache_file, index=False)
        print(f"✅ [DataCenter] 数据下载并缓存成功: {symbol}")

        mask = (df['date'] >= requested_start) & (df['date'] <= requested_end)
        return df.loc[mask].copy().reset_index(drop=True)
