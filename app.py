import streamlit as st

# ============================================================
# ✅ 페이지 설정 - 최상단 고정 (모든 st 호출 및 임포트보다 먼저 실행)
# ============================================================
st.set_page_config(
    page_title="PRO 급등주 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date
import os

# ============================================================
# 🔐 고유키(비밀번호) 인증 시스템 (konan0401 포함)
# ============================================================
VALID_KEYS = ["trader777", "secret99", "goldpass", "konan0401"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 PRO 급등주 대시보드 로그인")
    st.markdown("본 시스템은 허가된 사용자만 이용할 수 있습니다. 발급받은 고유키를 입력하세요.")

    user_key = st.text_input(
        "고유 라이선스 키 입력",
        type="password",
        placeholder="Access Key를 입력하세요."
    )
    if st.button("인증하기", use_container_width=True):
        if user_key in VALID_KEYS:
            st.session_state["authenticated"] = True
            st.success("인증 성공! 대시보드를 로드합니다.")
            st.rerun()
        else:
            st.error("올바르지 않은 고유키입니다. 발급자에게 문의하세요.")
    st.stop()

# ============================================================
# ✅ 인증 완료 후 코어 모듈 임포트
# ============================================================
from database import DatabaseManager
from crawler import NaverFinanceCrawler
from news_analyzer import KeywordNewsAnalyzer
from utils import ScoringEngine

# 🎨 대시보드 가독성 최적화 CSS 주입
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        html, body, [data-testid="stSidebar"] {
            font-family: 'Inter', -apple-system, sans-serif !important;
        }
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.2rem !important;
        }
        h3 {
            font-size: 1.3rem !important;
            font-weight: 600 !important;
            border-left: 4px solid #ff4b4b;
            padding-left: 8px;
            margin-top: 1.2rem !important;
            margin-bottom: 0.8rem !important;
        }
        .stMetric {
            background-color: #1e2530;
            padding: 8px 12px !important;
            border-radius: 6px;
            border: 1px solid #2d3748;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
            color: #a0aec0 !important;
        }
        .company-summary {
            background-color: #141923;
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #4a5568;
            font-size: 0.92rem !important;
            line-height: 1.5 !important;
            color: #e2e8f0;
            margin-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

# ⚙️ 싱글톤 인스턴스 초기화
db = DatabaseManager()
crawler = NaverFinanceCrawler()
analyzer = KeywordNewsAnalyzer()

today_str = datetime.now().strftime("%Y-%m-%d")

@st.cache_data(ttl=600)
def run_auto_collection(date_key):
    try:
        scraped_df = crawler.fetch_rising_stocks()
        if not scraped_df.empty:
            db.save_stocks(date_key, scraped_df)
    except Exception:
        pass

run_auto_collection(today_str)

# ============================================================
# 📊 SIDEBAR 레이아웃 구현 (급등주 목록 하단 배치)
# ============================================================
st.sidebar.title("⚡ TRADER DASHBOARD")
st.sidebar.markdown("---")

# ── 날짜 선택 ──
st.sidebar.subheader("📅 분석 기준일")
picked_date = st.sidebar.date_input("날짜선택", value=date.today(), label_visibility="collapsed")
selected_date_str = picked_date.strftime("%Y-%m-%d")

db_stocks = db.get_stocks_by_date(selected_date_str)

if not db_stocks.empty:
    st.sidebar.success(f"📊 {selected_date_str} loaded ({len(db_stocks)}개)")
else:
    st.sidebar.error(f"❌ {selected_date_str} 데이터 없음")
    if st.sidebar.button("🔄 실시간 수집 강제 실행"):
        with st.spinner("수집 중..."):
            scraped_df = crawler.fetch_rising_stocks()
            if not scraped_df.empty:
                db.save_stocks(selected_date_str, scraped_df)
                st.rerun()

st.sidebar.markdown("---")

# ── 종목명 / 티커 검색 ──
st.sidebar.subheader("🔍 종목명 / 티커 검색")
search_query = st.sidebar.text_input("검색어 입력", value="", placeholder="예: 성문, 014910", label_visibility="collapsed")

view_df = db_stocks.copy()
if search_query and not view_df.empty:
    view_df = view_df[
        view_df['name'].str.contains(search_query, case=False, na=False) |
        view_df['ticker'].str.contains(search_query, na=False)
    ].reset_index(drop=True)

st.sidebar.markdown("---")

# ── 관심종목 즐겨찾기 ──
st.sidebar.subheader("⭐ 관심종목 (즐겨찾기)")
fav_df = db.get_favorites()
selected_fav_ticker = None

if not fav_df.empty:
    fav_options = fav_df['name'] + " (" + fav_df['ticker'] + ")"
    selected_fav_box = st.sidebar.selectbox("선택", ["-- 선택 --"] + list(fav_options), label_visibility="collapsed")
    if selected_fav_box != "-- 선택 --":
        selected_fav_ticker = selected_fav_box.split("(")[1].replace(")", "").strip()
else:
    st.sidebar.caption("등록된 관심종목이 없습니다.")

st.sidebar.markdown("---")

# ── 급등주 목록 ──
st.sidebar.subheader(f"📈 급등주 목록 ({len(view_df)}개)")

target_row = None

if selected_fav_ticker and not view_df.empty:
    matched = view_df[view_df['ticker'] == selected_fav_ticker]
    if not matched.empty:
        target_row = matched.iloc[0]

if target_row is None and not view_df.empty:
    labels = view_df['name'] + " (" + view_df['ticker'] + ") | +" + view_df['change_rate'].astype(str) + "%"
    selected_label = st.sidebar.radio("급등주 리스트 선택", options=list(labels), label_visibility="collapsed")
    selected_name = selected_label.split(" (")[0]
    target_row = view_df[view_df['name'] == selected_name].iloc[0]

# ============================================================
# 📊 MAIN PANEL 레이아웃 구현
# ============================================================
if target_row is not None:
    ticker = str(target_row['ticker']).strip().zfill(6)
    name = str(target_row['name'])
    change_rate = target_row['change_rate']
    price = target_row['price']
    volume = target_row['volume']

    if not target_row.get('industry') or "데이터 갱신" in str(target_row.get('market_cap', '')):
        with st.spinner("기업 상세 정보 인코딩 정밀 갱신 중..."):
            details = crawler.fetch_stock_details(ticker)
            db.update_stock_detail(selected_date_str, ticker, details)
            target_row = target_row.copy()
            target_row['industry'] = details['industry']
            target_row['market_cap'] = details['market_cap']
            target_row['per'] = details['per']
            target_row['pbr'] = details['pbr']
            target_row['summary'] = details['summary']

    cached_news = db.get_cached_news(ticker)
    if not cached_news:
        news_list = crawler.fetch_naver_news(name)
        db.save_news_cache(ticker, news_list)
        cached_news = news_list

    inferred_reason = analyzer.analyze_reasons(cached_news)
    intensity_score = ScoringEngine.calculate_momentum_score(change_rate, volume, len(cached_news))

    # 🏢 상단 분할 레이아웃 [1.2 : 0.8]
    left_col, right_col = st.columns([1.2, 0.8])

    with left_col:
        # ── [요청 완벽 반영] 당일 종가 차트 스냅샷을 왼쪽 상단 메인 영역에 확실히 고정 ──
        st.markdown("### 📉 네이버 금융 기준 당일 거래 현황")
        st.image(
            "https://ssl.pstatic.net/imgfinance/chart/item/candle/day/" + ticker + ".png", 
            use_container_width=True, 
            caption="당일 기준 정밀 캔들 및 거래량 변동현황 스냅샷"
        )
        st.markdown("---")

        title_sub_col1, title_sub_col2 = st.columns([3, 1])
        with title_sub_col1:
            st.title(f"{name} ({ticker})")
        with title_sub_col2:
            is_fav = db.is_favorite(ticker)
            if is_fav:
                if st.button("⭐ 즐겨찾기 해제", use_container_width=True):
                    db.remove_favorite(ticker)
                    st.rerun()
            else:
                if st.button("➕ 관심등록", use_container_width=True):
                    db.add_favorite(ticker, name)
                    st.rerun()

        st.markdown(f"**🔥 급등 강도 Score:** `{intensity_score}점` / 100점")
        st.progress(intensity_score / 100.0)
        st.info(f"💡 **예상 급등 사유:** {inferred_reason}")

        st.markdown("### 🏢 핵심 분석 지표 (HTS Real-time)")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("업종", target_row['industry'] if target_row['industry'] else "제조 및 서비스")
        m_col2.metric("시가총액", target_row['market_cap'] if target_row['market_cap'] else "N/A")
        m_col3.metric("당일 종가", f"{price:,} 원 (+{change_rate}%)")

        per_val = target_row['per']
        pbr_val = target_row['pbr']
        per_str = f"{float(per_val):.2f} 배" if per_val and pd.notna(per_val) and float(per_val) != 0 else "N/A (적자)"
        pbr_str = f"{float(pbr_val):.2f} 배" if pbr_val and pd.notna(pbr_val) and float(pbr_val) != 0 else "N/A"

        m_col4, m_col5, m_col6 = st.columns(3)
        m_col4.metric("PER 지표", per_str)
        m_col5.metric("PBR 지표", pbr_str)
        m_col6.metric("당일 거래량", f"{volume:,} 주")

        st.markdown("### 📄 정제된 기업 개요")
        st.markdown(f'<div class="company-summary">{target_row["summary"]}</div>', unsafe_allow_html=True)

        st.markdown("### 📰 관련 뉴스 타임라인")
        if cached_news:
            for idx, n in enumerate(cached_news[:6], 1):
                st.markdown(f"**{idx}** . [{n['title']}]({n['url']}) <span style='color:#7f8c8d; font-size:11px;'>{n['press']} | {n['pub_date']}</span>", unsafe_allow_html=True)
        else:
            st.caption("특징 뉴스가 아직 로드되지 않았거나 존재하지 않습니다.")

    with right_col:
        st.markdown("### 📝 트레이딩 룸 매매 일지")
        memo_data = db.get_memo(selected_date_str, ticker)

        buy_reason  = st.text_area("매수 이유 및 타점 관점", value=memo_data['buy_reason'], height=120)
        sell_reason = st.text_area("매도 및 분할 익절/손절가", value=memo_data['sell_reason'], height=120)
        review      = st.text_area("매매 관점 복기", value=memo_data['review'], height=120)
        free_memo   = st.text_area("자유 분석 메모", value=memo_data['free_memo'], height=120)

        if st.button("💾 매매 일지 기록 저장", use_container_width=True):
            db.save_memo(selected_date_str, ticker, buy_reason, sell_reason, review, free_memo)
            st.success("기록 완료")

    # ============================================================
    # 📉 하단 배치: 대형 멀티 타임프레임 차트 피드 (순수 차트만 확대 적용)
    # ============================================================
    st.markdown("---")
    st.markdown("### 📊 대한민국 실시간 종합 차트 멀티 피드")

    # 💡 [구조 최종 정립] 상단 광고 및 포털 메뉴판을 프레임 바깥으로 완전히 밀어내고
    # 오직 내부 캔들 차트실 본체만 시원하게 채워주는 제어 파라미터(&width=100%&height=100%) 주입 완료
    _base_url = "https://finance.naver.com/item/fchart.naver?code=" + ticker + "&width=100%&height=100%"
    IFRAME_W  = "100%"
    IFRAME_H  = "600" # 차트를 더 큼직하게 보기 위해 내부 프레임 높이 확대

    iframe_daily   = '<iframe src="' + _base_url + '&expr=1" width="' + IFRAME_W + '" height="' + IFRAME_H + '" style="border:none; display:block; margin-top:-140px;" scrolling="no"></iframe>'
    iframe_weekly  = '<iframe src="' + _base_url + '&expr=3" width="' + IFRAME_W + '" height="' + IFRAME_H + '" style="border:none; display:block; margin-top:-140px;" scrolling="no"></iframe>'
    iframe_monthly = '<iframe src="' + _base_url + '&expr=5" width="' + IFRAME_W + '" height="' + IFRAME_H + '" style="border:none; display:block; margin-top:-140px;" scrolling="no"></iframe>'

    chart_tabs = st.tabs(["실시간 일봉 차트실", "실시간 주봉 차트실", "실시간 월봉 차트실"])

    # margin-top 상단 여백 역연산을 통해 불필요한 포털 헤더 영역을 완전히 가리고 순수 차트만 꽉 차게 노출시킵니다.
    with chart_tabs[0]:
        components.html(iframe_daily, height=480, scrolling=False)

    with chart_tabs[1]:
        components.html(iframe_weekly, height=480, scrolling=False)

    with chart_tabs[2]:
        components.html(iframe_monthly, height=480, scrolling=False)

else:
    st.title("📈 실시간 급등주 자동 분석 시스템")
    st.info("좌측 사이드바에서 날짜를 선택하거나 주식을 리스트에서 클릭해 주십시오.")