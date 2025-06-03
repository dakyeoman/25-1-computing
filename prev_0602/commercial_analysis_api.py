#!/usr/bin/env python3
"""
commercial_analysis_api.py - 서울시 상권분석서비스 API 클라이언트
실제 매출, 유동인구, 점포 데이터를 제공
"""

import requests
import xml.etree.ElementTree as ET
import logging
from typing import Dict, List, Optional
from urllib.parse import quote
import json

logger = logging.getLogger(__name__)


class CommercialAnalysisAPIClient:
    """서울시 상권분석서비스 API 클라이언트"""
    
    def __init__(self, api_key: str = "51504b7a6861646b35314b797a7771"):
        self.api_key = api_key
        self.base_url = "http://openapi.seoul.go.kr:8088"
        
        # 상권코드 매핑 (주요 지역)
        self.area_to_trdar_code = {
            '강남역': '1000001',
            '홍대입구역': '1000002',
            '명동': '1000003',
            '종로': '1000004',
            '신촌역': '1000005',
            '건대입구역': '1000006',
            '이태원역': '1000007',
            '성수역': '1000008',
            '여의도': '1000009',
            '잠실역': '1000010'
            # 실제 상권코드로 업데이트 필요
        }
        
        # 행정동 코드 매핑
        self.area_to_dong_code = {
            '강남역': '1168010100',  # 역삼1동
            '홍대입구역': '1144012000',  # 서교동
            '명동': '1114012600',  # 명동
            '종로': '1111012600',  # 종로1가동
            '신촌역': '1141011500',  # 신촌동
            # 더 많은 매핑 추가 필요
        }
    
    def get_commercial_area_data(self, area_name: str) -> Optional[Dict]:
        """상권 영역 데이터 조회 (실제 매출, 유동인구)"""
        # 상권코드 찾기
        trdar_code = self.area_to_trdar_code.get(area_name)
        if not trdar_code:
            logger.warning(f"상권코드를 찾을 수 없음: {area_name}")
            return self._search_by_area_name(area_name)
        
        url = f"{self.base_url}/{self.api_key}/xml/TbgisTrdarRelm/1/100/"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return self._parse_commercial_xml(response.text, area_name)
        except Exception as e:
            logger.error(f"상권 데이터 조회 실패: {e}")
        
        return None
    
    def get_dong_commercial_data(self, area_name: str) -> Optional[Dict]:
        """행정동별 상권 데이터 조회"""
        dong_code = self.area_to_dong_code.get(area_name)
        if not dong_code:
            logger.warning(f"행정동 코드를 찾을 수 없음: {area_name}")
            return None
        
        url = f"{self.base_url}/{self.api_key}/xml/TbgisAdstrdRelmW/1/100/{dong_code}"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return self._parse_dong_xml(response.text)
        except Exception as e:
            logger.error(f"행정동 데이터 조회 실패: {e}")
        
        return None
    
    def _search_by_area_name(self, area_name: str) -> Optional[Dict]:
        """지역명으로 검색 (전체 데이터에서)"""
        url = f"{self.base_url}/{self.api_key}/xml/TbgisTrdarRelm/1/1000/"
        
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                return self._parse_commercial_xml(response.text, area_name)
        except Exception as e:
            logger.error(f"전체 검색 실패: {e}")
        
        return None
    
    def _parse_commercial_xml(self, xml_text: str, target_area: str) -> Optional[Dict]:
        """상권 XML 데이터 파싱"""
        try:
            root = ET.fromstring(xml_text)
            
            # 에러 체크
            if root.find('.//CODE') is not None:
                code = root.find('.//CODE').text
                if code != 'INFO-000':
                    logger.warning(f"API 에러: {code}")
                    return None
            
            # 데이터 추출
            for row in root.findall('.//row'):
                area_nm = row.find('TRDAR_CD_NM')
                if area_nm is not None and target_area in area_nm.text:
                    return self._extract_commercial_data(row)
            
            return None
            
        except Exception as e:
            logger.error(f"XML 파싱 실패: {e}")
            return None
    
    def _extract_commercial_data(self, row: ET.Element) -> Dict:
        """상권 데이터 추출"""
        def safe_int(elem, tag, default=0):
            try:
                node = elem.find(tag)
                if node is not None and node.text:
                    return int(float(node.text))
            except:
                pass
            return default
        
        def safe_float(elem, tag, default=0.0):
            try:
                node = elem.find(tag)
                if node is not None and node.text:
                    return float(node.text)
            except:
                pass
            return default
        
        return {
            'trdar_code': row.find('TRDAR_CD').text if row.find('TRDAR_CD') is not None else '',
            'trdar_name': row.find('TRDAR_CD_NM').text if row.find('TRDAR_CD_NM') is not None else '',
            
            # 실제 유동인구 데이터
            'floating_population': {
                'total': safe_int(row, 'TOT_FLPOP_CO'),  # 총 유동인구
                'male': safe_int(row, 'ML_FLPOP_CO'),    # 남성 유동인구
                'female': safe_int(row, 'FML_FLPOP_CO'),  # 여성 유동인구
                
                # 시간대별 유동인구
                'time_00_06': safe_int(row, 'TMZON_00_06_FLPOP_CO'),
                'time_06_11': safe_int(row, 'TMZON_06_11_FLPOP_CO'),
                'time_11_14': safe_int(row, 'TMZON_11_14_FLPOP_CO'),
                'time_14_17': safe_int(row, 'TMZON_14_17_FLPOP_CO'),
                'time_17_21': safe_int(row, 'TMZON_17_21_FLPOP_CO'),
                'time_21_24': safe_int(row, 'TMZON_21_24_FLPOP_CO'),
                
                # 요일별 유동인구
                'mon': safe_int(row, 'MON_FLPOP_CO'),
                'tue': safe_int(row, 'TUES_FLPOP_CO'),
                'wed': safe_int(row, 'WED_FLPOP_CO'),
                'thu': safe_int(row, 'THUR_FLPOP_CO'),
                'fri': safe_int(row, 'FRI_FLPOP_CO'),
                'sat': safe_int(row, 'SAT_FLPOP_CO'),
                'sun': safe_int(row, 'SUN_FLPOP_CO'),
                
                # 연령대별 유동인구
                'age_10': safe_int(row, 'AGRDE_10_FLPOP_CO'),
                'age_20': safe_int(row, 'AGRDE_20_FLPOP_CO'),
                'age_30': safe_int(row, 'AGRDE_30_FLPOP_CO'),
                'age_40': safe_int(row, 'AGRDE_40_FLPOP_CO'),
                'age_50': safe_int(row, 'AGRDE_50_FLPOP_CO'),
                'age_60': safe_int(row, 'AGRDE_60_ABOVE_FLPOP_CO')
            },
            
            # 실제 상주인구 데이터
            'resident_population': {
                'total': safe_int(row, 'TOT_REPOP_CO'),      # 총 상주인구
                'resident': safe_int(row, 'TOT_WRC_POPLTN_CO'),  # 거주인구
                'worker': safe_int(row, 'TOT_WORK_POPLTN_CO')    # 직장인구
            },
            
            # 실제 매출 데이터
            'sales_data': {
                'monthly_sales': safe_int(row, 'THSMON_SELNG_AMT'),  # 당월 매출액
                'store_count': safe_int(row, 'STOR_CO'),             # 점포수
                
                # 업종별 매출액
                'food_sales': safe_int(row, 'FD_THSMON_SELNG_AMT'),        # 음식점
                'retail_sales': safe_int(row, 'RETL_THSMON_SELNG_AMT'),    # 소매
                'service_sales': safe_int(row, 'SERV_THSMON_SELNG_AMT'),   # 서비스
                
                # 업종별 점포수
                'food_stores': safe_int(row, 'FD_STOR_CO'),
                'retail_stores': safe_int(row, 'RETL_STOR_CO'),
                'service_stores': safe_int(row, 'SERV_STOR_CO')
            },
            
            # 실제 임대료 데이터
            'rent_data': {
                'avg_rent': safe_int(row, 'RENT_FEE'),              # 평균 임대료
                'avg_deposit': safe_int(row, 'RENT_GUAR_AMOUNT')    # 평균 보증금
            },
            
            # 개폐업률
            'business_dynamics': {
                'open_rate': safe_float(row, 'OPBIZ_RT'),    # 개업률
                'close_rate': safe_float(row, 'CLSBIZ_RT')   # 폐업률
            }
        }
    
    def _parse_dong_xml(self, xml_text: str) -> Optional[Dict]:
        """행정동 XML 데이터 파싱"""
        try:
            root = ET.fromstring(xml_text)
            
            # 에러 체크
            if root.find('.//CODE') is not None:
                code = root.find('.//CODE').text
                if code != 'INFO-000':
                    return None
            
            # 첫 번째 row 데이터 추출
            row = root.find('.//row')
            if row is not None:
                return self._extract_dong_data(row)
            
            return None
            
        except Exception as e:
            logger.error(f"행정동 XML 파싱 실패: {e}")
            return None
    
    def _extract_dong_data(self, row: ET.Element) -> Dict:
        """행정동 데이터 추출"""
        def safe_int(elem, tag, default=0):
            try:
                node = elem.find(tag)
                if node is not None and node.text:
                    return int(float(node.text))
            except:
                pass
            return default
        
        return {
            'dong_code': row.find('ADSTRD_CD').text if row.find('ADSTRD_CD') is not None else '',
            'dong_name': row.find('ADSTRD_CD_NM').text if row.find('ADSTRD_CD_NM') is not None else '',
            
            # 업종별 실제 평균 결제 단가
            'avg_payment_per_use': {
                'food': safe_int(row, 'FD_USE_UNIT_AMT'),       # 음식점 건당 평균
                'retail': safe_int(row, 'RETL_USE_UNIT_AMT'),   # 소매 건당 평균
                'service': safe_int(row, 'SERV_USE_UNIT_AMT'),  # 서비스 건당 평균
                'cafe': safe_int(row, 'CAFE_USE_UNIT_AMT'),     # 카페 건당 평균
                'pub': safe_int(row, 'PUB_USE_UNIT_AMT')        # 주점 건당 평균
            },
            
            # 업종별 실제 이용 건수
            'usage_count': {
                'food': safe_int(row, 'FD_USE_CNT'),
                'retail': safe_int(row, 'RETL_USE_CNT'),
                'service': safe_int(row, 'SERV_USE_CNT'),
                'cafe': safe_int(row, 'CAFE_USE_CNT'),
                'pub': safe_int(row, 'PUB_USE_CNT')
            },
            
            # 시간대별 매출 비중
            'sales_by_time': {
                'morning': safe_int(row, 'TMZON_06_11_SELNG_RT'),   # 오전
                'lunch': safe_int(row, 'TMZON_11_14_SELNG_RT'),     # 점심
                'afternoon': safe_int(row, 'TMZON_14_17_SELNG_RT'), # 오후
                'evening': safe_int(row, 'TMZON_17_21_SELNG_RT'),   # 저녁
                'night': safe_int(row, 'TMZON_21_24_SELNG_RT')      # 밤
            },
            
            # 요일별 매출 비중
            'sales_by_day': {
                'weekday': safe_int(row, 'WKDAY_SELNG_RT'),
                'weekend': safe_int(row, 'WKEND_SELNG_RT')
            }
        }
    
    def calculate_realistic_metrics(self, area_name: str, business_type: str) -> Dict:
        """실제 데이터 기반 창업 지표 계산"""
        commercial_data = self.get_commercial_area_data(area_name)
        dong_data = self.get_dong_commercial_data(area_name)
        
        if not commercial_data:
            logger.warning(f"상권 데이터 없음: {area_name}")
            return {}
        
        # 업종 매핑
        business_mapping = {
            '카페': 'cafe',
            '음식점': 'food',
            '편의점': 'retail',
            '주점': 'pub',
            '미용실': 'service',
            '학원': 'service',
            '약국': 'retail',
            '헬스장': 'service'
        }
        
        mapped_type = business_mapping.get(business_type, 'service')
        
        # 1. 실제 일평균 유동인구
        daily_floating = commercial_data['floating_population']['total'] / 30
        
        # 2. 실제 평균 결제 단가 (행정동 데이터 우선)
        if dong_data and mapped_type in dong_data['avg_payment_per_use']:
            avg_payment = dong_data['avg_payment_per_use'][mapped_type]
        else:
            # 상권 전체 매출 / 점포수 / 일수로 추정
            if commercial_data['sales_data']['store_count'] > 0:
                monthly_sales = commercial_data['sales_data'].get(f'{mapped_type}_sales', 
                                                                 commercial_data['sales_data']['monthly_sales'])
                avg_payment = monthly_sales / commercial_data['sales_data']['store_count'] / 30 / 50  # 일 50건 가정
            else:
                avg_payment = 10000  # 기본값
        
        # 3. 실제 전환율 계산 (해당 업종 이용건수 / 유동인구)
        if dong_data and mapped_type in dong_data['usage_count']:
            monthly_usage = dong_data['usage_count'][mapped_type]
            daily_usage = monthly_usage / 30
            conversion_rate = daily_usage / daily_floating if daily_floating > 0 else 0.02
        else:
            conversion_rate = 0.025  # 기본 전환율 2.5%
        
        # 4. 경쟁 강도 (해당 업종 점포수)
        if mapped_type == 'food':
            competitor_count = commercial_data['sales_data']['food_stores']
        elif mapped_type in ['retail', 'cafe']:
            competitor_count = commercial_data['sales_data']['retail_stores']
        else:
            competitor_count = commercial_data['sales_data']['service_stores']
        
        # 5. 예상 일 고객수 (실제 데이터 기반)
        expected_daily_customers = int(daily_floating * conversion_rate / max(1, competitor_count))
        
        # 6. 예상 월 매출 (실제 단가 × 고객수 × 영업일)
        operating_days = 28 if business_type in ['음식점', '미용실'] else 30
        expected_monthly_revenue = expected_daily_customers * avg_payment * operating_days
        
        # 7. 실제 임대료
        monthly_rent = commercial_data['rent_data']['avg_rent']
        deposit = commercial_data['rent_data']['avg_deposit']
        
        # 8. 손익분기점 계산 (실제 데이터 기반)
        # 고정비 = 임대료 + 인건비 + 기타
        fixed_cost = monthly_rent + (3000000 if business_type in ['카페', '음식점'] else 2000000)  # 인건비
        # 변동비율 (원가율)
        variable_rate = {
            '카페': 0.35,
            '음식점': 0.40,
            '편의점': 0.75,
            '주점': 0.45,
            '미용실': 0.20,
            '학원': 0.30,
            '약국': 0.70,
            '헬스장': 0.20
        }.get(business_type, 0.40)
        
        # 손익분기 매출
        break_even_revenue = fixed_cost / (1 - variable_rate)
        months_to_break_even = int(deposit / 10000000 / ((expected_monthly_revenue - break_even_revenue) / expected_monthly_revenue) if expected_monthly_revenue > break_even_revenue else 999)
        
        return {
            'daily_floating_population': int(daily_floating),
            'conversion_rate': conversion_rate,
            'avg_payment_per_customer': int(avg_payment),
            'competitor_count': competitor_count,
            'expected_daily_customers': expected_daily_customers,
            'expected_monthly_revenue': int(expected_monthly_revenue),
            'monthly_rent': monthly_rent,
            'deposit': deposit,
            'break_even_revenue': int(break_even_revenue),
            'months_to_break_even': months_to_break_even,
            'open_rate': commercial_data['business_dynamics']['open_rate'],
            'close_rate': commercial_data['business_dynamics']['close_rate'],
            
            # 시간대별 최적 운영 시간 (실제 데이터)
            'peak_hours': self._get_peak_hours(commercial_data, dong_data),
            
            # 타겟 고객 분석 (실제 데이터)
            'target_analysis': self._analyze_target_customers(commercial_data, business_type)
        }
    
    def _get_peak_hours(self, commercial_data: Dict, dong_data: Optional[Dict]) -> List[str]:
        """실제 데이터 기반 피크 시간대 분석"""
        time_slots = {
            'time_06_11': '오전 (06-11시)',
            'time_11_14': '점심 (11-14시)',
            'time_14_17': '오후 (14-17시)',
            'time_17_21': '저녁 (17-21시)',
            'time_21_24': '밤 (21-24시)'
        }
        
        # 유동인구 기반 정렬
        floating_by_time = []
        for key, label in time_slots.items():
            if key in commercial_data['floating_population']:
                count = commercial_data['floating_population'][key]
                floating_by_time.append((label, count))
        
        # 상위 2개 시간대 반환
        floating_by_time.sort(key=lambda x: x[1], reverse=True)
        return [time[0] for time in floating_by_time[:2]]
    
    def _analyze_target_customers(self, commercial_data: Dict, business_type: str) -> Dict:
        """실제 데이터 기반 타겟 고객 분석"""
        pop_data = commercial_data['floating_population']
        
        # 성별 분석
        total = pop_data['total']
        male_ratio = (pop_data['male'] / total * 100) if total > 0 else 50
        female_ratio = (pop_data['female'] / total * 100) if total > 0 else 50
        
        # 연령대 분석
        age_distribution = {
            '10대': pop_data['age_10'],
            '20대': pop_data['age_20'],
            '30대': pop_data['age_30'],
            '40대': pop_data['age_40'],
            '50대': pop_data['age_50'],
            '60대+': pop_data['age_60']
        }
        
        # 최다 연령층 찾기
        max_age = max(age_distribution.items(), key=lambda x: x[1])
        
        # 상주인구 분석
        resident_data = commercial_data['resident_population']
        worker_ratio = (resident_data['worker'] / resident_data['total'] * 100) if resident_data['total'] > 0 else 0
        
        return {
            'primary_gender': '남성' if male_ratio > 55 else '여성' if female_ratio > 55 else '균등',
            'gender_ratio': {'male': male_ratio, 'female': female_ratio},
            'primary_age': max_age[0],
            'age_distribution': age_distribution,
            'worker_ratio': worker_ratio,
            'customer_type': '직장인' if worker_ratio > 60 else '주민' if worker_ratio < 30 else '혼합'
        }


# 사용 예시
if __name__ == "__main__":
    client = CommercialAnalysisAPIClient()
    
    # 강남역 카페 창업 분석
    metrics = client.calculate_realistic_metrics('강남역', '카페')
    
    if metrics:
        print("=== 강남역 카페 창업 실제 데이터 분석 ===")
        print(f"일평균 유동인구: {metrics['daily_floating_population']:,}명")
        print(f"실제 전환율: {metrics['conversion_rate']:.2%}")
        print(f"평균 객단가: {metrics['avg_payment_per_customer']:,}원")
        print(f"경쟁 매장수: {metrics['competitor_count']}개")
        print(f"예상 일 고객: {metrics['expected_daily_customers']:,}명")
        print(f"예상 월 매출: {metrics['expected_monthly_revenue']:,}원")
        print(f"월 임대료: {metrics['monthly_rent']:,}원")
        print(f"손익분기점: {metrics['months_to_break_even']}개월")
        print(f"개업률: {metrics['open_rate']:.1f}%")
        print(f"폐업률: {metrics['close_rate']:.1f}%")
