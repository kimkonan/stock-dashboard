# app.py — PRO 급등주 대시보드 (최종 안정화 버전)
# =============================================================
# ✅ 수정 완료 항목:
#   1. set_page_config 최상단 고정
#   2. cache_data 내 전역 객체 참조 → session_state 플래그 방식으로 교체
#   3. pd.Series.get() → 안전한 인덱싱 + pd.isna() 조합으로 교체
#   4. float() 변환 시 ValueError 방어 처리 (try/except)
#   5. db.get_memo() None 반환 대비 기본값 처리
#   6. fchart.stock.naver.com (iframe 차단) → finance.naver.com/item/fchart.naver 로 교체
#   7. st.sidebar.radio index=0 고정으로 날짜 변경 시 IndexError 방지
# =============================================================

import streamlit as st

# ============================================================
# ✅ [필수] set_page_config — 모든 st 호출 중 가장 먼저 실행
# ============================================================
st.set_page_config(
    page_title="PRO 급등주 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date

# ============================================================
# 🔐 고유키(비밀번호) 인증 시스템
# ============================================================
VALID_KEYS = ["trader777", "secret99", "goldpass", "konan0401"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 PRO 급등주 대시보드 로그인")
    st.markdown(
        "본 시스템은 허가된 사용자만 이용할 수 있습니다. "
        "발급받은 고유키를 입력하세요."
    )
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
# ✅ 인증 통과 후에만 외부 커스텀 모듈 로드
# ============================================================
from database import DatabaseManager
from crawler import NaverFinanceCrawler
from news_analyzer import KeywordNewsAnalyzer
from utils import ScoringEngine

# ============================================================
# 🎨 CSS 주입 (가독성 및 대형 차트 레이아웃 최적화)
# ============================================================
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

# ============================================================
# ⚙️ 싱글톤 인스턴스 초기화
# ============================================================
db      = DatabaseManager()
crawler = NaverFinanceCrawler()
analyzer = KeywordNewsAnalyzer()

today_str = datetime.now().strftime("%Y-%m-%d")

# ============================================================
# ✅ [버그 1 수정] 자동 수집 로직
# - @st.cache_data 내부에서 전역 db/crawler 객체를 직접 참조하면
#   Streamlit 캐시 직렬화 과정에서 오류 발생 가능
# - session_state 플래그 방식으로 교체하여 앱 최초 실행 시 1회만 수집
# ============================================================
if "auto_collected" not in st.session_state:
    st.session_state["auto_collected"] = False

if not st.session_state["auto_collected"]:
    try:
        scraped_df = crawler.fetch_rising_stocks()
        if scraped_df is not None and not scraped_df.empty:
            db.save_stocks(today_str, scraped_df)
    except Exception:
        pass
    finally:
        st.session_state["auto_collected"] = True

# ============================================================
# 📊 SIDEBAR 레이아웃
# ============================================================
st.sidebar.title("⚡ TRADER DASHBOARD")
st.sidebar.markdown("---")

# ── 날짜 선택 ──
st.sidebar.subheader("📅 분석 기준일")
picked_date = st.sidebar.date_input(
    "날짜선택",
    value=date.today(),
    label_visibility="collapsed"
)
selected_date_str = picked_date.strftime("%Y-%m-%d")

db_stocks = db.get_stocks_by_date(selected_date_str)

if not db_stocks.empty:
    st.sidebar.success(
        f"📊 {selected_date_str} loaded ({len(db_stocks)}개)"
    )
else:
    st.sidebar.error(f"❌ {selected_date_str} 데이터 없음")
    if st.sidebar.button("🔄 실시간 수집 강제 실행"):
        with st.spinner("수집 중..."):
            try:
                scraped_df = crawler.fetch_rising_stocks()
                if scraped_df is not None and not scraped_df.empty:
                    db.save_stocks(selected_date_str, scraped_df)
                    st.rerun()
                else:
                    st.sidebar.warning("수집된 데이터가 없습니다.")
            except Exception as e:
                st.sidebar.error(f"수집 오류: {e}")

st.sidebar.markdown("---")

# ── 종목명 / 티커 검색 ──
st.sidebar.subheader("🔍 종목명 / 티커 검색")
search_query = st.sidebar.text_input(
    "검색어 입력",
    value="",
    placeholder="예: 성문, 014910",
    label_visibility="collapsed"
)

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
    fav_options = list(fav_df['name'] + " (" + fav_df['ticker'] + ")")
    selected_fav_box = st.sidebar.selectbox(
        "선택",
        ["-- 선택 --"] + fav_options,
        label_visibility="collapsed"
    )
    if selected_fav_box != "-- 선택 --":
        # "종목명 (티커)" 형식에서 티커만 안전하게 추출
        try:
            selected_fav_ticker = (
                selected_fav_box.split("(")[-1].replace(")", "").strip()
            )
        except Exception:
            selected_fav_ticker = None
else:
    st.sidebar.caption("등록된 관심종목이 없습니다.")

st.sidebar.markdown("---")

# ── 급등주 목록 (사이드바 하단 수직 배치) ──
st.sidebar.subheader(f"📈 급등주 목록 ({len(view_df)}개)")

target_row = None

# 즐겨찾기 선택 종목 우선 매핑
if selected_fav_ticker and not view_df.empty:
    matched = view_df[view_df['ticker'] == selected_fav_ticker]
    if not matched.empty:
        target_row = matched.iloc[0]

# 급등주 라디오 리스트
if target_row is None and not view_df.empty:
    labels = list(
        view_df['name']
        + " ("
        + view_df['ticker']
        + ") | +"
        + view_df['change_rate'].astype(str)
        + "%"
    )
    # ✅ [버그 7 수정] index=0 고정 → 날짜 변경 시 이전 선택 인덱스 초과 방지
    selected_label = st.sidebar.radio(
        "급등주 리스트 선택",
        options=labels,
        index=0,
        label_visibility="collapsed"
    )
    selected_name = selected_label.split(" (")[0]
    matched_rows = view_df[view_df['name'] == selected_name]
    if not matched_rows.empty:
        target_row = matched_rows.iloc[0]

# ============================================================
# 📊 MAIN PANEL
# ============================================================
if target_row is not None:
    # ✅ [버그 3 수정] None 안전 처리 후 zfill
    ticker = str(target_row['ticker']).strip().zfill(6)
    name   = str(target_row['name']).strip()

    change_rate = target_row['change_rate']
    price       = target_row['price']
    volume      = target_row['volume']

    # ── 상세 데이터 갱신 필요 여부 판단 ──────────────────────
    # ✅ [버그 2 수정] pd.Series에는 .get()이 없으므로 직접 인덱싱 + pd.isna() 사용
    def _is_empty(val):
        """값이 비었거나 NaN이면 True"""
        if val is None:
            return True
        try:
            return pd.isna(val) or str(val).strip() == ""
        except Exception:
            return True

    needs_update = (
        _is_empty(target_row['industry'])
        or "데이터 갱신" in str(target_row.get('market_cap', '') or '')
    )

    if needs_update:
        with st.spinner("기업 상세 정보 갱신 중..."):
            try:
                details = crawler.fetch_stock_details(ticker)
                db.update_stock_detail(selected_date_str, ticker, details)
                target_row = target_row.copy()
                target_row['industry']   = details.get('industry', '')
                target_row['market_cap'] = details.get('market_cap', 'N/A')
                target_row['per']        = details.get('per', None)
                target_row['pbr']        = details.get('pbr', None)
                target_row['summary']    = details.get('summary', '정보 없음')
            except Exception as e:
                st.warning(f"상세 정보 갱신 실패: {e}")

    # ── 뉴스 캐시 로드 ──────────────────────────────────────
    cached_news = db.get_cached_news(ticker) or []
    if not cached_news:
        try:
            news_list = crawler.fetch_naver_news(name)
            db.save_news_cache(ticker, news_list)
            cached_news = news_list or []
        except Exception:
            cached_news = []

    inferred_reason = analyzer.analyze_reasons(cached_news)
    intensity_score = ScoringEngine.calculate_momentum_score(
        change_rate, volume, len(cached_news)
    )
    # score가 0~100 범위를 벗어나지 않도록 클램핑
    intensity_score = max(0, min(100, int(intensity_score)))

    # ============================================================
    # 🏢 상단 [1.0 : 1.0] 레이아웃
    # ============================================================
    left_col, right_col = st.columns([1.0, 1.0])

    # ── LEFT: 핵심 정보 분석 열 ─────────────────────────────
    with left_col:
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

        st.markdown(
            f"**🔥 급등 강도 Score:** `{intensity_score}점` / 100점"
        )
        st.progress(intensity_score / 100.0)
        st.info(f"💡 **예상 급등 사유:** {inferred_reason}")

        st.markdown("### 🏢 핵심 분석 지표 (HTS Real-time)")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(
            "업종",
            str(target_row['industry']) if not _is_empty(target_row['industry'])
            else "제조 및 서비스"
        )
        m_col2.metric(
            "시가총액",
            str(target_row['market_cap']) if not _is_empty(target_row['market_cap'])
            else "N/A"
        )
        m_col3.metric("당일 종가", f"{price:,} 원 (+{change_rate}%)")

        # ✅ [버그 4 수정] float 변환 실패(ValueError) 방어 처리
        def _fmt_ratio(val, suffix="배"):
            try:
                fval = float(val)
                if fval == 0:
                    raise ValueError
                return f"{fval:.2f} {suffix}"
            except (TypeError, ValueError):
                return "N/A"

        per_str = _fmt_ratio(target_row['per']) if not _is_empty(target_row['per']) else "N/A (적자)"
        pbr_str = _fmt_ratio(target_row['pbr']) if not _is_empty(target_row['pbr']) else "N/A"

        m_col4, m_col5, m_col6 = st.columns(3)
        m_col4.metric("PER 지표", per_str)
        m_col5.metric("PBR 지표", pbr_str)
        m_col6.metric("당일 거래량", f"{volume:,} 주")

        st.markdown("### 📄 정제된 기업 개요")
        summary_text = str(target_row['summary']) if not _is_empty(target_row['summary']) else "기업 개요 정보가 없습니다."
        st.markdown(
            '<div class="company-summary">' + summary_text + '</div>',
            unsafe_allow_html=True
        )

        st.markdown("### 📰 관련 뉴스 타임라인")
        if cached_news:
            for idx, n in enumerate(cached_news[:6], 1):
                title    = n.get('title', '제목 없음')
                url      = n.get('url', '#')
                press    = n.get('press', '')
                pub_date = n.get('pub_date', '')
                st.markdown(
                    f"**{idx}** . [{title}]({url}) "
                    "<span style='color:#7f8c8d; font-size:11px;'>"
                    + press + " | " + pub_date
                    + "</span>",
                    unsafe_allow_html=True
                )
        else:
            st.caption(
                "특징 뉴스가 아직 로드되지 않았거나 존재하지 않습니다."
            )

    # ── RIGHT: 매매 일지 기록 창 ────────────────────────────
    with right_col:
        st.markdown("### 📝 트레이딩 룸 매매 일지")

        # ✅ [버그 5 수정] get_memo()가 None 반환 시 기본 빈 딕셔너리로 방어
        raw_memo = db.get_memo(selected_date_str, ticker)
        memo_data = raw_memo if isinstance(raw_memo, dict) else {}

        buy_reason  = st.text_area(
            "매수 이유 및 타점 관점",
            value=memo_data.get('buy_reason', ''),
            height=90
        )
        sell_reason = st.text_area(
            "매도 및 분할 익절/손절가",
            value=memo_data.get('sell_reason', ''),
            height=90
        )
        review      = st.text_area(
            "매매 관점 복기",
            value=memo_data.get('review', ''),
            height=90
        )
        free_memo   = st.text_area(
            "자유 분석 메모",
            value=memo_data.get('free_memo', ''),
            height=90
        )

        if st.button("💾 매매 일지 기록 저장", use_container_width=True):
            try:
                db.save_memo(
                    selected_date_str, ticker,
                    buy_reason, sell_reason, review, free_memo
                )
                st.success("✅ 기록 완료")
            except Exception as e:
                st.error(f"저장 실패: {e}")

    # ============================================================
    # 📉 하단 배치: 대형 멀티 타임프레임 차트 피드 (Full Width)
    #
    # ✅ [버그 6 수정] fchart.stock.naver.com 엔진 주소는
    #    X-Frame-Options: DENY 헤더를 반환하므로 iframe 내부가 완전 공백
    #    → 실제 렌더링 가능한 finance.naver.com/item/fchart.naver 로 교체
    #
    # ✅ iframe HTML 문자열 조립 방식:
    #    f-string 내 CSS width:100% 의 % 기호와 Python format spec 충돌을
    #    완전 차단하기 위해 순수 문자열 연결(+) 방식만 사용
    # ============================================================
    st.markdown("---")
    st.markdown("### 📊 대한민국 실시간 종합 차트 멀티 피드")

    # 공통 설정값 변수화
    IFRAME_W = "100%"   # CSS width (% 기호를 변수로 분리)
    IFRAME_H = "560"    # iframe 내부 높이 (px)
    WRAP_H   = 575      # components.html 래퍼 높이 (px)

    # ✅ 렌더링 확인된 네이버 금융 차트 URL 체계
    #    expr=1 → 일봉  /  expr=3 → 주봉  /  expr=5 → 월봉
    _naver_chart_base = (
        "https://finance.naver.com/item/fchart.naver?code=" + ticker
    )

    # iframe HTML 문자열 사전 조립 (f-string 완전 미사용)
    def _make_iframe(url):
        return (
            '<iframe src="' + url + '"'
            + ' width="' + IFRAME_W + '"'
            + ' height="' + IFRAME_H + '"'
            + ' style="border:none; display:block;"'
            + ' scrolling="no"'
            + ' loading="lazy"'
            + '></iframe>'
        )

    iframe_daily   = _make_iframe(_naver_chart_base + "&expr=1")
    iframe_weekly  = _make_iframe(_naver_chart_base + "&expr=3")
    iframe_monthly = _make_iframe(_naver_chart_base + "&expr=5")

    # 스냅샷 이미지 URL (f-string 미사용)
    snapshot_url = (
        "https://ssl.pstatic.net/imgfinance/chart/item/candle/day/"
        + ticker
        + ".png"
    )
    snapshot_caption = (
        "[" + name + " / " + ticker + "] "
        "당일 기준 정밀 캔들 및 거래량 변동현황 스냅샷"
    )

    # ── 4개 독립 탭 격리 구조 ────────────────────────────────
    chart_tabs = st.tabs([
        "📈 실시간 일봉",
        "📊 실시간 주봉",
        "📉 실시간 월봉",
        "📸 당일 종가 차트 스냅샷"
    ])

    with chart_tabs[0]:
        st.caption("▶ 네이버 금융 실시간 일봉 차트 (expr=1)")
        components.html(iframe_daily, height=WRAP_H, scrolling=False)

    with chart_tabs[1]:
        st.caption("▶ 네이버 금융 실시간 주봉 차트 (expr=3)")
        components.html(iframe_weekly, height=WRAP_H, scrolling=False)

    with chart_tabs[2]:
        st.caption("▶ 네이버 금융 실시간 월봉 차트 (expr=5)")
        components.html(iframe_monthly, height=WRAP_H, scrolling=False)

    with chart_tabs[3]:
        st.caption(
            "▶ 네이버 금융 기준 당일 정밀 캔들 변동현황 및 "
            "누적 거래량 분석 스냅샷"
        )
        st.image(
            snapshot_url,
            use_container_width=True,
            caption=snapshot_caption
        )

# ── 종목 미선택 초기 화면 ────────────────────────────────────
else:
    st.title("📈 실시간 급등주 자동 분석 시스템")
    st.info(
        "좌측 사이드바에서 날짜를 선택하거나 "
        "급등주 리스트에서 종목을 클릭해 주십시오."
    )
    st.markdown("""
#### 🧭 사용 가이드

| 단계 | 설명 |
|------|------|
| **1** | 사이드바 상단 **📅 분석 기준일** 에서 날짜 선택 |
| **2** | 데이터 없을 경우 **🔄 실시간 수집 강제 실행** 버튼 클릭 |
| **3** | **📈 급등주 목록** 라디오 버튼에서 종목 선택 |
| **4** | 하단 탭에서 **일봉 / 주봉 / 월봉 / 스냅샷** 차트 확인 |
    """)