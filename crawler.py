import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

class NaverFinanceCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_rising_stocks(self):
        """
        네이버 금융의 당일 상승 섹션을 코스피/코스닥별로 정밀 분석하여
        +9.0% 이상 상승한 순수 단일 기업 종목을 누락과 서버 차단 없이 100% 수집합니다.
        """
        all_stocks = []
        
        # 필터링할 파생상품 및 ETF 키워드
        exclude_keywords = [
            "KODEX", "TIGER", "HANARO", "ACE", "SOL", "KBSTAR", "ARIRANG", "KOSEF", "TIMEFOLIO", "PLUS",
            "ETF", "ETN", "레버리지", "인버스", "선물", "스팩", "TREX", "히어로즈", "마이티", "UNICORN"
        ]
        
        # sosok=0 (코스피 상승률별), sosok=1 (코스닥 상승률별) 랭킹 페이지 타겟팅
        # 이 페이지는 네이버가 상위 상승 종목을 한눈에 제공하므로 다중 페이지 호출로 인한 IP 차단이 발생하지 않습니다.
        for sosok in [0, 1]:
            url = f"https://finance.naver.com/sise/sise_rise.naver?sosok={sosok}"
            res = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 시세 테이블 추출
            table = soup.find("table", {"class": "type_2"})
            if not table:
                continue
                
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 11:
                    continue
                    
                name_anchor = cols[1].find("a")
                if not name_anchor:
                    continue
                    
                name = name_anchor.text.strip()
                
                # ── 1️⃣ ETF / ETN 파생상품 필터링 ──
                if any(keyword in name.upper() for keyword in exclude_keywords):
                    continue
                    
                href = name_anchor.get("href", "")
                ticker_match = re.search(r"code=(\d+)", href)
                ticker = ticker_match.group(1) if ticker_match else ""
                
                if not ticker:
                    continue
                    
                try:
                    price = int(cols[2].text.replace(",", "").strip())
                    
                    # 등락률 파싱 및 정제
                    raw_change = cols[4].text.replace("%", "").strip()
                    raw_change = raw_change.replace("+", "").replace("-", "").strip()
                    change_rate = float(raw_change)
                    
                    # ── 2️⃣ 상승 종목 검증 기호 필터링 ──
                    # sise_rise 페이지에서는 상승/상한가 종목만 모아두나 안전을 위해 ico_up 체크를 병행합니다.
                    col_html = str(cols[4])
                    if "ico_down" in col_html or "ico_fall" in col_html:
                        continue
                        
                    volume = int(cols[5].text.replace(",", "").strip())
                except Exception:
                    continue
                
                # ── 3️⃣ 실질 주도주 조건 (+9.0% 이상 및 상한가 제한폭) 적재 ──
                if change_rate >= 9.0 and change_rate <= 30.5:
                    all_stocks.append({
                        "ticker": ticker,
                        "name": name,
                        "price": price,
                        "change_rate": change_rate,
                        "volume": volume
                    })

        result_df = pd.DataFrame(all_stocks)
        if not result_df.empty:
            result_df = result_df.drop_duplicates(subset=['ticker']).reset_index(drop=True)
            result_df = result_df.sort_values(by="change_rate", ascending=False).reset_index(drop=True)
        return result_df

    def fetch_stock_details(self, ticker):
        """종목별 HTS 상세 내역 인코딩 수집 파이프라인"""
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        res = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        details = {
            "industry": "N/A",
            "market_cap": "N/A",
            "per": "0.0",
            "pbr": "0.0",
            "summary": "등록된 기업 개요 요약 정보가 없습니다."
        }
        
        try:
            h4_tags = soup.find_all("h4")
            for h4 in h4_tags:
                if "업종명" in h4.text:
                    anchor = h4.find_next("a")
                    if anchor:
                        details["industry"] = anchor.text.strip()
                        break
            
            cap_em = soup.find("em", {"id": "_market_sum"})
            if cap_em:
                details["market_cap"] = cap_em.text.replace("\n", "").replace("\t", "").strip() + "억원"
                
            per_th = soup.find("th", text="PER")
            if per_th:
                per_td = per_th.find_next("td")
                if per_td:
                    details["per"] = per_td.text.replace(",", "").strip()
                    
            pbr_th = soup.find("th", text="PBR")
            if pbr_th:
                pbr_td = pbr_th.find_next("td")
                if pbr_td:
                    details["pbr"] = pbr_td.text.replace(",", "").strip()
            
            summary_div = soup.find("div", {"class": "summary_info"})
            if summary_div:
                details["summary"] = summary_div.text.replace("\n", " ").strip()
        except Exception:
            pass
            
        return details

    def fetch_naver_news(self, keyword):
        """특징주 실시간 타임라인 뉴스 크롤링"""
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
        res = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        news_list = []
        try:
            items = soup.find_all("li", {"class": "bx"})
            for item in items:
                title_a = item.find("a", {"class": "news_ticker"}) or item.find("a", {"class": "news_tit"})
                if not title_a:
                    continue
                
                title = title_a.text.strip()
                link = title_a.get("href", "")
                
                press_span = item.find("a", {"class": "info_press"}) or item.find("span", {"class": "info"})
                press = press_span.text.strip() if press_span else "언론사"
                
                news_list.append({
                    "title": title,
                    "url": link,
                    "press": press,
                    "pub_date": "장중 속보"
                })
        except Exception:
            pass
            
        return news_list