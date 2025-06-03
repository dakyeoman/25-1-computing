#!/usr/bin/env python3
"""
optimizer_realistic.py - 실제 평가 가능한 성별 타겟과 상권 특성만 추가
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RealisticStartupConstraints:
    """현실적인 창업 제약조건"""
    # 기본 정보
    business_type: str
    target_customers: List[str]
    budget_min: int  # 목표 객단가 최소
    budget_max: int  # 목표 객단가 최대
    max_competition: int
    min_target_match: float
    
    # === 추가 입력 (실제 평가 가능) ===
    
    # 성별 타겟
    target_gender: str = 'all'            # 'male', 'female', 'all'
    min_gender_ratio: float = 40.0        # 최소 성별 비율 (%)
    
    # 선호 상권 특성
    prefer_tourist_area: bool = False     # 관광지 선호
    prefer_office_area: bool = False      # 오피스 밀집지역 선호
    prefer_residential_area: bool = False # 주거지역 선호
    prefer_university_area: bool = False  # 대학가 선호


@dataclass
class LocationScore:
    """입지 점수"""
    area_name: str
    profitability: float = 0.0
    stability: float = 0.0
    accessibility: float = 0.0
    network_efficiency: float = 0.0
    
    # 세부 점수
    population_score: float = 0
    payment_activity_score: float = 0
    target_match_score: float = 0
    competition_score: float = 0
    budget_fit_score: float = 0
    
    # 추가 점수
    gender_match_score: float = 0         # 성별 타겟 매칭
    area_type_score: float = 0            # 상권 특성 매칭
    
    # Flow 데이터
    flow_data: Dict = field(default_factory=dict)
    raw_data: Dict = field(default_factory=dict)


class RealisticOptimizer:
    """현실적인 최적화 시스템"""
    
    def __init__(self):
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
        
        self.ideal_competition = {
            "카페": 40, "음식점": 50, "주점": 30, "편의점": 20,
            "학원": 15, "미용실": 25, "약국": 10, "헬스장": 8
        }
        
        # 상권 특성 키워드 (지역명으로 판단)
        self.area_type_keywords = {
            'tourist': ['관광특구', '명동', '인사동', '북촌', '이태원', '삼청동', '익선동', 'DDP'],
            'office': ['MICE', '디지털단지', '여의도', '강남', '을지로', '종로', '테헤란로', '광화문'],
            'university': ['대학', '신촌', '이대', '건대', '홍대', '회기', '성신여대', '혜화'],
            'residential': []  # 거주 비율로 판단
        }
    
    def optimize(self, location_data: List[Dict], constraints: RealisticStartupConstraints, 
                flow_analysis: Optional[Dict] = None) -> Dict:
        """최적화 실행"""
        # 1. 제약조건 필터링
        filtered = self._filter_by_constraints(location_data, constraints)
        logger.info(f"제약조건 통과: {len(filtered)}개 지역")
        
        if not filtered:
            return {'filtered_locations': [], 'pareto_optimal': [], 'recommendations': {}}
        
        # 2. 점수 계산
        scored = self._calculate_scores(filtered, constraints, flow_analysis)
        
        # 3. 파레토 최적해
        pareto = self._find_pareto_optimal(scored)
        
        # 4. 추천 생성
        recommendations = self._generate_recommendations(pareto)
        
        return {
            'all_locations': location_data,
            'filtered_locations': filtered,
            'scored_locations': scored,
            'pareto_optimal': pareto,
            'recommendations': recommendations,
            'flow_analysis': flow_analysis
        }
    
    def _filter_by_constraints(self, locations: List[Dict], constraints: RealisticStartupConstraints) -> List[Dict]:
        """제약조건 필터링"""
        filtered = []
        
        for loc in locations:
            # 기본 필터링
            payment = self._calculate_average_payment_per_person(loc['commercial'], constraints.business_type)
            
            logger.debug(f"{loc['area_name']} - 추정 객단가: {payment:,.0f}원")
            
            if payment > 0 and not (constraints.budget_min <= payment <= constraints.budget_max):
                logger.debug(f"  → 객단가 부적합")
                continue
            
            competition = self._count_competition(loc['commercial'], constraints.business_type)
            if competition > constraints.max_competition:
                logger.debug(f"  → 경쟁 과다: {competition}개")
                continue
            
            target_match = self._calculate_target_match(loc['population'], constraints.target_customers)
            if target_match < constraints.min_target_match:
                logger.debug(f"  → 타겟 부족: {target_match:.0f}%")
                continue
            
            # 성별 필터링
            if constraints.target_gender != 'all':
                gender_data = loc['population'].get('gender_distribution', {})
                if constraints.target_gender == 'male':
                    gender_ratio = gender_data.get('male', 50)
                else:
                    gender_ratio = gender_data.get('female', 50)
                
                if gender_ratio < constraints.min_gender_ratio:
                    logger.debug(f"  → 성별 타겟 부족: {gender_ratio:.1f}%")
                    continue
            
            filtered.append(loc)
        
        return filtered
    
    def _calculate_scores(self, locations: List[Dict], constraints: RealisticStartupConstraints, 
                         flow_analysis: Optional[Dict]) -> List[LocationScore]:
        """점수 계산"""
        scored = []
        
        for loc in locations:
            score = LocationScore(area_name=loc['area_name'])
            
            # 기본 점수들
            pop_max = loc['population'].get('population_max', 10000)
            score.population_score = min(100, (pop_max / 30000) * 100)
            
            payment_count = loc['commercial'].get('area_payment_count', 1000)
            score.payment_activity_score = min(100, (payment_count / 10000) * 100)
            
            score.target_match_score = self._calculate_target_match(
                loc['population'], constraints.target_customers
            )
            
            # 경쟁 점수 (역U자형)
            competition = self._count_competition(loc['commercial'], constraints.business_type)
            ideal = self.ideal_competition.get(constraints.business_type, 30)
            if competition <= ideal:
                score.competition_score = 60 + (competition / ideal) * 40
            else:
                score.competition_score = max(30, 100 - (competition - ideal) / ideal * 70)
            
            # 객단가 적합도
            payment = self._calculate_average_payment_per_person(loc['commercial'], constraints.business_type)
            if payment:
                center = (constraints.budget_min + constraints.budget_max) / 2
                if constraints.budget_min <= payment <= constraints.budget_max:
                    deviation = abs(payment - center) / (center * 0.5)
                    score.budget_fit_score = 100 - (deviation * 20)
                else:
                    if payment < constraints.budget_min:
                        deviation = (constraints.budget_min - payment) / constraints.budget_min
                    else:
                        deviation = (payment - constraints.budget_max) / constraints.budget_max
                    score.budget_fit_score = max(0, 50 - (deviation * 50))
            
            # === 추가 점수 계산 ===
            
            # 성별 매칭 점수
            score.gender_match_score = self._calculate_gender_match_score(
                loc['population'], constraints
            )
            
            # 상권 특성 점수
            score.area_type_score = self._calculate_area_type_score(
                loc, constraints
            )
            
            # 목적함수 계산
            score.profitability = (
                score.population_score * 0.35 +
                score.payment_activity_score * 0.35 +
                score.target_match_score * 0.3
            )
            
            score.stability = (
                score.competition_score * 0.6 +
                score.budget_fit_score * 0.4
            )
            
            # 접근성 (상권 특성 반영)
            non_resident = loc['population'].get('non_resident_ratio', 50)
            score.accessibility = (
                non_resident * 0.7 +           # 외부 유입
                score.area_type_score * 0.3    # 상권 특성
            )
            
            # 성별 타겟이 있으면 수익성에 반영
            if constraints.target_gender != 'all':
                score.profitability = score.profitability * 0.9 + score.gender_match_score * 0.1
            
            # Flow 점수 통합
            if flow_analysis and loc['area_name'] in flow_analysis['areas']:
                flow = flow_analysis['areas'][loc['area_name']]
                score.flow_data = flow
                score.network_efficiency = flow['efficiency'] * 100
                
                # 수익성에 flow 효율성 반영
                score.profitability = score.profitability * 0.7 + score.network_efficiency * 0.3
            
            score.raw_data = loc
            scored.append(score)
        
        return scored
    
    def _calculate_gender_match_score(self, pop_data: Dict, constraints: RealisticStartupConstraints) -> float:
        """성별 매칭 점수"""
        if constraints.target_gender == 'all':
            return 80  # 성별 무관하면 기본 점수
        
        gender_dist = pop_data.get('gender_distribution', {})
        
        if constraints.target_gender == 'male':
            ratio = gender_dist.get('male', 50)
        else:
            ratio = gender_dist.get('female', 50)
        
        # 목표 비율보다 높으면 높을수록 좋음
        if ratio >= constraints.min_gender_ratio + 10:
            return 100
        elif ratio >= constraints.min_gender_ratio:
            return 80 + (ratio - constraints.min_gender_ratio) * 2
        else:
            # 목표 미달이지만 필터링에서 통과했으면 최소 점수
            return 50
    
    def _calculate_area_type_score(self, location: Dict, constraints: RealisticStartupConstraints) -> float:
        """상권 특성 점수"""
        area_name = location['area_name']
        pop_data = location['population']
        score = 50  # 기본 점수
        matched = 0
        total_prefs = 0
        
        # 관광지 선호
        if constraints.prefer_tourist_area:
            total_prefs += 1
            if any(keyword in area_name for keyword in self.area_type_keywords['tourist']):
                matched += 1
                score += 25
            elif pop_data.get('non_resident_ratio', 0) > 80:  # 비거주자 매우 높음
                matched += 0.5
                score += 15
        
        # 오피스 선호
        if constraints.prefer_office_area:
            total_prefs += 1
            if any(keyword in area_name for keyword in self.area_type_keywords['office']):
                matched += 1
                score += 25
            elif pop_data.get('non_resident_ratio', 0) > 70 and '20s' in pop_data.get('age_distribution', {}):
                # 비거주자 높고 20-40대 많으면 오피스 지역 가능성
                age_20_40 = (pop_data['age_distribution'].get('20s', 0) + 
                           pop_data['age_distribution'].get('30s', 0) + 
                           pop_data['age_distribution'].get('40s', 0))
                if age_20_40 > 60:
                    matched += 0.7
                    score += 20
        
        # 주거지역 선호
        if constraints.prefer_residential_area:
            total_prefs += 1
            resident_ratio = pop_data.get('resident_ratio', 50)
            if resident_ratio > 70:
                matched += 1
                score += 25
            elif resident_ratio > 60:
                matched += 0.5
                score += 15
        
        # 대학가 선호
        if constraints.prefer_university_area:
            total_prefs += 1
            if any(keyword in area_name for keyword in self.area_type_keywords['university']):
                matched += 1
                score += 25
            elif pop_data['age_distribution'].get('20s', 0) > 35:  # 20대 비율 매우 높음
                matched += 0.7
                score += 20
        
        # 선호가 없으면 기본 점수 유지
        if total_prefs == 0:
            return 70
        
        # 매칭률에 따라 최종 점수 조정
        match_rate = matched / total_prefs if total_prefs > 0 else 0
        final_score = 50 + (match_rate * 50)
        
        return min(100, final_score)
    
    def _find_pareto_optimal(self, locations: List[LocationScore]) -> List[LocationScore]:
        """파레토 최적해 찾기"""
        pareto = []
        
        for i, loc1 in enumerate(locations):
            dominated = False
            
            for j, loc2 in enumerate(locations):
                if i == j:
                    continue
                
                # 4차원 지배 관계
                if (loc2.profitability >= loc1.profitability and
                    loc2.stability >= loc1.stability and
                    loc2.accessibility >= loc1.accessibility and
                    loc2.network_efficiency >= loc1.network_efficiency and
                    (loc2.profitability > loc1.profitability or
                     loc2.stability > loc1.stability or
                     loc2.accessibility > loc1.accessibility or
                     loc2.network_efficiency > loc1.network_efficiency)):
                    dominated = True
                    break
            
            if not dominated:
                pareto.append(loc1)
        
        # 종합 점수로 정렬
        pareto.sort(key=lambda x: (
            x.profitability + x.stability + x.accessibility + x.network_efficiency
        ), reverse=True)
        
        return pareto
    
    def _generate_recommendations(self, pareto: List[LocationScore]) -> Dict:
        """추천 생성"""
        if not pareto:
            return {}
        
        recommendations = {
            'best_overall': max(pareto, key=lambda x: 
                x.profitability + x.stability + x.accessibility + x.network_efficiency),
            'best_profitability': max(pareto, key=lambda x: x.profitability),
            'best_stability': max(pareto, key=lambda x: x.stability),
            'best_accessibility': max(pareto, key=lambda x: x.accessibility),
            'balanced': [loc for loc in pareto if all([
                loc.profitability >= 60, loc.stability >= 60, 
                loc.accessibility >= 60
            ])]
        }
        
        # 성별 매칭 최고
        if any(loc.gender_match_score > 0 for loc in pareto):
            recommendations['best_gender_match'] = max(
                pareto, key=lambda x: x.gender_match_score
            )
        
        # 상권 특성 최고
        if any(loc.area_type_score > 50 for loc in pareto):
            recommendations['best_area_type'] = max(
                pareto, key=lambda x: x.area_type_score
            )
        
        # Flow 기반 추천
        if any(loc.flow_data for loc in pareto):
            recommendations['best_efficiency'] = max(
                [loc for loc in pareto if loc.flow_data],
                key=lambda x: x.flow_data.get('efficiency', 0)
            )
        
        return recommendations
    
    # === 기존 헬퍼 메서드들 ===
    def _calculate_average_payment_per_person(self, com_data: Dict, business_type: str) -> float:
        """1인당 평균 결제금액 계산"""
        keywords = self.business_keywords.get(business_type, [])
        
        # 업종별 카테고리 데이터 우선 확인
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                if any(kw in category for kw in keywords):
                    # 해당 업종의 결제 데이터만 사용
                    payment_min = biz.get('payment_amount_min', 0)
                    payment_max = biz.get('payment_amount_max', 0)
                    total_amount = (payment_min + payment_max) / 2
                    payment_count = biz.get('payment_count', 1)
                    
                    if payment_count > 0 and total_amount > 0:
                        # 월 총액을 월 건수로 나누면 건당 평균
                        avg_per_transaction = total_amount / payment_count
                        
                        # 카페의 경우 1인 1잔, 음식점은 2-3인 기준
                        persons_per_transaction = {
                            '카페': 1.2,      # 대부분 1인, 가끔 2인
                            '편의점': 1.1,    # 대부분 1인
                            '음식점': 2.5,    # 평균 2-3인
                            '주점': 3.0,      # 평균 3인
                            '미용실': 1.0,    # 1인
                            '학원': 1.0,      # 1인
                            '약국': 1.2,      # 1인, 가끔 가족
                            '헬스장': 1.0     # 1인
                        }
                        
                        avg_per_person = avg_per_transaction / persons_per_transaction.get(business_type, 1.5)
                        
                        # 합리적 범위 체크
                        min_price = {'카페': 3000, '편의점': 2000, '음식점': 8000}.get(business_type, 5000)
                        max_price = {'카페': 20000, '편의점': 15000, '음식점': 50000}.get(business_type, 100000)
                        
                        return max(min_price, min(max_price, avg_per_person))
        
        # 카테고리별 데이터가 없으면 전체 데이터 사용
        area_min = com_data.get('area_payment_amount', {}).get('min', 0)
        area_max = com_data.get('area_payment_amount', {}).get('max', 0)
        area_total = (area_min + area_max) / 2
        area_count = com_data.get('area_payment_count', 1)
        
        if area_count > 0 and area_total > 0:
            avg_per_transaction = area_total / area_count
            
            # 업종별 추정 비율 (전체 상권에서 차지하는 비중)
            business_share = {
                '카페': 0.05,      # 전체 매출의 5%
                '편의점': 0.03,    # 전체 매출의 3%
                '음식점': 0.25,    # 전체 매출의 25%
                '주점': 0.10,      # 전체 매출의 10%
                '미용실': 0.02,    # 전체 매출의 2%
                '학원': 0.05,      # 전체 매출의 5%
                '약국': 0.02,      # 전체 매출의 2%
                '헬스장': 0.01     # 전체 매출의 1%
            }
            
            # 해당 업종의 추정 평균 결제액
            estimated_avg = avg_per_transaction * business_share.get(business_type, 0.05) * 10
            
            # 인당 결제액으로 변환
            persons_per_transaction = {
                '카페': 1.2, '편의점': 1.1, '음식점': 2.5, '주점': 3.0,
                '미용실': 1.0, '학원': 1.0, '약국': 1.2, '헬스장': 1.0
            }
            
            avg_per_person = estimated_avg / persons_per_transaction.get(business_type, 1.5)
            
            # 합리적 범위로 제한
            min_price = {'카페': 3000, '편의점': 2000, '음식점': 8000}.get(business_type, 5000)
            max_price = {'카페': 20000, '편의점': 15000, '음식점': 50000}.get(business_type, 100000)
            
            return max(min_price, min(max_price, avg_per_person))
        
        # 기본값
        default_values = {
            '카페': 6000,      # 아메리카노 기준
            '편의점': 4000,    # 평균 구매액
            '음식점': 12000,   # 점심 기준
            '주점': 25000,     # 인당 평균
            '미용실': 30000,   # 커트 기준
            '학원': 150000,    # 월 수강료
            '약국': 8000,      # 평균 구매액
            '헬스장': 50000    # 월 회비
        }
        
        return default_values.get(business_type, 10000)
    
    def _count_competition(self, com_data: Dict, business_type: str) -> int:
        """경쟁 매장 수"""
        keywords = self.business_keywords.get(business_type, [])
        count = 0
        
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                if any(kw in category for kw in keywords):
                    count += biz.get('merchant_count', 0)
        
        if count == 0:
            total_merchants = sum(biz.get('merchant_count', 0) 
                                for biz in com_data.get('business_categories', []))
            ratios = {
                '카페': 0.15, '음식점': 0.25, '편의점': 0.05,
                '학원': 0.05, '미용실': 0.08, '약국': 0.02,
                '헬스장': 0.02, '주점': 0.10
            }
            count = int(total_merchants * ratios.get(business_type, 0.1))
        
        return count
    
    def _calculate_target_match(self, pop_data: Dict, targets: List[str]) -> float:
        """타겟 매칭률"""
        score = 0
        count = 0
        
        age_dist = pop_data.get('age_distribution', {})
        
        if '직장인' in targets:
            score += (age_dist.get('20s', 0) * 0.3 + age_dist.get('30s', 0) * 0.3 +
                     age_dist.get('40s', 0) * 0.2) * 0.8 + pop_data.get('non_resident_ratio', 0) * 0.2
            count += 1
        
        if '학생' in targets:
            score += age_dist.get('10s', 0) * 0.2 + age_dist.get('20s', 0) * 0.8
            count += 1
        
        if '주민' in targets:
            score += pop_data.get('resident_ratio', 0)
            count += 1
        
        if '관광객' in targets:
            score += pop_data.get('non_resident_ratio', 0)
            count += 1
        
        return score / count if count > 0 else 0