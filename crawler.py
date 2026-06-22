import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

class NaverFinanceCrawler:
    """네이버 금융 데이터 및 뉴스 수집 전문 크롤러"""
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.etf_keywords = [
            "KODEX", "TIGER", "KBSTAR", "ACE", "SOL", "ARIRANG", "HANARO", "KOSEF", 
            "레버리지", "인버스", "합성", "ETN", "스팩", "SPAC", "액티브", "선물", "인덱스", "펀드"
        ]

    def fetch_rising_stocks(self) -> pd.DataFrame:
        """전일대비 상승 종목 페이지 수집 및 필터링 (+9% 이상 단일 종목)"""
        url = "https://finance.naver.com/sise/sise_rise.naver"
        try:
            response = requests.get(url, headers=self.headers)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'lxml')
            
            table = soup.find("table", class_="type_2")
            if not table:
                return pd.DataFrame()
                
            rows = table.find_all("tr")
            stock_list = []
            
            for row in rows:
                link = row.find("a", class_="tltle")
                if not link:
                    continue
                    
                name = link.text.strip()
                if any(keyword in name for keyword in self.etf_keywords):
                    continue
                    
                href = link.get("href", "")
                ticker = href.split("code=")[-1] if "code=" in href else ""
                
                tds = row.find_all("td")
                if len(tds) < 6:
                    continue
                    
                try:
                    price_str = tds[2].text.strip().replace(",", "")
                    price = int(price_str) if price_str.isdigit() else 0
                    
                    change_str = tds[4].text.strip().replace("\n", "").replace("\t", "").replace("%", "")
                    change_rate = float(change_str)
                    
                    volume_str = tds[5].text.strip().replace(",", "")
                    volume = int(volume_str) if volume_str.isdigit() else 0
                    
                    if change_rate >= 9.0:
                        stock_list.append({
                            "name": name,
                            "ticker": ticker,
                            "change_rate": change_rate,
                            "price": price,
                            "volume": volume
                        })
                except (ValueError, IndexError):
                    continue
                    
            return pd.DataFrame(stock_list)
        except Exception:
            return pd.DataFrame()

    def fetch_stock_details(self, ticker: str) -> dict:
        """종목 코드를 기반으로 업종, 시총, PER, PBR, 기업개요를 네이버 금융에서 파싱"""
        details = {"industry": "", "market_cap": "", "per": 0.0, "pbr": 0.0, "summary": ""}
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 1. 시가총액 파싱
            market_cap_th = soup.find("th", string=re.compile("시가총액"))
            if market_cap_th:
                td = market_cap_th.find_next("td")
                if td:
                    raw_cap = td.text.strip().replace("\n", "").replace("\t", "").replace(",", "")
                    raw_cap = re.sub(r'\s+', ' ', raw_cap)
                    details["market_cap"] = raw_cap
            
            # 2. PER / PBR 파싱
            per_id = soup.find("em", id="_per")
            if per_id:
                try: details["per"] = float(per_id.text.strip().replace(",", ""))
                except ValueError: pass
                
            pbr_id = soup.find("em", id="_pbr")
            if pbr_id:
                try: details["pbr"] = float(pbr_id.text.strip().replace(",", ""))
                except ValueError: pass
            
            # 3. 주요업종 파싱
            industry_th = soup.find("th", string=re.compile("주요업종"))
            if industry_th:
                td = industry_th.find_next("td")
                if td: details["industry"] = td.text.strip()
                
            # 4. 기업개요 파싱 (인코딩 우회용 전용 탭 컴포넌트 타격)
            summary_url = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
            res_sum = requests.get(summary_url, headers=self.headers)
            res_sum.encoding = 'euc-kr'
            soup_sum = BeautifulSoup(res_sum.text, 'lxml')
            
            # 네이버 금융 coinfo summary_info 영역 추출
            summary_div = soup_sum.find("div", class_="summary_info")
            if summary_div:
                text_content = summary_div.text.strip()
                text_content = re.sub(r'\s+', ' ', text_content)
                details["summary"] = text_content
            else:
                # 메인 영역 차선책
                h4_summary = soup.find("div", class_="summary_info")
                if h4_summary:
                    details["summary"] = re.sub(r'\s+', ' ', h4_summary.text.strip())
                else:
                    details["summary"] = f"본 기업은 단일 기업 주식 종목(코드: {ticker})입니다. 당일 상세 섹터 테마 및 수급 현황을 파악하여 매매에 참고하십시오."
                
            return details
        except Exception:
            return details

    def fetch_naver_news(self, query: str) -> list:
        """네이버 뉴스 검색 섹션을 크롤링하여 최근 20개 뉴스 수집"""
        news_list = []
        for start in [1, 11]:
            url = f"https://search.naver.com/search.naver?where=news&query={query}&sm=tab_pge&sort=0&start={start}"
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'lxml')
                
                li_tags = soup.find_all("li", class_="bx")
                for li in li_tags:
                    a_tag = li.find("a", class_="news_tit")
                    if not a_tag:
                        continue
                    
                    title = a_tag.get("title") if a_tag.get("title") else a_tag.text.strip()
                    news_url = a_tag.get("href", "")
                    
                    press_tag = li.find("a", class_="info_press")
                    press = press_tag.text.strip().replace("언론사 선정", "") if press_tag else "뉴스"
                    
                    date_tags = li.find_all("span", class_="info")
                    pub_date = "방금 전"
                    for d in date_tags:
                        if "전" in d.text or "." in d.text:
                            pub_date = d.text.strip()
                            break
                            
                    news_list.append({
                        "title": title,
                        "press": press,
                        "pub_date": pub_date,
                        "url": news_url
                    })
                    if len(news_list) >= 20:
                        break
            except Exception:
                continue
            if len(news_list) >= 20:
                break
        return news_list