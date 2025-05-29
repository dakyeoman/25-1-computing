#!/usr/bin/env python3
### 월 임대료 데이터를 불러오고 있지 못함
### api 데이터를 모두 사용하고 있는 것인지 확인(임의로 설정한 데이터가 없어야 함) 

"""
서울시 창업 입지 선정 최적화를 위한 다중 기준 의사결정 알고리즘
- 파레토 최적화 (Pareto Optimization)
- 제약조건 만족 문제 (Constraint Satisfaction Problem)
- 다목적 최적화 (Multi-objective Optimization)
"""
"""
서울시 창업 입지 선정 최적화를 위한 다중 기준 의사결정 알고리즘
- 파레토 최적화 (Pareto Optimization)
- 제약조건 만족 문제 (Constraint Satisfaction Problem)
- 다목적 최적화 (Multi-objective Optimization)

데이터 출처:
1. 서울시 실시간 인구 현황 (citydata_ppltn)
   - API: http://openapi.seoul.go.kr:8088/{API_KEY}/json/citydata_ppltn/1/5/{지역명}
   - 제공: 서울시 스마트도시정책관
   - 내용: 실시간 유동인구, 연령별/성별 분포, 혼잡도

2. 서울시 실시간 상권 현황 (citydata_cmrcl)
   - API: http://openapi.seoul.go.kr:8088/{API_KEY}/json/citydata_cmrcl/1/5/{지역명}
   - 제공: 서울시 스마트도시정책관
   - 내용: 업종별 매장수, 결제건수, 결제금액

3. 서울시 상권분석서비스 - 추정매출 (VwsmAdstrdSelngW)
   - API: http://openapi.seoul.go.kr:8088/{API_KEY}/json/VwsmAdstrdSelngW/1/1000/
   - 제공: 서울시 소상공인정책과
   - 내용: 행정동별 업종별 추정매출, 점포수, 분기별 매출 추이

4. 서울시 부동산 전월세가 정보 (tbLnOpendataRentV)
   - API: http://openapi.seoul.go.kr:8088/{API_KEY}/json/tbLnOpendataRentV/1/1000/
   - 제공: 서울시 부동산정책과
   - 내용: 행정동별 임대료, 보증금, 면적별 시세
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
import requests
from urllib.parse import quote

# 기존 API 클라이언트 import
from seoul_api_client import SeoulDataAPIClient, Config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('startup_location.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class StartupConstraints:
    """창업 제약조건"""
    business_type: str
    target_customers: List[str]
    budget_min: int
    budget_max: int
    max_competition: int
    min_target_match: float  # 퍼센트 (0-100)
    max_rent: int = 0  # 최대 월 임대료 (선택)
    min_sales: int = 0  # 최소 예상 매출 (선택)


@dataclass
class LocationScore:
    """입지 점수 (3개 목적함수)"""
    area_name: str
    profitability: float = 0.0  # 수익성
    stability: float = 0.0      # 안정성
    accessibility: float = 0.0  # 접근성
    
    # 상세 데이터
    population_score: float = 0
    payment_activity_score: float = 0
    target_match_score: float = 0
    competition_score: float = 0
    budget_fit_score: float = 0
    non_resident_ratio: float = 0
    commercial_level_score: float = 0
    
    # 추가 데이터 (새 API)
    estimated_sales: float = 0  # 추정 매출
    rent_score: float = 0  # 임대료 적정성
    sales_trend: str = ""  # 매출 추세
    
    # 제약조건 만족 여부
    satisfies_constraints: bool = True
    constraint_details: Dict[str, bool] = field(default_factory=dict)
    
    # 원본 데이터
    raw_data: Dict = field(default_factory=dict)


class EnhancedDataCollector:
    """향상된 데이터 수집기 - 추가 API 통합"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://openapi.seoul.go.kr:8088"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 캐시 (반복 호출 방지)
        self.sales_cache = {}
        self.rent_cache = {}
        self.rent_data_loaded = False
        
    def fetch_sales_data(self) -> Dict:
        """서울시 상권분석 - 추정매출 데이터 수집"""
        if self.sales_cache:
            return self.sales_cache
            
        logger.info("상권 추정매출 데이터 수집 중...")
        sales_data = {}
        
        # 데이터가 많으므로 샘플만 수집 (1000건)
        url = f"{self.base_url}/{self.api_key}/json/VwsmAdstrdSelngW/1/1000/"
        
        try:
            response = self.session.get(url, timeout=60)  # 타임아웃 증가
            if response.status_code == 200:
                data = response.json()
                
                # 응답 확인
                if 'RESULT' in data:
                    code = data['RESULT'].get('CODE', '')
                    if code == 'INFO-200':
                        logger.warning("매출 데이터가 없습니다")
                        return sales_data
                    elif code != 'INFO-000' and code != '':
                        logger.warning(f"매출 API 오류: {code}")
                        return sales_data
                
                if 'VwsmAdstrdSelngW' in data and 'row' in data['VwsmAdstrdSelngW']:
                    rows = data['VwsmAdstrdSelngW']['row']
                    
                    for row in rows:
                        key = f"{row.get('ADSTRD_CD_NM', '')}_{row.get('SVC_INDUTY_CD_NM', '')}"
                        sales_data[key] = {
                            'area_name': row.get('ADSTRD_CD_NM', ''),
                            'service_type': row.get('SVC_INDUTY_CD_NM', ''),
                            'quarter': row.get('STDR_YYQU_CD', ''),
                            'monthly_sales': float(row.get('MONTH_SELNG_AMT', 0)),
                            'store_count': int(row.get('STOR_CO', 0)),
                            'sales_per_store': float(row.get('AVERG_SELNG_AMT', 0)),
                            'weekend_sales_ratio': float(row.get('WKEND_SELNG_RATE', 0)),
                            'weekday_sales_ratio': float(row.get('WKDAY_SELNG_RATE', 0)),
                            'male_sales_ratio': float(row.get('MALE_SELNG_RATE', 0)),
                            'female_sales_ratio': float(row.get('FEMALE_SELNG_RATE', 0))
                        }
                    
                    logger.info(f"수집된 매출 데이터: {len(sales_data)}건")
                        
        except requests.exceptions.Timeout:
            logger.error("매출 데이터 수집 타임아웃")
        except Exception as e:
            logger.error(f"매출 데이터 수집 오류: {e}")
        
        self.sales_cache = sales_data
        return sales_data
    
    def fetch_rent_data(self) -> Dict:
        """서울시 부동산 전월세가 정보 수집 - 간소화 버전"""
        if self.rent_data_loaded:
            return self.rent_cache
            
        logger.info("부동산 임대료 데이터 수집 시작...")
        rent_data = {}
        
        # API 호출을 최소화 - 500건만 수집
        url = f"{self.base_url}/{self.api_key}/json/tbLnOpendataRentV/1/500/"
        
        try:
            response = self.session.get(url, timeout=60)  # 타임아웃 증가
            if response.status_code == 200:
                data = response.json()
                
                # 응답 확인
                if 'RESULT' in data:
                    code = data['RESULT'].get('CODE', '')
                    if code == 'INFO-200':
                        logger.warning("임대료 데이터가 없습니다")
                        self.rent_data_loaded = True
                        return rent_data
                    elif code != 'INFO-000' and code != '':
                        logger.warning(f"임대료 API 오류: {code}")
                        self.rent_data_loaded = True
                        return rent_data
                
                if 'tbLnOpendataRentV' in data and 'row' in data['tbLnOpendataRentV']:
                    rows = data['tbLnOpendataRentV']['row']
                    processed = 0
                    
                    for row in rows:
                        # 상업용 부동산만 필터링
                        if row.get('BLDG_USES', '') in ['상가', '근린생활시설', '판매시설']:
                            address = row.get('ADRES', '')
                            if not address:
                                continue
                                
                            # 주소에서 지역명 추출 (더 안전하게)
                            parts = address.split()
                            area = None
                            
                            # 다양한 형태의 주소 처리
                            for i, part in enumerate(parts):
                                if '동' in part and i > 0:
                                    area = part
                                    break
                                elif '역' in part:
                                    area = part
                                    break
                            
                            if not area and len(parts) >= 3:
                                area = parts[2]  # 기본값
                            
                            if area:
                                if area not in rent_data:
                                    rent_data[area] = []
                                
                                rent_data[area].append({
                                    'rent_type': row.get('RENT_SE', ''),
                                    'deposit': int(row.get('RENT_GTN', 0) or 0),
                                    'monthly_rent': int(row.get('RENT_FEE', 0) or 0),
                                    'area': float(row.get('RENT_AREA', 0) or 0),
                                    'floor': row.get('FLOR_NO', ''),
                                    'contract_date': row.get('CNTRCT_DE', '')
                                })
                                processed += 1
                    
                    logger.info(f"처리된 임대료 데이터: {processed}건, {len(rent_data)}개 지역")
                else:
                    logger.warning("임대료 데이터 형식이 예상과 다름")
                    
        except requests.exceptions.Timeout:
            logger.error("임대료 데이터 수집 타임아웃 - 기본값 사용")
        except Exception as e:
            logger.error(f"임대료 데이터 수집 오류: {e}")
        
        self.rent_cache = rent_data
        self.rent_data_loaded = True
        return rent_data
    
    def get_area_sales_info(self, area_name: str, business_type: str) -> Optional[Dict]:
        """특정 지역의 업종별 매출 정보 조회"""
        # 매출 데이터가 없으면 시도하지 않음
        if not self.sales_cache:
            self.fetch_sales_data()
            
        if not self.sales_cache:
            return None
        
        # 업종 매핑
        business_mapping = {
            '카페': ['커피전문점', '커피-음료', '카페', '음료', '제과점'],
            '음식점': ['한식음식점', '한식', '양식', '중식', '일식', '분식', '기타외국식'],
            '주점': ['호프-간이주점', '주점', '포차', '술집'],
            '편의점': ['편의점'],
            '학원': ['학원', '교육', '일반교습학원'],
            '미용실': ['미용실', '헤어샵', '네일', '피부관리'],
            '약국': ['약국'],
            '헬스장': ['스포츠시설', '헬스', '요가', '필라테스', '스포츠클럽']
        }
        
        # 매칭되는 업종 찾기
        target_types = business_mapping.get(business_type, [business_type])
        
        # 지역명 변형 시도
        area_variations = [area_name]
        if '역' in area_name:
            area_variations.append(area_name.replace('역', ''))
        if '동' not in area_name:
            area_variations.append(area_name + '동')
        
        for area in area_variations:
            for service_type in target_types:
                key = f"{area}_{service_type}"
                if key in self.sales_cache:
                    return self.sales_cache[key]
        
        return None
    
    def get_area_rent_info(self, area_name: str) -> Dict:
        """특정 지역의 평균 임대료 정보"""
        # 캐시가 없으면 한 번 시도
        if not self.rent_data_loaded:
            self.fetch_rent_data()
        
        # 기본값
        default_info = {'avg_deposit': 0, 'avg_monthly_rent': 0, 'sample_count': 0}
        
        if not self.rent_cache:
            return default_info
        
        # 지역명 변형 시도
        area_variations = [area_name]
        if '역' in area_name:
            area_variations.append(area_name.replace('역', ''))
            area_variations.append(area_name.replace('역', '') + '동')
        if '동' not in area_name:
            area_variations.append(area_name + '동')
        
        for area in area_variations:
            if area in self.rent_cache:
                area_rents = self.rent_cache[area]
                
                # 월세 데이터만 필터링
                monthly_rents = [r for r in area_rents if r['rent_type'] == '월세' and r['monthly_rent'] > 0]
                
                if monthly_rents:
                    avg_deposit = sum(r['deposit'] for r in monthly_rents) / len(monthly_rents)
                    avg_monthly = sum(r['monthly_rent'] for r in monthly_rents) / len(monthly_rents)
                    
                    return {
                        'avg_deposit': avg_deposit,
                        'avg_monthly_rent': avg_monthly,
                        'sample_count': len(monthly_rents)
                    }
        
        return default_info


class MultiCriteriaOptimizer:
    """다중 기준 의사결정 최적화 시스템"""
    
    def __init__(self):
        self.client = SeoulDataAPIClient()
        self.enhanced_collector = EnhancedDataCollector(api_key="51504b7a6861646b35314b797a7771")
        
        # 업종별 적정 경쟁 수준 (매장 수)
        self.ideal_competition = {
            "카페": 40,
            "음식점": 50,
            "주점": 30,
            "편의점": 20,
            "학원": 15,
            "미용실": 25,
            "약국": 10,
            "헬스장": 8
        }
        
        # 상권 레벨 점수 매핑
        self.commercial_level_scores = {
            "매우높음": 100,
            "높음": 80,
            "보통": 60,
            "낮음": 40,
            "매우낮음": 20,
            "활발": 100,
            "정상": 80,
            "활성화된": 85,
            "점포밀집": 90,
            "집중": 85,
            "약간 밀집": 75,
            "분산": 65,
            "침체": 40,
            "한산한": 20,
            "미형성": 10,
            "쇠퇴": 30
        }
        
        # 임대료 데이터 미리 로드
        logger.info("초기화: 임대료 데이터 로드 중...")
        self.enhanced_collector.fetch_rent_data()
    
    def analyze_locations(self, areas: List[str], constraints: StartupConstraints) -> Dict:
        """전체 분석 프로세스 실행"""
        logger.info(f"분석 시작: {len(areas)}개 지역")
        
        # 1. API 데이터 수집 (병렬 처리)
        location_data = self._collect_data_parallel(areas)
        logger.info(f"데이터 수집 완료: {len(location_data)}개 지역")
        
        # 2. 제약조건 필터링 (CSP)
        filtered_locations = self._apply_constraints(location_data, constraints)
        logger.info(f"제약조건 통과: {len(filtered_locations)}개 지역")
        
        # 제약조건을 통과한 지역이 없는 경우 처리
        if len(filtered_locations) == 0:
            logger.warning("제약조건을 만족하는 지역이 없습니다.")
            return {
                'all_locations': location_data,
                'filtered_locations': [],
                'scored_locations': [],
                'pareto_optimal': [],
                'recommendations': {}
            }
        
        # 3. 목적함수 계산
        scored_locations = self._calculate_objectives(filtered_locations, constraints)
        
        # 4. 파레토 최적해 집합 도출
        pareto_optimal = self._find_pareto_optimal(scored_locations)
        logger.info(f"파레토 최적해: {len(pareto_optimal)}개")
        
        # 5. 결과 정리
        results = {
            'all_locations': location_data,
            'filtered_locations': filtered_locations,
            'scored_locations': scored_locations,
            'pareto_optimal': pareto_optimal,
            'recommendations': self._generate_recommendations(pareto_optimal)
        }
        
        return results
    
    def _collect_data_parallel(self, areas: List[str]) -> List[Dict]:
        """병렬로 API 데이터 수집"""
        location_data = []
        
        # 병렬 처리를 Sequential로 변경하여 디버깅
        for area in areas:
            try:
                data = self._fetch_area_data(area)
                if data:
                    location_data.append(data)
                else:
                    logger.warning(f"No data received for {area}")
            except Exception as e:
                logger.error(f"Error fetching data for {area}: {e}", exc_info=True)
        
        return location_data
    
    def _fetch_area_data(self, area_name: str) -> Optional[Dict]:
        """단일 지역 데이터 수집 - 모든 데이터 소스 통합"""
        try:
            # 기존 API 데이터
            pop_data = self.client.get_population_data(area_name)
            com_data = self.client.get_commercial_data(area_name)
            
            # 임대료 정보 수집
            rent_info = self.enhanced_collector.get_area_rent_info(area_name)
            
            if pop_data and com_data:
                return {
                    'area_name': area_name,
                    'population': pop_data,
                    'commercial': com_data,
                    'sales': None,  # 나중에 업종별로 채워짐
                    'rent': rent_info
                }
            else:
                logger.warning(f"No data for {area_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error in _fetch_area_data for {area_name}: {e}")
            return None
    
    def _apply_constraints(self, location_data: List[Dict], constraints: StartupConstraints) -> List[Dict]:
        """제약조건 만족 문제 (CSP) 해결 - 백트래킹"""
        filtered = []
        
        for loc in location_data:
            constraint_check = self._check_constraints(loc, constraints)
            loc['constraint_check'] = constraint_check
            
            if constraint_check['satisfies_all']:
                filtered.append(loc)
            else:
                logger.info(f"{loc['area_name']} 제외: {constraint_check['failed_constraints']}")
        
        return filtered
    
    def _check_constraints(self, location: Dict, constraints: StartupConstraints) -> Dict:
        """개별 제약조건 확인 - 향상된 버전"""
        results = {
            'budget': True,
            'competition': True,
            'target_match': True,
            'rent': True,
            'sales': True,
            'satisfies_all': True,
            'failed_constraints': []
        }
        
        com_data = location['commercial']
        pop_data = location['population']
        sales_data = location.get('sales')
        rent_data = location.get('rent', {})
        
        # 1. 예산 제약 (카페별 실제 결제 데이터 사용)
        cafe_payment = self._get_business_payment_amount(com_data, constraints.business_type)
        if cafe_payment > 0:
            if cafe_payment < constraints.budget_min or cafe_payment > constraints.budget_max:
                results['budget'] = False
                results['failed_constraints'].append(
                    f"{constraints.business_type} 평균결제액 부적합: {cafe_payment:,.0f}원"
                )
        
        # 2. 경쟁 제약 (업종별 정확한 매장 수)
        competition_count = self._count_business_stores(com_data, constraints.business_type)
        if competition_count > constraints.max_competition:
            results['competition'] = False
            results['failed_constraints'].append(f"과도한 경쟁: {competition_count}개 매장")
        
        # 3. 타겟 매칭 제약
        target_match = self._calculate_target_match(pop_data, constraints.target_customers)
        if target_match < constraints.min_target_match:
            results['target_match'] = False
            results['failed_constraints'].append(f"타겟 매칭 부족: {target_match:.1f}%")
        
        # 4. 임대료 제약 (선택)
        if constraints.max_rent > 0 and rent_data.get('avg_monthly_rent', 0) > 0:
            if rent_data['avg_monthly_rent'] > constraints.max_rent:
                results['rent'] = False
                results['failed_constraints'].append(
                    f"임대료 초과: {rent_data['avg_monthly_rent']:,.0f}원"
                )
        
        # 5. 최소 매출 제약 (선택)
        if constraints.min_sales > 0 and sales_data:
            if sales_data.get('monthly_sales', 0) < constraints.min_sales:
                results['sales'] = False
                results['failed_constraints'].append(
                    f"예상 매출 부족: {sales_data.get('monthly_sales', 0):,.0f}원"
                )
        
        results['satisfies_all'] = all([
            results['budget'], results['competition'], results['target_match'],
            results['rent'], results['sales']
        ])
        
        return results
    
    def _get_business_payment_amount(self, com_data: Dict, business_type: str) -> float:
        """특정 업종의 평균 결제금액 추출"""
        business_keywords = {
            '카페': ['카페', '커피', '음료', '디저트'],
            '음식점': ['한식', '중식', '일식', '양식', '분식'],
            '주점': ['주점', '호프', '포차'],
            '편의점': ['편의점'],
            '학원': ['학원', '교육'],
            '미용실': ['미용', '헤어', '네일'],
            '약국': ['약국'],
            '헬스장': ['스포츠', '헬스', '피트니스']
        }
        
        keywords = business_keywords.get(business_type, [business_type])
        total_amount = 0
        count = 0
        
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                
                for keyword in keywords:
                    if keyword in category:
                        min_pay = biz.get('payment_amount_min', 0)
                        max_pay = biz.get('payment_amount_max', 0)
                        if min_pay > 0 or max_pay > 0:
                            avg_pay = (min_pay + max_pay) / 2
                            # 단위 보정
                            if avg_pay > 100000:
                                avg_pay = avg_pay / 1000
                            total_amount += avg_pay
                            count += 1
                        break
        
        # 업종별 데이터가 없으면 전체 평균 사용
        if count == 0:
            min_payment = com_data.get('area_payment_amount', {}).get('min', 0)
            max_payment = com_data.get('area_payment_amount', {}).get('max', 0)
            if min_payment > 0 or max_payment > 0:
                avg_payment = (min_payment + max_payment) / 2
                if avg_payment > 100000:
                    avg_payment = avg_payment / 1000
                return avg_payment
            return 0
        
        return total_amount / count
    
    def _count_business_stores(self, com_data: Dict, business_type: str) -> int:
        """특정 업종의 매장 수 계산"""
        business_keywords = {
            '카페': ['카페', '커피', '음료', '디저트', '베이커리'],
            '음식점': ['한식', '중식', '일식', '양식', '분식', '음식'],
            '주점': ['주점', '호프', '포차', '술집'],
            '편의점': ['편의점'],
            '학원': ['학원', '교육', '입시'],
            '미용실': ['미용', '헤어', '네일', '뷰티'],
            '약국': ['약국'],
            '헬스장': ['스포츠', '헬스', '피트니스', '요가']
        }
        
        keywords = business_keywords.get(business_type, [business_type])
        total_count = 0
        
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                
                for keyword in keywords:
                    if keyword in category:
                        total_count += biz.get('merchant_count', 0)
                        logger.debug(f"Found {business_type}: {category} - {biz.get('merchant_count', 0)}개")
                        break
        
        # 데이터가 없으면 결제 건수로 추정
        if total_count == 0 and com_data.get('area_payment_count', 0) > 0:
            estimated_stores = com_data.get('area_payment_count', 0) / (50 * 30)
            total_count = int(estimated_stores)
        
        return total_count
    
    def _calculate_target_match(self, pop_data: Dict, target_customers: List[str]) -> float:
        """타겟 고객 매칭률 계산"""
        total_score = 0
        count = 0
        
        if '직장인' in target_customers:
            # 20-50대 비율 + 비거주민 비율
            worker_score = (
                pop_data['age_distribution'].get('20s', 0) * 0.3 +
                pop_data['age_distribution'].get('30s', 0) * 0.3 +
                pop_data['age_distribution'].get('40s', 0) * 0.2 +
                pop_data['age_distribution'].get('50s', 0) * 0.2
            )
            worker_score = worker_score * 0.8 + pop_data.get('non_resident_ratio', 0) * 0.2
            total_score += worker_score
            count += 1
        
        if '학생' in target_customers:
            # 10-20대 비율
            student_score = (
                pop_data['age_distribution'].get('10s', 0) * 0.2 +
                pop_data['age_distribution'].get('20s', 0) * 0.8
            )
            total_score += student_score
            count += 1
        
        if '주민' in target_customers:
            # 거주민 비율
            resident_score = pop_data.get('resident_ratio', 0)
            total_score += resident_score
            count += 1
        
        if '관광객' in target_customers:
            # 비거주민 비율 + 관광특구 보너스
            tourist_score = pop_data.get('non_resident_ratio', 0)
            if '관광특구' in pop_data.get('area_name', ''):
                tourist_score = min(tourist_score + 30, 100)
            total_score += tourist_score
            count += 1
        
        return total_score / count if count > 0 else 0
    
    def _calculate_objectives(self, locations: List[Dict], constraints: StartupConstraints) -> List[LocationScore]:
        """3개 목적함수 계산 - 향상된 버전"""
        scored_locations = []
        
        for loc in locations:
            pop_data = loc['population']
            com_data = loc['commercial']
            
            # 업종별 매출 데이터 가져오기
            sales_data = self.enhanced_collector.get_area_sales_info(
                loc['area_name'], constraints.business_type
            )
            loc['sales'] = sales_data  # 업데이트
            
            rent_data = loc.get('rent', {})
            
            # 개별 점수 계산
            scores = LocationScore(area_name=loc['area_name'])
            
            # 1. 유동인구 점수 (조정된 기준)
            max_pop = pop_data.get('population_max', 0)
            scores.population_score = min(100, (max_pop / 30000) * 100)
            
            # 2. 결제 활성도 점수 (업종별)
            payment_cnt = self._get_business_payment_count(com_data, constraints.business_type)
            scores.payment_activity_score = min(100, (payment_cnt / 10000) * 100)
            
            # 3. 타겟 매칭 점수
            scores.target_match_score = self._calculate_target_match(pop_data, constraints.target_customers)
            
            # 4. 적정 경쟁 점수 (역U자형)
            competition_count = self._count_business_stores(com_data, constraints.business_type)
            ideal = self.ideal_competition.get(constraints.business_type, 30)
            if competition_count <= ideal:
                scores.competition_score = 60 + (competition_count / ideal) * 40
            else:
                scores.competition_score = max(30, 100 - (competition_count - ideal) / ideal * 70)
            
            # 5. 예산 적합도 점수
            cafe_payment = self._get_business_payment_amount(com_data, constraints.business_type)
            if cafe_payment > 0:
                budget_center = (constraints.budget_min + constraints.budget_max) / 2
                budget_range = constraints.budget_max - constraints.budget_min
                
                if constraints.budget_min <= cafe_payment <= constraints.budget_max:
                    distance_from_center = abs(cafe_payment - budget_center)
                    scores.budget_fit_score = 100 - (distance_from_center / (budget_range / 2)) * 20
                else:
                    if cafe_payment < constraints.budget_min:
                        ratio = cafe_payment / constraints.budget_min
                        scores.budget_fit_score = max(0, ratio * 50)
                    else:
                        ratio = constraints.budget_max / cafe_payment
                        scores.budget_fit_score = max(0, ratio * 50)
            else:
                scores.budget_fit_score = 50
            
            # 6. 비거주민 비율
            scores.non_resident_ratio = pop_data.get('non_resident_ratio', 0)
            
            # 7. 상권 레벨 점수
            level = com_data.get('area_commercial_level', '보통')
            scores.commercial_level_score = self.commercial_level_scores.get(level, 60)
            
            # 8. 추정 매출 (새 API 데이터)
            if sales_data:
                scores.estimated_sales = sales_data.get('monthly_sales', 0)
                # 매출 추세 분석
                weekend_ratio = sales_data.get('weekend_sales_ratio', 0)
                if weekend_ratio > 60:
                    scores.sales_trend = "주말 중심"
                elif weekend_ratio < 40:
                    scores.sales_trend = "평일 중심"
                else:
                    scores.sales_trend = "균형"
            
            # 9. 임대료 적정성 점수 (새 API 데이터)
            if rent_data.get('avg_monthly_rent', 0) > 0:
                # 예상 매출 대비 임대료 비율 (적정: 10-15%)
                if scores.estimated_sales > 0:
                    rent_ratio = (rent_data['avg_monthly_rent'] / scores.estimated_sales) * 100
                    if 10 <= rent_ratio <= 15:
                        scores.rent_score = 100
                    elif rent_ratio < 10:
                        scores.rent_score = 80  # 저렴하지만 상권이 약할 수 있음
                    elif rent_ratio <= 20:
                        scores.rent_score = 100 - (rent_ratio - 15) * 10
                    else:
                        scores.rent_score = max(0, 50 - (rent_ratio - 20) * 2)
                else:
                    scores.rent_score = 50
            else:
                scores.rent_score = 50
            
            # 목적함수 계산 (가중치 조정)
            # 수익성 = 0.3 × 유동인구 + 0.3 × 결제활성도 + 0.2 × 타겟매칭 + 0.2 × 추정매출
            if scores.estimated_sales > 0:
                sales_score = min(100, (scores.estimated_sales / 100000000) * 100)  # 1억 기준
                scores.profitability = (
                    0.3 * scores.population_score +
                    0.3 * scores.payment_activity_score +
                    0.2 * scores.target_match_score +
                    0.2 * sales_score
                )
            else:
                scores.profitability = (
                    0.4 * scores.population_score +
                    0.4 * scores.payment_activity_score +
                    0.2 * scores.target_match_score
                )
            
            # 안정성 = 0.4 × 적정경쟁 + 0.3 × 예산적합도 + 0.3 × 임대료적정성
            scores.stability = (
                0.4 * scores.competition_score +
                0.3 * scores.budget_fit_score +
                0.3 * scores.rent_score
            )
            
            # 접근성 = 0.6 × 비거주민비율 + 0.4 × 상권레벨
            scores.accessibility = (
                0.6 * scores.non_resident_ratio +
                0.4 * scores.commercial_level_score
            )
            
            scores.raw_data = loc
            scored_locations.append(scores)
        
        return scored_locations
    
    def _get_business_payment_count(self, com_data: Dict, business_type: str) -> int:
        """특정 업종의 결제 건수 추출"""
        business_keywords = {
            '카페': ['카페', '커피', '음료'],
            '음식점': ['한식', '중식', '일식', '양식', '분식'],
            '주점': ['주점', '호프', '포차'],
            '편의점': ['편의점'],
            '학원': ['학원', '교육'],
            '미용실': ['미용', '헤어', '네일'],
            '약국': ['약국'],
            '헬스장': ['스포츠', '헬스', '피트니스']
        }
        
        keywords = business_keywords.get(business_type, [business_type])
        total_count = 0
        
        if 'business_categories' in com_data:
            for biz in com_data['business_categories']:
                category = f"{biz.get('large_category', '')} {biz.get('mid_category', '')}"
                
                for keyword in keywords:
                    if keyword in category:
                        total_count += biz.get('payment_count', 0)
                        break
        
        # 데이터가 없으면 전체 평균 사용
        if total_count == 0:
            total_count = com_data.get('area_payment_count', 0)
        
        return total_count
    
    def _find_pareto_optimal(self, locations: List[LocationScore]) -> List[LocationScore]:
        """파레토 최적해 집합 도출"""
        pareto_optimal = []
        
        for i, loc1 in enumerate(locations):
            is_dominated = False
            
            for j, loc2 in enumerate(locations):
                if i == j:
                    continue
                
                # loc2가 loc1을 지배하는지 확인
                if (loc2.profitability >= loc1.profitability and
                    loc2.stability >= loc1.stability and
                    loc2.accessibility >= loc1.accessibility and
                    (loc2.profitability > loc1.profitability or
                     loc2.stability > loc1.stability or
                     loc2.accessibility > loc1.accessibility)):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto_optimal.append(loc1)
        
        # 파레토 최적해를 각 목적함수별로 정렬
        pareto_optimal.sort(key=lambda x: x.profitability + x.stability + x.accessibility, reverse=True)
        
        return pareto_optimal
    
    def _generate_recommendations(self, pareto_optimal: List[LocationScore]) -> Dict:
        """추천 결과 생성"""
        recommendations = {
            'best_overall': None,
            'best_profitability': None,
            'best_stability': None,
            'best_accessibility': None,
            'balanced': []
        }
        
        if not pareto_optimal:
            return recommendations
        
        # 전체 최고 점수
        recommendations['best_overall'] = max(
            pareto_optimal,
            key=lambda x: x.profitability + x.stability + x.accessibility
        )
        
        # 각 목적함수별 최고
        recommendations['best_profitability'] = max(pareto_optimal, key=lambda x: x.profitability)
        recommendations['best_stability'] = max(pareto_optimal, key=lambda x: x.stability)
        recommendations['best_accessibility'] = max(pareto_optimal, key=lambda x: x.accessibility)
        
        # 균형 잡힌 지역 (모든 점수가 60점 이상)
        recommendations['balanced'] = [
            loc for loc in pareto_optimal
            if loc.profitability >= 60 and loc.stability >= 60 and loc.accessibility >= 60
        ]
        
        return recommendations


def get_user_input() -> Tuple[List[str], StartupConstraints]:
    """사용자 입력 받기"""
    print("\n" + "="*60)
    print("🏪 서울시 창업 입지 추천 시스템")
    print("="*60)
    
    # 업종 선택
    business_types = ['카페', '음식점', '주점', '편의점', '학원', '미용실', '약국', '헬스장']
    print("\n📋 업종을 선택하세요:")
    for i, btype in enumerate(business_types, 1):
        print(f"  {i}. {btype}")
    
    while True:
        try:
            choice = int(input("선택 (1-8): "))
            if 1 <= choice <= 8:
                business_type = business_types[choice-1]
                break
            else:
                print("1-8 사이의 숫자를 입력하세요.")
        except ValueError:
            print("올바른 숫자를 입력하세요.")
    
    # 타겟 고객 선택
    print("\n👥 타겟 고객을 선택하세요 (여러 개 선택 가능, 쉼표로 구분):")
    print("  1. 직장인\n  2. 학생\n  3. 주민\n  4. 관광객")
    
    target_mapping = {'1': '직장인', '2': '학생', '3': '주민', '4': '관광객'}
    target_input = input("선택 (예: 1,2): ").strip()
    target_customers = [target_mapping[x.strip()] for x in target_input.split(',') if x.strip() in target_mapping]
    
    if not target_customers:
        target_customers = ['직장인']  # 기본값
        print("기본값으로 '직장인'이 선택되었습니다.")
    
    # 예산 범위
    print("\n💰 객단가 예산 범위 (원):")
    while True:
        try:
            budget_min = int(input("  최소: "))
            budget_max = int(input("  최대: "))
            if budget_min < budget_max:
                break
            else:
                print("최소값이 최대값보다 작아야 합니다.")
        except ValueError:
            print("올바른 숫자를 입력하세요.")
    
    # 경쟁 수준
    print("\n🏢 최대 허용 경쟁 매장 수:")
    while True:
        try:
            max_competition = int(input("  개수: "))
            if max_competition > 0:
                break
            else:
                print("1개 이상의 값을 입력하세요.")
        except ValueError:
            print("올바른 숫자를 입력하세요.")
    
    # 타겟 매칭률
    print("\n🎯 최소 타겟 고객 매칭률 (%):")
    while True:
        try:
            min_target_match = float(input("  비율 (0-100): "))
            if 0 <= min_target_match <= 100:
                break
            else:
                print("0-100 사이의 값을 입력하세요.")
        except ValueError:
            print("올바른 숫자를 입력하세요.")
    
    # 임대료 제약 (선택)
    print("\n🏠 최대 월 임대료 (선택사항, 0 입력시 제약 없음):")
    try:
        max_rent = int(input("  월 임대료 (원): "))
    except ValueError:
        max_rent = 0
    
    # 최소 매출 제약 (선택)
    print("\n💵 최소 예상 월매출 (선택사항, 0 입력시 제약 없음):")
    try:
        min_sales = int(input("  월매출 (원): "))
    except ValueError:
        min_sales = 0
    
    # 분석할 지역 선택
    print("\n📍 분석할 지역을 선택하세요:")
    print("  1. 주요 상권 5개 (빠른 테스트)")
    print("  2. 주요 상권 20개")
    print("  3. 전체 82개 지역 (시간 소요)")
    print("  4. 직접 입력")
    
    area_choice = input("선택 (1-4): ").strip()
    
    if area_choice == '1':
        areas = Config.TEST_AREAS
    elif area_choice == '2':
        areas = Config.AVAILABLE_AREAS[:20]
    elif area_choice == '3':
        areas = Config.AVAILABLE_AREAS
    elif area_choice == '4':
        print("\n지역명을 입력하세요 (쉼표로 구분):")
        print("예: 강남역, 홍대입구역, 명동")
        custom_input = input("지역명: ")
        areas = [area.strip() for area in custom_input.split(',') if area.strip()]
        if not areas:
            print("기본값으로 주요 5개 지역이 선택되었습니다.")
            areas = Config.TEST_AREAS
    else:
        areas = Config.TEST_AREAS
    
    constraints = StartupConstraints(
        business_type=business_type,
        target_customers=target_customers,
        budget_min=budget_min,
        budget_max=budget_max,
        max_competition=max_competition,
        min_target_match=min_target_match,
        max_rent=max_rent,
        min_sales=min_sales
    )
    
    return areas, constraints


def display_results(results: Dict, constraints: StartupConstraints):
    """결과 출력"""
    print("\n" + "="*80)
    print("📊 분석 결과")
    print("="*80)
    
    # 기본 통계
    print(f"\n📈 분석 요약:")
    print(f"  - 전체 분석 지역: {len(results['all_locations'])}개")
    print(f"  - 제약조건 통과: {len(results['filtered_locations'])}개")
    print(f"  - 파레토 최적해: {len(results['pareto_optimal'])}개")
    
    # 제약조건
    print(f"\n🔍 적용된 제약조건:")
    print(f"  - 업종: {constraints.business_type}")
    print(f"  - 타겟 고객: {', '.join(constraints.target_customers)}")
    print(f"  - 객단가: {constraints.budget_min:,}~{constraints.budget_max:,}원")
    print(f"  - 최대 경쟁 매장: {constraints.max_competition}개")
    print(f"  - 최소 타겟 매칭률: {constraints.min_target_match}%")
    if constraints.max_rent > 0:
        print(f"  - 최대 월 임대료: {constraints.max_rent:,}원")
    if constraints.min_sales > 0:
        print(f"  - 최소 월매출: {constraints.min_sales:,}원")
    
    # 추천 결과
    recommendations = results['recommendations']
    
    if recommendations['best_overall']:
        print("\n🏆 종합 최우수 지역:")
        best = recommendations['best_overall']
        print(f"  📍 {best.area_name}")
        print(f"     - 수익성: {best.profitability:.1f}점")
        print(f"     - 안정성: {best.stability:.1f}점")
        print(f"     - 접근성: {best.accessibility:.1f}점")
        print(f"     - 종합점수: {best.profitability + best.stability + best.accessibility:.1f}점")
        
        # 상세 정보
        rent_info = best.raw_data.get('rent', {})
        if rent_info.get('avg_monthly_rent', 0) > 0:
            print(f"     - 평균 월임대료: {rent_info['avg_monthly_rent']:,.0f}원")
            print(f"     - 평균 보증금: {rent_info['avg_deposit']:,.0f}원")
        
        if best.estimated_sales > 0:
            print(f"     - 예상 월매출: {best.estimated_sales:,.0f}원")
            print(f"     - 매출 패턴: {best.sales_trend}")
    
    # 목적별 최적 지역
    print("\n목적별 최적 지역:")
    
    if recommendations['best_profitability']:
        loc = recommendations['best_profitability']
        print(f"\n  최대 수익성: {loc.area_name} ({loc.profitability:.1f}점)")
        if loc.estimated_sales > 0:
            print(f"     - 예상 월매출: {loc.estimated_sales:,.0f}원")
    
    if recommendations['best_stability']:
        loc = recommendations['best_stability']
        print(f"\n  최대 안정성: {loc.area_name} ({loc.stability:.1f}점)")
        rent_info = loc.raw_data.get('rent', {})
        if rent_info.get('avg_monthly_rent', 0) > 0:
            print(f"     - 평균 월임대료: {rent_info['avg_monthly_rent']:,.0f}원")
    
    if recommendations['best_accessibility']:
        loc = recommendations['best_accessibility']
        print(f"\n  최대 접근성: {loc.area_name} ({loc.accessibility:.1f}점)")
        print(f"     - 비거주민 비율: {loc.non_resident_ratio:.1f}%")
    
    # 균형잡힌 지역
    if recommendations['balanced']:
        print(f"\n⚖️ 균형잡힌 지역 (모든 점수 60점 이상):")
        for loc in recommendations['balanced'][:5]:  # 상위 5개만
            print(f"  - {loc.area_name}: 수익성 {loc.profitability:.1f}, 안정성 {loc.stability:.1f}, 접근성 {loc.accessibility:.1f}")
            rent_info = loc.raw_data.get('rent', {})
            if rent_info.get('avg_monthly_rent', 0) > 0:
                print(f"    월임대료: {rent_info['avg_monthly_rent']:,.0f}원")
    
    # 파레토 최적해 전체 목록
    print("\n파레토 최적해 상위 10개:")
    print("-" * 80)
    print(f"{'순위':<4} {'지역명':<20} {'수익성':<8} {'안정성':<8} {'접근성':<8} {'종합':<8} {'월임대료':<12}")
    print("-" * 80)
    
    for i, loc in enumerate(results['pareto_optimal'][:10], 1):
        total_score = loc.profitability + loc.stability + loc.accessibility
        rent_info = loc.raw_data.get('rent', {})
        rent_str = f"{rent_info.get('avg_monthly_rent', 0):,.0f}" if rent_info.get('avg_monthly_rent', 0) > 0 else "정보없음"
        
        print(f"{i:<4} {loc.area_name:<20} {loc.profitability:<8.1f} {loc.stability:<8.1f} "
              f"{loc.accessibility:<8.1f} {total_score:<8.1f} {rent_str:<12}")


def main():
    """메인 함수"""
    try:
        # 사용자 입력
        areas, constraints = get_user_input()
        
        print(f"\n🔄 {len(areas)}개 지역 분석을 시작합니다...")
        print("(API 호출 중... 잠시만 기다려주세요)")
        
        # 최적화 시스템 실행
        optimizer = MultiCriteriaOptimizer()
        results = optimizer.analyze_locations(areas, constraints)
        
        # 결과 출력
        display_results(results, constraints)
        
        # 결과 저장 옵션
        save = input("\n💾 결과를 JSON 파일로 저장하시겠습니까? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"startup_location_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # LocationScore 객체를 dict로 변환
            results_for_save = {
                'constraints': {
                    'business_type': constraints.business_type,
                    'target_customers': constraints.target_customers,
                    'budget_min': constraints.budget_min,
                    'budget_max': constraints.budget_max,
                    'max_competition': constraints.max_competition,
                    'min_target_match': constraints.min_target_match,
                    'max_rent': constraints.max_rent,
                    'min_sales': constraints.min_sales
                },
                'analysis_summary': {
                    'total_areas': len(results['all_locations']),
                    'filtered_areas': len(results['filtered_locations']),
                    'pareto_optimal': len(results['pareto_optimal'])
                },
                'pareto_optimal_locations': [
                    {
                        'area_name': loc.area_name,
                        'scores': {
                            'profitability': loc.profitability,
                            'stability': loc.stability,
                            'accessibility': loc.accessibility,
                            'total': loc.profitability + loc.stability + loc.accessibility
                        },
                        'details': {
                            'population_score': loc.population_score,
                            'payment_activity_score': loc.payment_activity_score,
                            'target_match_score': loc.target_match_score,
                            'competition_score': loc.competition_score,
                            'budget_fit_score': loc.budget_fit_score,
                            'commercial_level_score': loc.commercial_level_score,
                            'estimated_sales': loc.estimated_sales,
                            'rent_score': loc.rent_score,
                            'sales_trend': loc.sales_trend
                        },
                        'rent_info': loc.raw_data.get('rent', {})
                    }
                    for loc in results['pareto_optimal']
                ]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results_for_save, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 결과가 {filename}에 저장되었습니다.")
        
        print("\n프로그램을 종료합니다. 감사합니다! 👋")
        
    except KeyboardInterrupt:
        print("\n\n프로그램이 중단되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {e}")
        print(f"\n❌ 오류가 발생했습니다: {e}")
        print("프로그램을 종료합니다.")


if __name__ == "__main__":
    main()