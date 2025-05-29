# simple_startup_recommender.py
### 이게 파이널 버전입니다. ###

"""
간단한 창업 위치 추천 시스템 - 개선된 버전
- 현실적인 점수 체계
- 업종별 맞춤 가중치
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
from dataclasses import dataclass
from enum import Enum

# 기존 API 클라이언트 import
from seoul_api_client import SeoulDataAPIClient, Config


class BusinessType(Enum):
    """업종 분류"""
    RESTAURANT = "음식점"
    CAFE = "카페/베이커리"
    RETAIL = "소매점(편의점/마트)"
    SERVICE = "서비스업(세탁소/수선)"
    EDUCATION = "교육/학원"
    BEAUTY = "미용/뷰티"
    MEDICAL = "의료/약국"
    BAR = "주점/술집"
    FITNESS = "운동/헬스"
    OTHER = "기타"


@dataclass
class StartupProfile:
    """창업 프로필"""
    business_type: BusinessType
    target_customers: List[str]  # ['직장인', '학생', '주민', '관광객']
    budget_level: str  # 'low', 'medium', 'high'
    operating_time: str  # 'morning', 'day', 'evening', 'night'


class SimpleRecommender:
    """간단한 창업 위치 추천 시스템"""
    
    def __init__(self):
        self.client = SeoulDataAPIClient()
        
        # 업종별 평가 가중치 (총합 100)
        self.scoring_weights = {
            BusinessType.RESTAURANT: {
                'population': 25,      # 유동인구 중요
                'commercial': 30,      # 상권 활성도 매우 중요
                'target_match': 20,    # 타겟 매칭 중요
                'competition': 15,     # 경쟁 고려
                'budget': 10          # 예산은 부차적
            },
            BusinessType.CAFE: {
                'population': 20,
                'commercial': 25,
                'target_match': 30,    # 타겟 매칭 가장 중요
                'competition': 15,
                'budget': 10
            },
            BusinessType.BAR: {
                'population': 20,
                'commercial': 35,      # 상권 활성도 가장 중요
                'target_match': 25,
                'competition': 10,
                'budget': 10
            },
            BusinessType.EDUCATION: {
                'population': 30,      # 거주 인구 중요
                'commercial': 10,      # 상권은 덜 중요
                'target_match': 35,    # 타겟(학생/학부모) 가장 중요
                'competition': 20,
                'budget': 5
            },
            BusinessType.FITNESS: {
                'population': 35,      # 인구 밀도 가장 중요
                'commercial': 15,
                'target_match': 25,
                'competition': 20,
                'budget': 5
            },
            'default': {
                'population': 25,
                'commercial': 25,
                'target_match': 20,
                'competition': 20,
                'budget': 10
            }
        }
    
    def get_user_input(self) -> StartupProfile:
        """사용자 입력 받기"""
        print("\n" + "="*60)
        print("🏪 서울시 창업 위치 추천 시스템")
        print("="*60)
        
        # 1. 업종 선택
        print("\n📌 창업하실 업종을 선택해주세요:")
        for i, btype in enumerate(BusinessType):
            print(f"  {i+1}. {btype.value}")
        
        while True:
            try:
                choice = int(input("\n업종 번호 입력: "))
                if 1 <= choice <= len(BusinessType):
                    business_type = list(BusinessType)[choice-1]
                    break
                else:
                    print("올바른 번호를 입력해주세요.")
            except:
                print("숫자를 입력해주세요.")
        
        # 2. 주요 고객층
        print("\n📌 주요 타겟 고객을 선택해주세요 (복수 선택 가능, 쉼표로 구분):")
        print("  1. 직장인")
        print("  2. 학생 (대학생)")
        print("  3. 주민 (거주민)")
        print("  4. 관광객")
        
        customer_map = {
            '1': '직장인',
            '2': '학생',
            '3': '주민',
            '4': '관광객'
        }
        
        customer_input = input("선택 (예: 1,2): ").split(',')
        target_customers = [customer_map.get(c.strip(), '직장인') for c in customer_input if c.strip() in customer_map]
        
        if not target_customers:
            target_customers = ['직장인']
        
        # 3. 예산 수준
        print("\n📌 예산 수준을 선택해주세요:")
        print("  1. 저예산 (임대료 최소화)")
        print("  2. 중간 (균형)")
        print("  3. 고예산 (프리미엄 입지)")
        
        budget_map = {'1': 'low', '2': 'medium', '3': 'high'}
        budget_input = input("선택: ").strip()
        budget_level = budget_map.get(budget_input, 'medium')
        
        # 4. 주 운영 시간대
        print("\n📌 주 운영 시간대를 선택해주세요:")
        print("  1. 아침 (06-11시)")
        print("  2. 낮 (11-17시)")
        print("  3. 저녁 (17-22시)")
        print("  4. 심야 (22시 이후)")
        
        time_map = {'1': 'morning', '2': 'day', '3': 'evening', '4': 'night'}
        time_input = input("선택: ").strip()
        operating_time = time_map.get(time_input, 'day')
        
        return StartupProfile(
            business_type=business_type,
            target_customers=target_customers,
            budget_level=budget_level,
            operating_time=operating_time
        )
    
    def analyze_location(self, area_name: str, profile: StartupProfile) -> Optional[Dict]:
        """단일 지역 분석"""
        try:
            # API 데이터 수집
            pop_data = self.client.get_population_data(area_name)
            com_data = self.client.get_commercial_data(area_name)
            
            if not pop_data or not com_data:
                return None
            
            # 가중치 가져오기
            weights = self.scoring_weights.get(profile.business_type, self.scoring_weights['default'])
            
            # 각 항목별 점수 계산 (0~1 정규화)
            scores_raw = {
                'population': self._score_population(pop_data, com_data, profile),
                'commercial': self._score_commercial(com_data, profile),
                'target_match': self._score_target_match(pop_data, com_data, profile),
                'competition': self._score_competition(com_data, profile),
                'budget': self._score_budget(com_data, profile)
            }
            
            # 가중치 적용
            weighted_scores = {}
            total_score = 0
            
            for key, raw_score in scores_raw.items():
                weighted_score = raw_score * weights[key]
                weighted_scores[key] = weighted_score
                total_score += weighted_score
            
            # 분석 결과
            analysis = {
                'area_name': area_name,
                'total_score': total_score,
                'scores': weighted_scores,
                'raw_scores': scores_raw,
                'population_info': {
                    'total': (pop_data['population_min'] + pop_data['population_max']) // 2,
                    'congestion': pop_data['congestion_level'],
                    'main_age_group': self._get_main_age_group(pop_data['age_distribution'])
                },
                'commercial_info': {
                    'activity_level': com_data['area_commercial_level'],
                    'avg_payment': com_data['area_payment_amount']['max'],
                    'payment_count': com_data['area_payment_count']
                },
                'insights': self._generate_insights(scores_raw, pop_data, com_data, profile)
            }
            
            return analysis
            
        except Exception as e:
            print(f"\n⚠️ {area_name} 분석 중 오류 발생: {str(e)}")
            return None
    
    def _score_population(self, pop_data: Dict, com_data: Dict, profile: StartupProfile) -> float:
        """유동인구 점수 (0~1)"""
        population = (pop_data['population_min'] + pop_data['population_max']) / 2
        
        # 업종별 적정 인구수
        ideal_population = {
            BusinessType.RESTAURANT: 30000,
            BusinessType.CAFE: 25000,
            BusinessType.BAR: 30000,
            BusinessType.RETAIL: 20000,
            BusinessType.EDUCATION: 15000,
            BusinessType.FITNESS: 25000,
            BusinessType.BEAUTY: 20000,
            BusinessType.MEDICAL: 20000,
            BusinessType.SERVICE: 15000,
            BusinessType.OTHER: 20000
        }
        
        ideal = ideal_population.get(profile.business_type, 20000)
        
        # 이상적인 인구수 대비 점수 계산
        if population >= ideal * 1.5:
            return 1.0  # 충분한 인구
        elif population >= ideal:
            return 0.8 + (population - ideal) / (ideal * 0.5) * 0.2
        elif population >= ideal * 0.5:
            return 0.4 + (population - ideal * 0.5) / (ideal * 0.5) * 0.4
        else:
            return population / (ideal * 0.5) * 0.4
    
    def _score_commercial(self, com_data: Dict, profile: StartupProfile) -> float:
        """상권 활성도 점수 (0~1)"""
        level_scores = {
            '활발': 1.0,
            '정상': 0.8,
            '활성화된': 0.8,
            '보통': 0.6,
            '저조': 0.3,
            '한산한': 0.2,
            '매우 저조': 0.1
        }
        
        level = com_data.get('area_commercial_level', '보통')
        base_score = level_scores.get(level, 0.5)
        
        # 업종별 조정
        if profile.business_type in [BusinessType.RESTAURANT, BusinessType.CAFE, BusinessType.BAR]:
            # 음식/음료 업종은 활발한 상권 선호
            return base_score
        elif profile.business_type in [BusinessType.EDUCATION, BusinessType.FITNESS, BusinessType.SERVICE]:
            # 생활 밀착형 업종은 적당한 상권 선호
            if base_score >= 0.8:
                return 0.7  # 너무 활발하면 오히려 감점
            elif base_score >= 0.5:
                return 0.9  # 적당한 수준이 최적
            else:
                return base_score
        else:
            return base_score
    
    def _score_target_match(self, pop_data: Dict, com_data: Dict, profile: StartupProfile) -> float:
        """타겟 고객 매칭 점수 (0~1)"""
        score = 0.0
        weights = {
            '직장인': 0,
            '학생': 0,
            '주민': 0,
            '관광객': 0
        }
        
        # 각 타겟별 가중치 계산
        for customer in profile.target_customers:
            weights[customer] = 1.0 / len(profile.target_customers)
        
        # 직장인 점수
        if weights['직장인'] > 0:
            # 20-50대 비율과 비거주민 비율 고려
            worker_score = (
                pop_data['age_distribution'].get('20s', 0) * 0.3 +
                pop_data['age_distribution'].get('30s', 0) * 0.3 +
                pop_data['age_distribution'].get('40s', 0) * 0.3 +
                pop_data['age_distribution'].get('50s', 0) * 0.1
            ) / 100
            
            # 평일 낮 시간 활성화 정도 (비거주민 비율로 추정)
            worker_score = worker_score * 0.7 + (pop_data.get('non_resident_ratio', 0) / 100) * 0.3
            score += worker_score * weights['직장인']
        
        # 학생 점수
        if weights['학생'] > 0:
            student_score = (
                pop_data['age_distribution'].get('10s', 0) * 0.2 +
                pop_data['age_distribution'].get('20s', 0) * 0.8
            ) / 100
            score += student_score * weights['학생']
        
        # 주민 점수
        if weights['주민'] > 0:
            resident_score = pop_data.get('resident_ratio', 0) / 100
            score += resident_score * weights['주민']
        
        # 관광객 점수
        if weights['관광객'] > 0:
            # 비거주민 비율과 상권 활성도로 추정
            tourist_score = pop_data.get('non_resident_ratio', 0) / 100
            if '관광특구' in com_data.get('area_name', ''):
                tourist_score = min(tourist_score + 0.3, 1.0)
            score += tourist_score * weights['관광객']
        
        return score
    
    def _score_competition(self, com_data: Dict, profile: StartupProfile) -> float:
        """경쟁 수준 점수 (0~1) - 적절한 경쟁이 있을 때 높은 점수"""
        # 결제 건수로 경쟁 강도 추정
        payment_count = com_data.get('area_payment_count', 0)
        
        # 업종별 적정 경쟁 수준
        ideal_competition = {
            BusinessType.RESTAURANT: 50000,
            BusinessType.CAFE: 30000,
            BusinessType.BAR: 40000,
            BusinessType.RETAIL: 20000,
            BusinessType.EDUCATION: 10000,
            BusinessType.FITNESS: 5000,
            BusinessType.BEAUTY: 15000,
            BusinessType.MEDICAL: 5000,
            BusinessType.SERVICE: 10000,
            BusinessType.OTHER: 20000
        }
        
        ideal = ideal_competition.get(profile.business_type, 20000)
        
        # 적정 경쟁 수준에서 멀어질수록 감점
        if payment_count <= ideal * 0.3:
            # 너무 경쟁이 없음 (시장이 형성되지 않음)
            return 0.3
        elif payment_count <= ideal * 0.7:
            # 경쟁이 적음
            return 0.6
        elif payment_count <= ideal * 1.3:
            # 적정 수준
            return 1.0
        elif payment_count <= ideal * 2.0:
            # 경쟁이 많음
            return 0.7
        else:
            # 과도한 경쟁
            return 0.4
    
    def _score_budget(self, com_data: Dict, profile: StartupProfile) -> float:
        """예산 적합도 점수 (0~1)"""
        avg_payment = com_data.get('area_payment_amount', {}).get('max', 50000)
        
        # 예산별 적정 객단가 범위
        budget_ranges = {
            'low': (10000, 30000),
            'medium': (20000, 60000),
            'high': (40000, 200000)
        }
        
        min_pay, max_pay = budget_ranges.get(profile.budget_level, (20000, 60000))
        
        if min_pay <= avg_payment <= max_pay:
            # 적정 범위 내
            return 1.0
        elif avg_payment < min_pay:
            # 너무 낮은 객단가
            return 0.5 + (avg_payment / min_pay) * 0.5
        else:
            # 너무 높은 객단가
            if profile.budget_level == 'low':
                # 저예산인데 고객단가 지역은 부적합
                return max(0.2, 1.0 - (avg_payment - max_pay) / max_pay)
            else:
                # 고예산이면 어느정도 감당 가능
                return 0.7
    
    def _get_main_age_group(self, age_dist: Dict) -> str:
        """주요 연령대 추출"""
        if not age_dist:
            return "정보없음"
        
        # 실제 값이 있는 항목만 필터링
        valid_ages = {k: v for k, v in age_dist.items() if v > 0}
        
        if not valid_ages:
            return "정보없음"
            
        main_age = max(valid_ages.items(), key=lambda x: x[1])
        age_map = {
            '0-10': '10세 미만',
            '10s': '10대',
            '20s': '20대',
            '30s': '30대',
            '40s': '40대',
            '50s': '50대',
            '60s': '60대',
            '70s': '70대 이상'
        }
        return age_map.get(main_age[0], main_age[0])
    
    def _generate_insights(self, scores: Dict, pop_data: Dict, com_data: Dict, profile: StartupProfile) -> List[str]:
        """인사이트 생성"""
        insights = []
        
        # 종합 평가
        total = sum(scores.values()) / len(scores)
        if total >= 0.8:
            insights.append("🏆 매우 적합한 지역입니다!")
        elif total >= 0.6:
            insights.append("✅ 적합한 지역입니다.")
        elif total >= 0.4:
            insights.append("⚠️ 신중한 검토가 필요한 지역입니다.")
        else:
            insights.append("❌ 추천하지 않는 지역입니다.")
        
        # 강점 분석
        if scores['population'] >= 0.8:
            insights.append("💪 유동인구가 충분합니다.")
        if scores['commercial'] >= 0.8:
            insights.append("💪 상권이 활성화되어 있습니다.")
        if scores['target_match'] >= 0.8:
            insights.append("💪 타겟 고객층이 풍부합니다.")
        
        # 약점 분석
        if scores['population'] < 0.4:
            insights.append("📍 유동인구가 부족합니다. 배달/온라인 병행을 고려하세요.")
        if scores['commercial'] < 0.4:
            insights.append("📍 상권이 침체되어 있습니다. 적극적인 마케팅이 필요합니다.")
        if scores['competition'] < 0.4:
            insights.append("📍 경쟁이 매우 치열합니다. 차별화 전략이 필수입니다.")
        
        # 업종별 특화 조언
        if profile.business_type == BusinessType.RESTAURANT:
            if profile.operating_time == 'evening' and pop_data.get('non_resident_ratio', 0) < 30:
                insights.append("💡 주거 지역이므로 배달 서비스를 강화하세요.")
            if com_data.get('area_commercial_level') == '활발':
                insights.append("💡 회식/모임 수요를 공략하세요.")
                
        elif profile.business_type == BusinessType.CAFE:
            if '학생' in profile.target_customers and scores['target_match'] >= 0.7:
                insights.append("💡 스터디 공간을 마련하면 경쟁력이 있습니다.")
            if pop_data.get('resident_ratio', 0) > 70:
                insights.append("💡 테이크아웃과 디저트 메뉴를 강화하세요.")
                
        elif profile.business_type == BusinessType.FITNESS:
            if pop_data.get('resident_ratio', 0) > 60:
                insights.append("💡 주민 할인과 가족 회원권을 고려하세요.")
        
        return insights
    
    def recommend_locations(self, profile: StartupProfile, top_n: int = 10) -> List[Dict]:
        """전체 지역 분석 및 추천"""
        print("\n🔍 전체 지역 분석 중... (시간이 걸릴 수 있습니다)")
        
        results = []
        areas_to_analyze = Config.AVAILABLE_AREAS
        
        for i, area in enumerate(areas_to_analyze):
            print(f"\r분석 진행률: {i+1}/{len(areas_to_analyze)} ({area})", end='', flush=True)
            
            analysis = self.analyze_location(area, profile)
            if analysis:
                results.append(analysis)
        
        print("\n✅ 분석 완료!")
        
        # 점수순 정렬
        results.sort(key=lambda x: x['total_score'], reverse=True)
        
        return results[:top_n]
    
    def display_results(self, results: List[Dict], profile: StartupProfile):
        """결과 출력"""
        print("\n" + "="*80)
        print(f"🏆 {profile.business_type.value} 창업 추천 지역 TOP 10")
        print("="*80)
        
        # 가중치 정보 출력
        weights = self.scoring_weights.get(profile.business_type, self.scoring_weights['default'])
        print(f"\n📊 평가 기준 (가중치):")
        print(f"  - 유동인구: {weights['population']}%")
        print(f"  - 상권활성도: {weights['commercial']}%")
        print(f"  - 타겟매칭: {weights['target_match']}%")
        print(f"  - 경쟁수준: {weights['competition']}%")
        print(f"  - 예산적합도: {weights['budget']}%")
        
        for i, result in enumerate(results[:10]):
            print(f"\n{'='*80}")
            print(f"\n{i+1}. {result['area_name']} (종합점수: {result['total_score']:.1f}/100)")
            
            # 주요 정보
            print(f"\n📍 기본 정보:")
            print(f"  - 유동인구: {result['population_info']['total']:,}명 ({result['population_info']['congestion']})")
            print(f"  - 주 연령층: {result['population_info']['main_age_group']}")
            print(f"  - 상권: {result['commercial_info']['activity_level']}")
            print(f"  - 평균 결제액: {result['commercial_info']['avg_payment']:,}원")
            
            # 점수 상세
            print(f"\n📊 세부 점수:")
            for key, score in result['scores'].items():
                raw_score = result['raw_scores'][key]
                weight = weights[key]
                print(f"  - {key}: {score:.1f}점 (원점수 {raw_score:.2f} × 가중치 {weight}%)")
            
            # 인사이트
            print(f"\n💡 인사이트:")
            for insight in result['insights']:
                print(f"  {insight}")
    
    def save_results(self, results: List[Dict], profile: StartupProfile, filename: str = None):
        """결과 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"startup_recommendation_{profile.business_type.name}_{timestamp}.json"
        
        data = {
            'profile': {
                'business_type': profile.business_type.value,
                'target_customers': profile.target_customers,
                'budget_level': profile.budget_level,
                'operating_time': profile.operating_time
            },
            'results': results,
            'generated_at': datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {filename}에 저장되었습니다.")


def main():
    """메인 실행 함수"""
    recommender = SimpleRecommender()
    
    # 사용자 입력 받기
    profile = recommender.get_user_input()
    
    # 빠른 분석 vs 전체 분석 선택
    print("\n📌 분석 방식을 선택하세요:")
    print("  1. 빠른 분석 (특정 지역 10개만)")
    print("  2. 전체 분석 (82개 전지역 - 시간 소요)")
    
    analysis_type = input("\n선택: ").strip()
    
    if analysis_type == '1':
        # 빠른 분석 - 다양한 특성의 지역 선택
        test_areas = [
            '강남역', '홍대 관광특구', '건대입구역', '신촌·이대역',
            '성수카페거리', '이태원 관광특구', '명동 관광특구',
            '연남동', '압구정로데오거리', '여의도'
        ]
        print(f"\n🔍 {len(test_areas)}개 주요 지역 분석 중...")
        
        results = []
        for area in test_areas:
            analysis = recommender.analyze_location(area, profile)
            if analysis:
                results.append(analysis)
        
        results.sort(key=lambda x: x['total_score'], reverse=True)
        recommender.display_results(results, profile)
        
    else:
        # 전체 분석
        results = recommender.recommend_locations(profile, top_n=10)
        recommender.display_results(results, profile)
    
    # 저장 옵션
    save_choice = input("\n\n💾 결과를 저장하시겠습니까? (y/n): ").lower()
    if save_choice == 'y':
        recommender.save_results(results[:10], profile)
    
    print("\n✅ 분석이 완료되었습니다!")
    print("📌 참고: 실제 창업 시에는 현장 방문과 추가 조사를 꼭 하시기 바랍니다.")


if __name__ == "__main__":
    main()