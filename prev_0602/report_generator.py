#!/usr/bin/env python3
"""
report_generator_fixed.py - 개선된 고객 수 예측과 전환율 계산
"""

import json
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class StartupInsight:
    """창업 인사이트"""
    area_name: str
    recommendation_level: str  # "강력추천", "추천", "보통", "신중검토"
    key_strengths: List[str]
    key_weaknesses: List[str]
    target_match_score: float
    expected_daily_customers: int
    expected_monthly_revenue: int
    competitor_analysis: Dict
    best_time_slots: List[str]
    startup_tips: List[str]
    risk_factors: List[str]
    total_score: float


class ReportGenerator:
    """창업자를 위한 실질적 보고서 생성기"""
    
    def __init__(self):
        self.time_slots = {
            'morning': '07:00-11:00',
            'lunch': '11:00-14:00',
            'afternoon': '14:00-17:00',
            'evening': '17:00-21:00',
            'night': '21:00-24:00'
        }
        
        # 업종별 키워드
        self.business_keywords = {
            '카페': ['카페', '커피', '음료', '디저트'],
            '음식점': ['한식', '중식', '일식', '양식', '분식'],
            '주점': ['주점', '호프', '포차'],
            '편의점': ['편의점'],
            '학원': ['학원', '교육'],
            '미용실': ['미용', '헤어', '네일'],
            '약국': ['약국'],
            '헬스장': ['스포츠', '헬스', '피트니스']
        }
    
    def generate_comprehensive_report(self, results: Dict, constraints) -> Dict:
        """종합 보고서 생성"""
        # constraints가 객체인 경우 처리
        if hasattr(constraints, 'business_type'):
            # StartupConstraints 객체인 경우
            business_type = constraints.business_type
            budget_min = constraints.budget_min
            budget_max = constraints.budget_max
            target_customers = constraints.target_customers
        else:
            # 딕셔너리인 경우
            business_type = constraints['business_type']
            budget_min = constraints['budget_min']
            budget_max = constraints['budget_max']
            target_customers = constraints['target_customers']
        
        insights = []
        
        # 상위 10개 지역 분석
        for loc in results.get('pareto_optimal', [])[:10]:
            insight = self._analyze_location(loc, constraints)
            insights.append(insight)
        
        # 보고서 생성
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'business_type': business_type,
            'budget_range': f"{budget_min:,}원 ~ {budget_max:,}원",
            'target_customers': target_customers,
            'top_recommendations': self._format_recommendations(insights[:3]),
            'detailed_analysis': self._format_detailed_analysis(insights),
            'summary_table': self._create_summary_table(insights),
                            'action_items': self._generate_action_items(insights[0] if insights else None, constraints)
        }
        
        return report
    
    def calculate_actual_conversion_rate(self, location, business_type: str) -> float:
        """실제 데이터 기반 전환율 계산 (개선된 버전)"""
        
        # 1. 해당 지역의 업종별 실제 결제 건수
        com_data = location.raw_data['commercial']
        keywords = self.business_keywords.get(business_type, [])
        
        actual_payment_count = 0
        merchant_count = 0
        
        for biz in com_data.get('business_categories', []):
            category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
            if any(kw in category for kw in keywords):
                actual_payment_count += biz.get('payment_count', 0)
                merchant_count += biz.get('merchant_count', 0)
        
        # 2. 해당 지역의 일일 유동인구
        pop_data = location.raw_data['population']
        daily_population = (pop_data.get('population_min', 0) + 
                           pop_data.get('population_max', 0)) / 2
        
        # 3. 매장당 일일 고객수 추정
        if merchant_count > 0 and actual_payment_count > 0:
            # 월 결제건수를 일 결제건수로 변환
            daily_payment_per_store = (actual_payment_count / 30) / merchant_count
            
            # 매장당 고객수 기반 전환율
            stores_per_population = merchant_count / max(daily_population, 1000)
            adjusted_conversion = daily_payment_per_store * stores_per_population / daily_population
            
            # 합리적 범위로 제한
            return min(adjusted_conversion, 0.10)  # 최대 10%
        
        # 4. 데이터가 없으면 업종별 평균 사용
        industry_averages = {
            '카페': 0.025,      # 유동인구의 2.5%
            '음식점': 0.035,    # 유동인구의 3.5%
            '편의점': 0.060,    # 유동인구의 6%
            '학원': 0.003,      # 유동인구의 0.3%
            '미용실': 0.002,    # 유동인구의 0.2%
            '약국': 0.010,      # 유동인구의 1%
            '헬스장': 0.003,    # 유동인구의 0.3%
            '주점': 0.020       # 유동인구의 2%
        }
        
        return industry_averages.get(business_type, 0.020)
    
    def estimate_realistic_price_per_customer(self, location, business_type: str, 
                                             target_min: int, target_max: int) -> dict:
        """현실적인 객단가 추정 (업종별 통계 + 지역 특성)"""
        
        # 1. 업종별 전국 평균 객단가 (실제 통계 기반)
        # 출처: 소상공인시장진흥공단, KB경영연구소
        industry_avg_prices = {
            '카페': {
                'avg': 6500,
                'premium_factor': 1.5,   # 강남/청담 등
                'economy_factor': 0.7    # 대학가/주택가 등
            },
            '음식점': {
                'avg': 13000,
                'premium_factor': 2.0,
                'economy_factor': 0.6
            },
            '편의점': {
                'avg': 4500,
                'premium_factor': 1.3,
                'economy_factor': 0.8
            },
            '학원': {
                'avg': 150000,  # 월 기준
                'premium_factor': 2.0,
                'economy_factor': 0.5
            },
            '미용실': {
                'avg': 35000,
                'premium_factor': 3.0,
                'economy_factor': 0.5
            },
            '약국': {
                'avg': 8000,
                'premium_factor': 1.5,
                'economy_factor': 0.7
            },
            '헬스장': {
                'avg': 60000,  # 월 기준
                'premium_factor': 2.5,
                'economy_factor': 0.5
            },
            '주점': {
                'avg': 30000,
                'premium_factor': 2.0,
                'economy_factor': 0.6
            }
        }
        
        base_info = industry_avg_prices.get(business_type, {
            'avg': 10000, 
            'premium_factor': 1.5, 
            'economy_factor': 0.7
        })
        
        # 2. 지역 특성에 따른 조정
        area_name = location.area_name
        area_multiplier = 1.0
        
        # 프리미엄 지역
        premium_areas = ['강남', '청담', '신사', '압구정', '한남', '성수카페거리']
        if any(area in area_name for area in premium_areas):
            area_multiplier = base_info['premium_factor']
        
        # 중급 지역
        elif any(area in area_name for area in ['홍대', '신촌', '건대', '명동', '종로', '을지로', '여의도']):
            area_multiplier = 1.2
        
        # 관광지
        elif '관광특구' in area_name:
            area_multiplier = 1.3
        
        # 대학가/저가 지역
        elif any(area in area_name for area in ['회기', '신림', '노원', '미아', '수유']):
            area_multiplier = base_info['economy_factor']
        
        # 3. 추정 객단가 계산
        estimated_price = int(base_info['avg'] * area_multiplier)
        
        # 4. 목표 가격과의 조정
        if target_min <= estimated_price <= target_max:
            final_price = estimated_price
            match_status = "perfect"
        elif estimated_price < target_min:
            # 저렴한 지역에서 프리미엄 전략
            final_price = target_min
            match_status = "below_target"
        else:
            # 비싼 지역에서 가성비 전략
            final_price = target_max
            match_status = "above_target"
        
        return {
            'estimated': int(estimated_price),
            'final': int(final_price),
            'match_status': match_status,
            'area_level': 'premium' if area_multiplier > 1.3 else 'economy' if area_multiplier < 0.8 else 'standard'
        }
    
    def _analyze_location(self, location, constraints) -> StartupInsight:
        """개별 지역 심층 분석"""
        # constraints 타입 확인 및 변환
        if hasattr(constraints, 'business_type'):
            # StartupConstraints 객체인 경우
            business_type = constraints.business_type
            budget_min = constraints.budget_min
            budget_max = constraints.budget_max
            target_customers = constraints.target_customers
        else:
            # 딕셔너리인 경우
            business_type = constraints['business_type']
            budget_min = constraints['budget_min']
            budget_max = constraints['budget_max']
            target_customers = constraints['target_customers']
        
        area_name = location.area_name
        pop_data = location.raw_data['population']
        com_data = location.raw_data['commercial']
        
        # 예상 고객 수 계산 (개선된 버전)
        daily_population = (pop_data['population_min'] + pop_data['population_max']) / 2
        
        # 실제 전환율 계산
        actual_conversion_rate = self.calculate_actual_conversion_rate(location, business_type)
        
        # 타겟 고객 보정
        target_adjustment = {
            '직장인': 0.4,   # 전체 고객의 40%
            '학생': 0.3,     # 전체 고객의 30%
            '주민': 0.2,     # 전체 고객의 20%
            '관광객': 0.1    # 전체 고객의 10%
        }
        
        # 타겟 고객 비율 계산
        target_factor = 0
        for target in target_customers:
            target_factor += target_adjustment.get(target, 0.25)
        
        # 기본 예상 고객 수
        base_customers = int(daily_population * actual_conversion_rate)
        
        # 타겟 고객만 고려한 예상 고객 수
        expected_customers = int(base_customers * target_factor)
        
        # 경쟁 정도에 따른 조정
        competition_count = self._count_competition(com_data, business_type)
        ideal_competition = {
            '카페': 40, '음식점': 50, '편의점': 20, '학원': 15,
            '미용실': 25, '약국': 10, '헬스장': 8, '주점': 30
        }
        ideal = ideal_competition.get(business_type, 30)
        
        if competition_count > ideal * 2:
            # 매우 심한 경쟁
            expected_customers = int(expected_customers * 0.6)
        elif competition_count > ideal:
            # 경쟁 심함
            expected_customers = int(expected_customers * 0.8)
        elif competition_count < ideal * 0.5:
            # 경쟁 매우 적음
            expected_customers = int(expected_customers * 1.3)
        elif competition_count < ideal:
            # 경쟁 적음
            expected_customers = int(expected_customers * 1.1)
        
        # 지역 특성에 따른 조정
        area_name = location.area_name
        
        # 특수 지역 보정
        if '공항' in area_name:
            expected_customers = int(expected_customers * 1.5)  # 공항은 유동인구 많음
        elif '관광특구' in area_name:
            expected_customers = int(expected_customers * 1.3)  # 관광지 보정
        elif any(area in area_name for area in ['강남', '명동', '홍대']):
            expected_customers = int(expected_customers * 1.2)  # 주요 상권
        
        # Flow 효율성 반영
        if location.flow_data and location.flow_data.get('efficiency', 0) > 0:
            flow_efficiency = location.flow_data['efficiency']
            expected_customers = int(expected_customers * (1 + flow_efficiency * 0.3))
        
        # 현실성 체크 (범위를 넓힘)
        min_customers = {
            '카페': 30,      # 최소값을 더 낮춤
            '음식점': 40,    
            '편의점': 80,   
            '학원': 10,      
            '미용실': 20,    
            '약국': 30,      
            '헬스장': 20,    
            '주점': 30       
        }
        
        max_customers = {
            '카페': 1500,     # 상한선 대폭 상향
            '음식점': 2000,  
            '편의점': 3000,  
            '학원': 500,     
            '미용실': 300,   
            '약국': 800,     
            '헬스장': 500,   
            '주점': 1000      
        }
        
        # 디버깅을 위한 로그
        original_expected = expected_customers
        expected_customers = max(
            min_customers.get(business_type, 50),
            min(expected_customers, max_customers.get(business_type, 500))
        )
        
        # 디버깅 출력 (개발 중에만 사용)
        if expected_customers == min_customers.get(business_type, 50):
            print(f"[DEBUG] {area_name}: 최소값 적용 (계산값: {original_expected} → {expected_customers})")
            print(f"  - 유동인구: {int(daily_population)}")
            print(f"  - 전환율: {actual_conversion_rate:.3%}")
            print(f"  - 경쟁수: {competition_count}")
        
        # 계산 과정 저장 (나중에 보고서에 활용 가능)
        calculation_details = {
            'daily_population': int(daily_population),
            'conversion_rate': actual_conversion_rate,
            'base_customers': base_customers,
            'target_factor': target_factor,
            'competition_count': competition_count,
            'original_expected': original_expected,
            'final_expected': expected_customers
        }
        
        # 예상 매출 계산 (개선된 버전)
        price_info = self.estimate_realistic_price_per_customer(
            location, business_type, budget_min, budget_max
        )
        avg_price = price_info['final']
        
        # 일일 매출
        expected_daily_revenue = expected_customers * avg_price
        
        # 월 매출 (영업일수 고려)
        monthly_days = {
            '카페': 30, '음식점': 28, '편의점': 30, '학원': 26,
            '미용실': 28, '약국': 29, '헬스장': 30, '주점': 29
        }
        operating_days = monthly_days.get(business_type, 28)
        expected_monthly_revenue = int(expected_daily_revenue * operating_days)
        
        # 가격 매칭에 따른 조정
        if price_info['match_status'] == 'below_target':
            # 저렴한 지역에서 프리미엄 전략 → 고객 수 감소 가능
            expected_monthly_revenue = int(expected_monthly_revenue * 0.9)
        elif price_info['match_status'] == 'above_target':
            # 비싼 지역에서 가성비 전략 → 고객 수 증가 가능
            expected_monthly_revenue = int(expected_monthly_revenue * 1.1)
        
        # 경쟁 분석
        competitor_analysis = self._analyze_competition(com_data, business_type)
        
        # 강점/약점 분석
        strengths, weaknesses = self._identify_strengths_weaknesses(location, constraints)
        
        # 최적 시간대 분석
        best_times = self._analyze_best_times(pop_data, com_data, business_type)
        
        # 창업 팁 생성
        tips = self._generate_startup_tips(location, constraints)
        
        # 리스크 요인
        risks = self._identify_risks(location, constraints)
        
        # 추천 레벨 결정
        recommendation_level = self._determine_recommendation_level(location)
        
        return StartupInsight(
            area_name=area_name,
            recommendation_level=recommendation_level,
            key_strengths=strengths,
            key_weaknesses=weaknesses,
            target_match_score=location.target_match_score,
            expected_daily_customers=expected_customers,
            expected_monthly_revenue=expected_monthly_revenue,
            competitor_analysis=competitor_analysis,
            best_time_slots=best_times,
            startup_tips=tips,
            risk_factors=risks,
            total_score=location.profitability + location.stability + location.accessibility
        )
    
    def _count_competition(self, com_data: Dict, business_type: str) -> int:
        """경쟁 매장 수 계산"""
        keywords = self.business_keywords.get(business_type, [])
        count = 0
        
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                if any(kw in category for kw in keywords):
                    count += biz.get('merchant_count', 0)
        
        return count
    
    def _analyze_competition(self, com_data: Dict, business_type: str) -> Dict:
        """경쟁 상황 분석"""
        keywords = self.business_keywords.get(business_type, [])
        
        competitor_count = 0
        competitor_categories = []
        
        for biz in com_data.get('business_categories', []):
            category = f"{biz['large_category']} {biz['mid_category']}"
            for keyword in keywords:
                if keyword in category:
                    competitor_count += biz['merchant_count']
                    competitor_categories.append({
                        'category': category,
                        'count': biz['merchant_count'],
                        'avg_payment': (biz['payment_amount_min'] + biz['payment_amount_max']) / 2
                    })
        
        return {
            'total_competitors': competitor_count,
            'categories': competitor_categories[:3],  # 상위 3개
            'competition_level': self._get_competition_level(competitor_count, business_type)
        }
    
    def _get_competition_level(self, count: int, business_type: str) -> str:
        """경쟁 수준 판단"""
        thresholds = {
            '카페': (20, 40, 60),
            '음식점': (30, 50, 70),
            '편의점': (10, 20, 30),
            '학원': (10, 20, 30),
            '미용실': (15, 25, 35),
            '약국': (5, 10, 15),
            '헬스장': (5, 10, 15),
            '주점': (20, 30, 40)
        }
        
        low, medium, high = thresholds.get(business_type, (20, 40, 60))
        
        if count < low:
            return "낮음 (블루오션)"
        elif count < medium:
            return "적정 (경쟁 균형)"
        elif count < high:
            return "높음 (경쟁 치열)"
        else:
            return "매우 높음 (레드오션)"
    
    def _identify_strengths_weaknesses(self, location, constraints) -> tuple:
        """강점과 약점 식별"""
        strengths = []
        weaknesses = []
        
        # 수익성 분석
        if location.profitability >= 80:
            strengths.append("🌟 매우 높은 유동인구와 결제 활성도")
        elif location.profitability >= 60:
            strengths.append("✨ 양호한 유동인구와 상권 활력")
        elif location.profitability < 40:
            weaknesses.append("⚠️ 낮은 유동인구 또는 결제 활동")
        
        # 안정성 분석
        if location.stability >= 80:
            strengths.append("💎 최적의 경쟁 환경과 가격대")
        elif location.stability >= 60:
            strengths.append("💰 지역 평균 결제금액이 목표 객단가와 일치")
        elif location.stability < 40:
            weaknesses.append("⚠️ 과도한 경쟁 또는 객단가 불일치")
        
        # 접근성 분석
        if location.accessibility >= 70:
            strengths.append("🚶 높은 외부 유입 인구 (관광객/직장인)")
        elif location.accessibility < 30:
            weaknesses.append("⚠️ 주로 거주민 위주 지역")
        
        # Flow 효율성
        if location.flow_data and location.flow_data.get('efficiency', 0) > 0.7:
            strengths.append("🌊 우수한 고객 전환 효율")
        elif location.flow_data and location.flow_data.get('efficiency', 0) < 0.3:
            weaknesses.append("⚠️ 낮은 고객 전환율")
        
        # 타겟 매칭
        if location.target_match_score >= 70:
            strengths.append(f"🎯 타겟 고객 비율 우수 ({location.target_match_score:.0f}%)")
        elif location.target_match_score < 50:
            weaknesses.append(f"⚠️ 타겟 고객 비율 부족 ({location.target_match_score:.0f}%)")
        
        return strengths, weaknesses
    
    def _analyze_best_times(self, pop_data: Dict, com_data: Dict, business_type: str) -> List[str]:
        """최적 영업 시간대 분석"""
        # 업종별 주요 시간대
        time_preferences = {
            '카페': ['morning', 'afternoon'],
            '음식점': ['lunch', 'evening'],
            '편의점': ['evening', 'night'],
            '학원': ['afternoon', 'evening'],
            '미용실': ['afternoon', 'evening'],
            '약국': ['morning', 'afternoon'],
            '헬스장': ['morning', 'evening'],
            '주점': ['evening', 'night']
        }
        
        preferred = time_preferences.get(business_type, ['lunch', 'evening'])
        
        # 실제 데이터 기반 조정 (혼잡도 고려)
        congestion = pop_data.get('congestion_level', '')
        if '붐빔' in congestion:
            return [self.time_slots[t] for t in preferred]
        else:
            return [self.time_slots[t] for t in preferred[:1]]  # 주요 시간대만
    
    def _generate_startup_tips(self, location, constraints) -> List[str]:
        """맞춤형 창업 팁 생성"""
        tips = []
        
        # constraints 타입 확인
        if hasattr(constraints, 'business_type'):
            business_type = constraints.business_type
            target_customers = constraints.target_customers
        else:
            business_type = constraints['business_type']
            target_customers = constraints['target_customers']
        
        # 업종별 기본 팁
        if business_type == '카페':
            if location.target_match_score > 70:
                tips.append("💡 테이크아웃 중심 운영으로 회전율 극대화")
            if '직장인' in target_customers:
                tips.append("💡 모닝커피 할인 이벤트로 단골 확보")
        
        elif business_type == '음식점':
            if location.accessibility > 70:
                tips.append("💡 관광객 대상 시그니처 메뉴 개발")
            tips.append("💡 배달 앱 초기 프로모션으로 인지도 확보")
        
        # 경쟁 상황별 팁
        comp_level = location.competition_score
        if comp_level < 60:
            tips.append("💡 과도한 경쟁 지역 - 차별화된 컨셉 필수")
        elif comp_level > 80:
            tips.append("💡 블루오션 지역 - 초기 마케팅으로 선점 효과")
        
        # 유동인구 특성별 팁
        if location.raw_data['population']['non_resident_ratio'] > 70:
            tips.append("💡 SNS 마케팅으로 외부 방문객 유치")
        else:
            tips.append("💡 지역 커뮤니티 마케팅으로 단골 확보")
        
        return tips[:3]  # 최대 3개
    
    def _identify_risks(self, location, constraints) -> List[str]:
        """리스크 요인 식별"""
        risks = []
        
        # 경쟁 리스크
        if location.competition_score < 50:
            risks.append("🚨 높은 경쟁으로 인한 가격 경쟁 우려")
        
        # 타겟 미스매치 리스크
        if location.target_match_score < 60:
            risks.append("🚨 타겟 고객 부족으로 매출 한계 가능")
        
        # 유동인구 변동 리스크
        if location.raw_data['population']['forecast_available']:
            risks.append("⚡ 계절/이벤트에 따른 유동인구 변동 주의")
        
        # 임대료 리스크 (강남, 명동 등 주요 지역)
        if any(area in location.area_name for area in ['강남', '명동', '홍대', '신촌']):
            risks.append("💸 높은 임대료 부담 예상")
        
        return risks
    
    def _determine_recommendation_level(self, location) -> str:
        """추천 수준 결정"""
        total_score = location.profitability + location.stability + location.accessibility
        
        if total_score >= 240:
            return "🏆 강력추천"
        elif total_score >= 200:
            return "✅ 추천"
        elif total_score >= 160:
            return "🤔 보통"
        else:
            return "⚠️ 신중검토"
    
    def _format_recommendations(self, insights: List[StartupInsight]) -> List[Dict]:
        """상위 추천 지역 포맷팅"""
        recommendations = []
        
        for idx, insight in enumerate(insights, 1):
            rec = {
                'rank': idx,
                'area': insight.area_name,
                'level': insight.recommendation_level,
                'one_line_summary': self._create_one_line_summary(insight),
                'expected_monthly_revenue': f"{insight.expected_monthly_revenue:,}원",
                'expected_daily_customers': f"{insight.expected_daily_customers:,}명",
                'competition': insight.competitor_analysis['competition_level'],
                'best_features': insight.key_strengths[:2],
                'quick_tips': insight.startup_tips[:2]
            }
            recommendations.append(rec)
        
        return recommendations
    
    def _create_one_line_summary(self, insight: StartupInsight) -> str:
        """한 줄 요약 생성"""
        if insight.total_score >= 240:
            return f"✨ {insight.area_name}은(는) 모든 조건이 우수한 최적의 창업 입지입니다!"
        elif insight.total_score >= 200:
            return f"👍 {insight.area_name}은(는) 안정적인 수익이 기대되는 좋은 입지입니다."
        elif insight.total_score >= 160:
            return f"🤝 {insight.area_name}은(는) 적절한 전략으로 성공 가능한 입지입니다."
        else:
            return f"💭 {insight.area_name}은(는) 신중한 검토가 필요한 입지입니다."
    
    def _format_detailed_analysis(self, insights: List[StartupInsight]) -> List[Dict]:
        """상세 분석 포맷팅"""
        detailed = []
        
        for insight in insights[:5]:  # 상위 5개만
            analysis = {
                'area': insight.area_name,
                'scores': {
                    'recommendation': insight.recommendation_level,
                    'total_score': f"{insight.total_score:.1f}/300"
                },
                'business_outlook': {
                    'expected_customers_per_day': f"{insight.expected_daily_customers:,}명",
                    'expected_revenue_per_month': f"{insight.expected_monthly_revenue:,}원",
                    'break_even_estimate': self._estimate_break_even(insight),
                    'target_match': f"{insight.target_match_score:.0f}%"
                },
                'competitive_landscape': {
                    'level': insight.competitor_analysis['competition_level'],
                    'total_competitors': insight.competitor_analysis['total_competitors'],
                    'main_competitors': [
                        f"{cat['category']} ({cat['count']}개)" 
                        for cat in insight.competitor_analysis['categories'][:2]
                    ]
                },
                'success_factors': {
                    'strengths': insight.key_strengths,
                    'weaknesses': insight.key_weaknesses,
                    'opportunities': insight.startup_tips,
                    'threats': insight.risk_factors
                },
                'recommended_strategy': self._generate_strategy(insight)
            }
            detailed.append(analysis)
        
        return detailed
    
    def _estimate_break_even(self, insight: StartupInsight) -> str:
        """손익분기점 예상"""
        monthly_revenue = insight.expected_monthly_revenue
        
        # 업종별 평균 영업이익률 (추정치)
        profit_margins = {
            '카페': 0.15,
            '음식점': 0.20,
            '편의점': 0.25,
            '학원': 0.35,
            '미용실': 0.30,
            '약국': 0.25,
            '헬스장': 0.40,
            '주점': 0.30
        }
        
        # 초기 투자비용 추정 (단순화)
        if monthly_revenue > 100_000_000:
            investment = 200_000_000
        elif monthly_revenue > 50_000_000:
            investment = 150_000_000
        else:
            investment = 100_000_000
        
        margin = profit_margins.get('카페', 0.20)  # 기본값
        monthly_profit = monthly_revenue * margin
        
        if monthly_profit > 0:
            months = int(investment / monthly_profit)
            return f"약 {months}개월"
        else:
            return "수익성 재검토 필요"
    
    def _generate_strategy(self, insight: StartupInsight) -> str:
        """맞춤 전략 생성"""
        if insight.recommendation_level == "🏆 강력추천":
            return "공격적 마케팅으로 빠른 시장 진입 추천. 프리미엄 포지셔닝 가능."
        elif insight.recommendation_level == "✅ 추천":
            return "안정적 운영 전략 추천. 차별화된 서비스로 경쟁력 확보."
        elif insight.recommendation_level == "🤔 보통":
            return "틈새시장 공략 필요. 특화 메뉴/서비스로 차별화."
        else:
            return "보수적 접근 필요. 초기 투자 최소화하고 시장 반응 확인."
    
    def _create_summary_table(self, insights: List[StartupInsight]) -> List[Dict]:
        """요약 테이블 생성"""
        summary = []
        
        for insight in insights[:10]:
            row = {
                'area': insight.area_name,
                'grade': self._get_grade(insight.total_score),
                'monthly_revenue': f"{insight.expected_monthly_revenue/1000000:.1f}M",
                'daily_customers': insight.expected_daily_customers,
                'competition': self._get_competition_emoji(
                    insight.competitor_analysis['competition_level']
                ),
                'recommendation': insight.recommendation_level
            }
            summary.append(row)
        
        return summary
    
    def _get_grade(self, score: float) -> str:
        """점수를 등급으로 변환"""
        if score >= 240:
            return "A+"
        elif score >= 220:
            return "A"
        elif score >= 200:
            return "B+"
        elif score >= 180:
            return "B"
        elif score >= 160:
            return "C+"
        else:
            return "C"
    
    def _get_competition_emoji(self, level: str) -> str:
        """경쟁 수준 이모지"""
        if "낮음" in level:
            return "🟢"
        elif "적정" in level:
            return "🟡"
        elif "매우 높음" in level:
            return "🔴"
        elif "높음" in level:
            return "🟠"
        return "⚪"
    
    def _generate_action_items(self, top_insight: StartupInsight, constraints) -> List[str]:
        """실행 계획 생성"""
        if not top_insight:
            return ["지역 선정을 위한 추가 분석 필요"]
        
        # constraints에서 target_customers 가져오기
        if hasattr(constraints, 'target_customers'):
            target_customers = constraints.target_customers
        else:
            target_customers = constraints.get('target_customers', ['직장인'])
        
        actions = [
            f"1️⃣ {top_insight.area_name} 현장 방문 및 상권 조사 (평일/주말 각 2회)",
            f"2️⃣ 예상 임대료 확인 및 3-5개 후보 매물 탐색",
            f"3️⃣ 경쟁업체 {top_insight.competitor_analysis['total_competitors']}개 벤치마킹",
            f"4️⃣ 목표 고객층({', '.join(target_customers)}) 인터뷰 실시",
            f"5️⃣ 초기 투자비용 {self._estimate_initial_cost(top_insight)}원 준비",
            f"6️⃣ {top_insight.best_time_slots[0]} 시간대 중심 운영 계획 수립"
        ]
        
        return actions
    
    def _estimate_initial_cost(self, insight: StartupInsight) -> str:
        """초기 비용 추정"""
        base_cost = 100_000_000  # 1억 기준
        
        # 지역별 가중치
        if any(area in insight.area_name for area in ['강남', '신사', '청담']):
            base_cost *= 2.0
        elif any(area in insight.area_name for area in ['홍대', '신촌', '명동']):
            base_cost *= 1.5
        
        return f"{int(base_cost/10000000)},000만"


def create_user_friendly_output(results: Dict, constraints) -> str:
    """사용자 친화적 출력 생성"""
    generator = ReportGenerator()
    
    # constraints가 이미 객체이므로 바로 전달
    report = generator.generate_comprehensive_report(results, constraints)
    
    output = []
    output.append("\n" + "="*80)
    output.append("🏪 창업 입지 분석 보고서")
    output.append("="*80)
    
    # 기본 정보
    output.append(f"\n📅 분석일시: {report['generated_at']}")
    output.append(f"🍽️ 업종: {report['business_type']}")
    output.append(f"💰 목표 객단가: {report['budget_range']}")
    output.append(f"👥 타겟: {', '.join(report['target_customers'])}")
    
    # TOP 3 추천
    output.append(f"\n\n🏆 TOP 3 추천 지역")
    output.append("-"*60)
    
    for rec in report['top_recommendations']:
        output.append(f"\n{rec['rank']}위. {rec['area']} {rec['level']}")
        output.append(f"   {rec['one_line_summary']}")
        output.append(f"   💰 예상 월매출: {rec['expected_monthly_revenue']}")
        output.append(f"   👥 예상 일고객: {rec['expected_daily_customers']}")
        output.append(f"   🏢 경쟁상황: {rec['competition']}")
        output.append(f"   ✨ 주요강점:")
        for feature in rec['best_features']:
            output.append(f"      {feature}")
        # output.append(f"   💡 Quick Tips:")
        # for tip in rec['quick_tips']:
        #     output.append(f"      {tip}")
    
    # 요약 테이블
    output.append(f"\n\n📊 전체 순위표")
    output.append("-"*80)
    output.append(f"{'순위':<4} {'지역':<20} {'등급':<6} {'월매출':<10} {'일고객':<8} {'경쟁':<6} {'추천도':<15}")
    output.append("-"*80)
    
    for i, row in enumerate(report['summary_table'], 1):
        output.append(
            f"{i:<4} {row['area']:<20} {row['grade']:<6} "
            f"{row['monthly_revenue']:<10} {row['daily_customers']:<8} "
            f"{row['competition']:<6} {row['recommendation']:<15}"
        )
    
    # 1위 지역 상세 분석
    if report['detailed_analysis']:
        top = report['detailed_analysis'][0]
        output.append(f"\n\n🔍 최우수 지역 상세 분석: {top['area']}")
        output.append("="*60)
        
        output.append(f"\n📈 사업 전망")
        output.append(f"   • 예상 일 고객수: {top['business_outlook']['expected_customers_per_day']}")
        output.append(f"   • 예상 월 매출액: {top['business_outlook']['expected_revenue_per_month']}")
        output.append(f"   • 손익분기 예상: {top['business_outlook']['break_even_estimate']}")
        output.append(f"   • 타겟 매칭률: {top['business_outlook']['target_match']}")
        
        output.append(f"\n🏢 경쟁 환경")
        output.append(f"   • 경쟁 수준: {top['competitive_landscape']['level']}")
        # output.append(f"   • 경쟁 매장 수: {top['competitive_landscape']['total_competitors']}개")
        # 중복 제거 - set을 사용하여 unique한 경쟁업체만 표시
        unique_competitors = []
        seen = set()
        for comp in top['competitive_landscape']['main_competitors']:
            if comp not in seen:
                seen.add(comp)
                unique_competitors.append(comp)
        for comp in unique_competitors:
            output.append(f"   • {comp}")
        
        output.append(f"\n🎯 추천 전략")
        output.append(f"   {top['recommended_strategy']}")
    
    # # 실행 계획
    # output.append(f"\n\n📋 다음 단계 Action Items")
    # output.append("-"*60)
    # for action in report['action_items']:
    #     output.append(action)
    
    # output.append(f"\n\n💬 추가 조언")
    # output.append("-"*60)
    # output.append("• 현장 방문은 평일 점심, 주말 저녁 등 다양한 시간대에 실시하세요")
    # output.append("• 주변 상인들과의 대화를 통해 실제 매출 규모를 파악하세요")
    # output.append("• 임대료는 예상 매출의 10-15%를 넘지 않도록 협상하세요")
    # output.append("• 초기 3-6개월 운영자금을 별도로 준비하세요")
    
    return '\n'.join(output)