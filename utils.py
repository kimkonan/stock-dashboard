class ScoringEngine:
    """급등주 데이터 기반 정량 스코어 계산 엔진"""
    @staticmethod
    def calculate_momentum_score(change_rate: float, volume: int, news_count: int) -> int:
        """
        상승률, 당일 거래량 변동성, 노출 뉴스 개수를 가중 계산하여 100점 만점 점수 산출
        """
        score = 0
        
        # 1. 상승률 점수 (최대 40점)
        if change_rate >= 29.5: score += 40
        elif change_rate >= 20: score += 35
        elif change_rate >= 15: score += 30
        elif change_rate >= 11: score += 25
        else: score += 20
        
        # 2. 거래량 기반 점수 (최대 40점) -> 일반 평일 주식 거래량 수준 매핑
        if volume >= 5000000: score += 40
        elif volume >= 1000000: score += 35
        elif volume >= 500000: score += 30
        elif volume >= 100000: score += 25
        else: score += 15
        
        # 3. 뉴스 기사 노출 빈도 점수 (최대 20점)
        if news_count >= 15: score += 20
        elif news_count >= 10: score += 15
        elif news_count >= 5: score += 10
        else: score += 5
            
        return min(score, 100)