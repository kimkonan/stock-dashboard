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
        네이버 금융의 당일 상승 페이지를 정밀 탐색하여
        종목명과 티커를 정확하게 1:1 매칭하고, +9.0% 이상 상승한 
        순수 단일 기업 및 우선주 종목을 누락 없이 수집합니다.
        """
        all_stocks = []
        
        exclude_keywords = [
            "KODEX", "TIGER", "HANARO", "ACE", "SOL", "KBSTAR", "ARIRANG", "KOSEF", "TIMEFOLIO", "PLUS",
            "ETF", "ETN", "레버리지", "인버스", "선물", "스팩", "TREX", "히어로즈", "마이티", "UNICORN"
        ]
        
        for sosok in [0, 1]:
            url = f"https://finance.naver.com/sise/sise_rise.naver?sosok={sosok}"
            res = requests.get(url, headers=self.headers)
            res.encoding = 'euc-kr' 
            
            soup = BeautifulSoup(res.text, "html.parser")
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
                    
                href = name_anchor.get("href", "")
                ticker_match = re.search(r"code=(\d+)", href)
                ticker = ticker_match.group(1) if ticker_match else ""
                name = name_anchor.text.strip()
                
                if not ticker or not name or name == "" or len(ticker) != 6:
                    continue
                
                if any(keyword in name.upper() for keyword in exclude_keywords):
                    continue
                    
                try:
                    price = int(cols[2].text.replace(",", "").strip())
                    raw_change = cols[4].text.replace("%", "").strip().replace("+", "").replace("-", "").strip()
                    change_rate = float(raw_change)
                    
                    col_html = str(cols[4])
                    if "ico_down" in col_html or "ico_fall" in col_html:
                        continue
                        
                    volume = int(cols[5].text.replace(",", "").strip())
                except Exception:
                    continue
                
                if change_rate >= 9.0 and change_rate <= 30.5:
                    all_stocks.append({
                        "ticker": ticker.zfill(6),
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
        """종목별 HTS 상세 내역 및 '순수 기업개요' 정밀 추출 파이프라인"""
        # 지표와 업종은 메인 페이지에서 파싱
        url_main = f"https://finance.naver.com/item/main.naver?code={ticker}"
        res_main = requests.get(url_main, headers=self.headers)
        res_main.encoding = 'euc-kr'
        soup_main = BeautifulSoup(res_main.text, "html.parser")
        
        details = {
            "industry": "N/A",
            "market_cap": "N/A",
            "per": "0.0",
            "pbr": "0.0",
            "summary": "등록된 기업 개요 요약 정보가 없습니다."
        }
        
        try:
            h4_tags = soup_main.find_all("h4")
            for h4 in h4_tags:
                if "업종명" in h4.text:
                    anchor = h4.find_next("a")
                    if anchor:
                        details["industry"] = anchor.text.strip()
                        break
            
            cap_em = soup_main.find("em", {"id": "_market_sum"})
            if cap_em:
                details["market_cap"] = cap_em.text.replace("\n", "").replace("\t", "").strip() + "억원"
                
            per_th = soup_main.find("th", text="PER")
            if per_th:
                per_td = per_th.find_next("td")
                if per_td:
                    details["per"] = per_td.text.replace(",", "").strip()
                    
            pbr_th = soup_main.find("th", text="PBR")
            if pbr_th:
                pbr_td = pbr_th.find_next("td")
                if pbr_td:
                    details["pbr"] = pbr_td.text.replace(",", "").strip()
            
            # ── 🎯 [경로 전면 수정] 기업분석 전용 페이지에서 진짜 '기업개요' 텍스트만 추출 ──
            url_coinfo = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
            res_coinfo = requests.get(url_coinfo, headers=self.headers)
            res_coinfo.encoding = 'euc-kr'
            soup_coinfo = BeautifulSoup(res_coinfo.text, "html.parser")
            
            # coinfo 페이지 내에서 summary 정보가 담긴 클래스 정밀 타겟팅
            summary_div = soup_coinfo.find("div", {"class": "summary_info"}) or soup_coinfo.find("td", {"class": "txt"})
            if summary_div:
                raw_text = summary_div.get_text(separator=" ").strip()
                cleaned_text = re.sub(r'\s+', ' ', raw_text)
                if cleaned_text:
                    details["summary"] = cleaned_text
            else:
                # 대안 서치: p 태그나 summary용 id 내부 텍스트 추적
                p_desc = soup_coinfo.find("p", {"class": "description"})
                if p_desc:
                    details["summary"] = p_desc.get_text().strip()
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