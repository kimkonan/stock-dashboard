import sqlite3
import pandas as pd
from datetime import datetime

class DatabaseManager:
    """SQLite 데이터베이스를 관리하는 클래스"""
    def __init__(self, db_path="stocks.db"):
        self.db_path = db_path
        self.init_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_tables(self):
        """필요한 모든 테이블을 자동 생성"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 급등주 수집 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    name TEXT,
                    ticker TEXT,
                    change_rate REAL,
                    price INTEGER,
                    volume INTEGER,
                    industry TEXT,
                    market_cap TEXT,
                    per REAL,
                    pbr REAL,
                    summary TEXT,
                    UNIQUE(date, ticker)
                )
            """)
            
            # 2. 즐겨찾기(관심종목) 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    added_at TEXT
                )
            """)
            
            # 3. 매매일지 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    ticker TEXT,
                    buy_reason TEXT,
                    sell_reason TEXT,
                    review TEXT,
                    free_memo TEXT,
                    updated_at TEXT,
                    UNIQUE(date, ticker)
                )
            """)
            
            # 4. 뉴스 캐시 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    title TEXT,
                    press TEXT,
                    pub_date TEXT,
                    url TEXT,
                    cached_at TEXT
                )
            """)
            conn.commit()

    # --- Stocks 관련 메서드 ---
    def save_stocks(self, date_str, df: pd.DataFrame):
        if df.empty:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO stocks (date, name, ticker, change_rate, price, volume, industry, market_cap, per, pbr, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, ticker) DO UPDATE SET
                        change_rate=excluded.change_rate,
                        price=excluded.price,
                        volume=excluded.volume,
                        industry=CASE WHEN excluded.industry IS NOT NULL AND excluded.industry != '' THEN excluded.industry ELSE stocks.industry END,
                        market_cap=CASE WHEN excluded.market_cap IS NOT NULL AND excluded.market_cap != '' THEN excluded.market_cap ELSE stocks.market_cap END,
                        per=CASE WHEN excluded.per IS NOT NULL AND excluded.per != 0 THEN excluded.per ELSE stocks.per END,
                        pbr=CASE WHEN excluded.pbr IS NOT NULL AND excluded.pbr != 0 THEN excluded.pbr ELSE stocks.pbr END,
                        summary=CASE WHEN excluded.summary IS NOT NULL AND excluded.summary != '' THEN excluded.summary ELSE stocks.summary END
                """, (
                    date_str, row['name'], row['ticker'], row['change_rate'], row['price'], row['volume'],
                    row.get('industry', ''), row.get('market_cap', ''), row.get('per', 0.0), row.get('pbr', 0.0), row.get('summary', '')
                ))
            conn.commit()

    def get_stocks_by_date(self, date_str):
        with self.get_connection() as conn:
            query = "SELECT * FROM stocks WHERE date = ? ORDER BY change_rate DESC"
            return pd.read_sql_query(query, conn, params=(date_str,))

    def update_stock_detail(self, date_str, ticker, detail_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE stocks 
                SET industry=?, market_cap=?, per=?, pbr=?, summary=? 
                WHERE date=? AND ticker=?
            """, (
                detail_dict.get('industry', ''),
                detail_dict.get('market_cap', ''),
                detail_dict.get('per', 0.0),
                detail_dict.get('pbr', 0.0),
                detail_dict.get('summary', ''),
                date_str, ticker
            ))
            conn.commit()

    # --- 즐겨찾기 관련 메서드 ---
    def add_favorite(self, ticker, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT OR IGNORE INTO favorites (ticker, name, added_at) VALUES (?, ?, ?)
            """, (ticker, name, now))
            conn.commit()

    def remove_favorite(self, ticker):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorites WHERE ticker = ?", (ticker,))
            conn.commit()

    def get_favorites(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM favorites ORDER BY added_at DESC", conn)

    def is_favorite(self, ticker):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM favorites WHERE ticker = ?", (ticker,))
            return cursor.fetchone() is not None

    # --- 매매일지 관련 메서드 ---
    def save_memo(self, date_str, ticker, buy_reason, sell_reason, review, free_memo):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO memo (date, ticker, buy_reason, sell_reason, review, free_memo, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    buy_reason=excluded.buy_reason,
                    sell_reason=excluded.sell_reason,
                    review=excluded.review,
                    free_memo=excluded.free_memo,
                    updated_at=excluded.updated_at
            """, (date_str, ticker, buy_reason, sell_reason, review, free_memo, now))
            conn.commit()

    def get_memo(self, date_str, ticker):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT buy_reason, sell_reason, review, free_memo FROM memo WHERE date=? AND ticker=?", (date_str, ticker))
            row = cursor.fetchone()
            if row:
                return {"buy_reason": row[0], "sell_reason": row[1], "review": row[2], "free_memo": row[3]}
            return {"buy_reason": "", "sell_reason": "", "review": "", "free_memo": ""}

    # --- 뉴스 캐시 관련 메서드 ---
    def save_news_cache(self, ticker, news_list):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news_cache WHERE ticker = ?", (ticker,))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for news in news_list:
                cursor.execute("""
                    INSERT INTO news_cache (ticker, title, press, pub_date, url, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticker, news['title'], news['press'], news['pub_date'], news['url'], now))
            conn.commit()

    def get_cached_news(self, ticker):
        with self.get_connection() as conn:
            query = "SELECT title, press, pub_date, url FROM news_cache WHERE ticker = ?"
            return pd.read_sql_query(query, conn, params=(ticker,)).to_dict(orient='records')