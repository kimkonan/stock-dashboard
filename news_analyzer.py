class KeywordNewsAnalyzer:
    """규칙 및 키워드 사전 기반 급등 사유 추론 엔진"""
    def __init__(self):
        # 딕셔너리 구조의 키워드 및 대응 모멘텀 사전
        self.rules = {
            "바이오 모멘텀": ["FDA", "임상", "승인", "신약", "바이오", "제약", "치료제", "백신", "암", "학회"],
            "수주 및 공급 계약": ["수주", "계약", "공급", "납품", "체결", "규모", "공시", "증설"],
            "AI 반도체 모멘텀": ["HBM", "엔비디아", "AI", "반도체", "CXL", "온디바이스", "삼성전자", "SK하이닉스"],
            "경영권 분쟁 및 M&A": ["경영권", "분쟁", "M&A", "인수", "합병", "지분", "공개매수", "최대주주"],
            "정부 정책 수혜": ["정부", "정책", "수혜", "국책 과제", "법안", "통과", "지원금"],
            "원자재 및 에너지": ["리튬", "니켈", "구리", "원유", "천연가스", "태양광", "풍력", "원전", "우라늄"],
            "실적 어닝 서프라이즈": ["흑자", "어닝", "최대 실적", "영업이익", "매출", "급증", "서프라이즈"],
            "초전도체 및 신소재": ["초전도체", "신소재", "맥신", "그래핀", "양자컴퓨터"]
        }

    def analyze_reasons(self, news_list: list) -> str:
        """뉴스 제목들을 스캔하여 가장 많이 중복 등장한 모멘텀 카테고리를 추론"""
        if not news_list:
            return "당일 수집된 특징 뉴스가 부족하여 기술적 수급 유입 및 순환매 장세에 의한 급등으로 추정됩니다."

        score_board = {category: 0 for category in self.rules.keys()}
        matched_keywords = []

        for news in news_list:
            title = news.get('title', '')
            for category, keywords in self.rules.items():
                for kw in keywords:
                    if kw.upper() in title.upper():
                        score_board[category] += 1
                        matched_keywords.append(kw)

        # 가장 점수가 높은 카테고리 추출
        sorted_scores = sorted(score_board.items(), key=lambda x: x[1], reverse=True)
        top_category, max_score = sorted_scores[0]

        if max_score > 0:
            unique_kw = list(set(matched_keywords))[:3]
            return f"💥 **{top_category}** (관련 키워드: {', '.join(unique_kw)}) 성격의 재료가 포착되었습니다. 관련 공시 및 후속 기사를 필히 체크하십시오."
        
        return "종합 섹터 순환매 및 대량 거래대금 유입에 기인한 기술적 급등세로 분석됩니다."