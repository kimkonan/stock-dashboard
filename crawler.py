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
        당일 등락률이 9.0% 이상인 모든 종목을 누락 없이 수집합니다.
        """
        all_stocks = []
        
        # sosok=0 (코스피), sosok=1 (코스닥)
        for sosok in [0, 1]:
            # 안전하게 최대 5페이지까지 전수 조사 (보통 코스피 40장, 코스닥 35장 분량)
            # 네이버 시세 테이블 구조를 역추적하여 데이터 유실을 원천 차단합니다.
            page = 1
            while True:
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 페이지 끝에 도달했는지 검증 (네이버는 끝 페이지 이후 빈 페이지를 반환하거나 링크가 없음)
                has_data = soup.find("table", {"class": "type_2"})
                if not has_data:
                    break
                
                rows = has_data.find_all("tr")
                valid_row_count = 0
                
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 12:  # 네이버 표준 시세 컬럼 규격 검증
                        continue
                        
                    # 종목명 및 티커 추출
                    name_anchor = cols[1].find("a")
                    if not name_anchor:
                        continue
                        
                    name = name_anchor.text.strip()
                    href = name_anchor.get("href", "")
                    ticker_match = re.search(r"code=(\d+)", href)
                    ticker = ticker_match.group(1) if ticker_match else ""
                    
                    if not ticker:
                        continue
                        
                    # 당일 종가, 등락률, 거래량 정밀 정제
                    try:
                        price = int(cols[2].text.replace(",", "").strip())
                        
                        # 등락률 텍스트에서 플러스, 마이너스, 공백 기호 완전 제거 후 실수형 변환
                        raw_change = cols[4].text.replace("%", "").strip()
                        raw_change = raw_change.replace("+", "").replace("-", "")
                        change_rate = float(raw_change)
                        
                        # 하락/보합 종목 필터링 (네이버는 상승 종목에 ico_up 클래스나 빨간색 스타일을 씁니다)
                        # 단순 절댓값 파싱 오류를 막기 위해 td 내부의 부호 이미지를 교차 체크합니다.
                        if "ico_down" in str(cols[4]) or "ico_fall" in str(cols[4]):
                            change_rate = -change_rate
                            
                        volume = int(cols[9].text.replace(",", "").strip())
                    except Exception:
                        continue
                    
                    # 💡 [핵심 타겟 보정] 당일 상승률 9.0% 이상인 주도주만 전수 적재
                    if change_rate >= 9.0:
                        all_stocks.append({
                            "ticker": ticker,
                            "name": name,
                            "price": price,
                            "change_rate": change_rate,
                            "volume": volume
                        })
                    
                    valid_row_count += 1
                
                # 해당 페이지에 유효한 주식 데이터 행이 전혀 없으면 루프 탈출
                if valid_row_count == 0 or page >= 45: 
                    break
                    
                page += 1

        # 데이터프레임으로 변환 후 등락률이 높은 순서대로 탑 다운 정렬
        result_df = pd.DataFrame(all_stocks)
        if not result_df.empty:
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
            # 업종 분석
            h4_tags = soup.find_all("h4")
            for h4 in h4_tags:
                if "업종명" in h4.text:
                    anchor = h4.find_next("a")
                    if anchor:
                        details["industry"] = anchor.text.strip()
                        break
            
            # 시가총액 분석
            cap_em = soup.find("em", {"id": "_market_sum"})
            if cap_em:
                details["market_cap"] = cap_em.text.replace("\n", "").replace("\t", "").strip() + "억원"
                
            # PER / PBR 지표 트래킹
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
            
            # 기업 개요 파싱 데이터 결합
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