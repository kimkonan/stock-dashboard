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
        코스피/코스닥 전체 시세 페이지를 전수 조사하여 
        당일 등락률이 +9.0% 이상인 순수 기업 단일 종목만 누락 없이 수집합니다.
        (하락 종목 및 ETF/ETN 완벽 필터링)
        """
        all_stocks = []
        
        # ETF, ETN 및 파생 상품 필터링을 위한 키워드 셋
        exclude_keywords = [
            "KODEX", "TIGER", "HANARO", "ACE", "SOL", "KBSTAR", "ARIRANG", "KOSEF", "TIMEFOLIO", "PLUS",
            "ETF", "ETN", "레버리지", "인버스", "선물", "스팩", "TREX", "히어로즈", "마이티", "UNICORN"
        ]
        
        # sosok=0 (코스피), sosok=1 (코스닥)
        for sosok in [0, 1]:
            page = 1
            while True:
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(res.text, "html.parser")
                
                has_data = soup.find("table", {"class": "type_2"})
                if not has_data:
                    break
                
                rows = has_data.find_all("tr")
                valid_row_count = 0
                
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 12:
                        continue
                        
                    name_anchor = cols[1].find("a")
                    if not name_anchor:
                        continue
                        
                    name = name_anchor.text.strip()
                    
                    # ── 1️⃣ ETF / ETN 및 파생상품 거르기 ──
                    if any(keyword in name.upper() for keyword in exclude_keywords):
                        continue
                        
                    href = name_anchor.get("href", "")
                    ticker_match = re.search(r"code=(\d+)", href)
                    ticker = ticker_match.group(1) if ticker_match else ""
                    
                    if not ticker:
                        continue
                        
                    try:
                        price = int(cols[2].text.replace(",", "").strip())
                        
                        # 등락률 텍스트 정제 (%, +, - 공백 등 제거)
                        raw_change = cols[4].text.replace("%", "").strip()
                        raw_change = raw_change.replace("+", "").replace("-", "").strip()
                        change_rate = float(raw_change)
                        
                        # ── 2️⃣ 부호 판별 정밀 검증 (하락/보합 종목 완전 차단) ──
                        # 네이버 금융은 상승 종목의 등락률 td 내부에 반드시 빨간색 화살표(ico_up) 태그를 넣습니다.
                        col_html = str(cols[4])
                        if "ico_up" not in col_html and "상승" not in col_html:
                            # 상한가는 별도의 클래스나 구조를 가질 수 있으므로 추가 체크
                            if "ico_down" in col_html or "하락" in col_html or "ico_fall" in col_html:
                                continue  # 하락 종목은 패스
                            
                            # 만약 상승 화살표가 없다면 보합이거나 하락이므로 리스트에서 제외
                            continue
                            
                        volume = int(cols[9].text.replace(",", "").strip())
                    except Exception:
                        continue
                    
                    # ── 3️⃣ 당일 실질 상승률 +9.0% 이상인 종목만 최종 적재 ──
                    if change_rate >= 9.0 and change_rate <= 30.5: # 상한가 제한폭 보정
                        all_stocks.append({
                            "ticker": ticker,
                            "name": name,
                            "price": price,
                            "change_rate": change_rate,
                            "volume": volume
                        })
                    
                    valid_row_count += 1
                
                if valid_row_count == 0 or page >= 45: 
                    break
                    
                page += 1

        result_df = pd.DataFrame(all_stocks)
        if not result_df.empty:
            # 중복 데이터 제거 및 등락률 내림차순 정렬
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