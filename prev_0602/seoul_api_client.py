# # 서울 주요 상권 데이터 처리 
# import requests
# import json
# import time
# import logging
# from typing import Dict, List, Optional, Union
# from urllib.parse import quote

# # 로깅 설정
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# class Config:
#     """설정 클래스"""
#     # API 설정
#     API_KEY = "51504b7a6861646b35314b797a7771"
#     BASE_URL = "http://openapi.seoul.go.kr:8088"
#     REQUEST_TIMEOUT = 30
#     MAX_RETRIES = 3
    
#     # 서울시 주요 지역 - 82개 공식 지역명 (API 지원 확인됨)
#     AVAILABLE_AREAS = [
#         "강남 MICE 관광특구", "동대문 관광특구", "명동 관광특구", "이태원 관광특구", 
#         "잠실 관광특구", "종로·청계 관광특구", "홍대 관광특구", "광화문·덕수궁", 
#         "보신각", "가산디지털단지역", "강남역", "건대입구역", "고덕역", "고속터미널역", 
#         "교대역", "구로디지털단지역", "구로역", "군자역", "대림역", "동대문역", 
#         "뚝섬역", "미아사거리역", "발산역", "사당역", "서울대입구역", 
#         "서울식물원·마곡나루역", "서울역", "선릉역", "성신여대입구역", "수유역", 
#         "신논현역·논현역", "신도림역", "신림역", "신촌·이대역", "양재역", 
#         "역삼역", "연신내역", "오목교역·목동운동장", "왕십리역", "용산역", 
#         "이태원역", "장지역", "장한평역", "천호역", "총신대입구(이수)역", 
#         "충정로역", "합정역", "혜화역", "홍대입구역(2호선)", "회기역", 
#         "가락시장", "가로수길", "광장(전통)시장", "김포공항", "노량진", 
#         "덕수궁길·정동길", "북촌한옥마을", "서촌", "성수카페거리", "쌍문역", 
#         "압구정로데오거리", "여의도", "연남동", "영등포 타임스퀘어", "용리단길", 
#         "이태원 앤틱가구거리", "인사동", "창동 신경제 중심지", "청담동 명품거리", 
#         "청량리 제기동 일대 전통시장", "해방촌·경리단길", "DDP(동대문디자인플라자)", 
#         "DMC(디지털미디어시티)", "북창동 먹자골목", "남대문시장", "익선동", 
#         "신정네거리역", "잠실새내역", "잠실역", "잠실롯데타워 일대", 
#         "송리단길·호수단길", "신촌 스타광장"
#     ]
    
#     # 테스트용 주요 지역 (실제 API 지원 확인된 정확한 명칭)
#     TEST_AREAS = [
#         "광화문·덕수궁",      # POI009
#         "명동 관광특구",      # POI003 (명동X, 정확한 명칭 사용)
#         "홍대 관광특구",      # POI007
#         "강남역",            # POI014
#         "잠실 관광특구"       # POI005
#     ]

# class SeoulDataAPIClient:
#     """서울시 열린데이터광장 API 클라이언트 - 디버깅 강화 버전"""
    
#     def __init__(self, api_key: str = None):
#         self.api_key = api_key or Config.API_KEY
#         self.base_url = Config.BASE_URL
#         self.timeout = Config.REQUEST_TIMEOUT
#         self.max_retries = Config.MAX_RETRIES
        
#         # 세션 생성
#         self.session = requests.Session()
#         self.session.headers.update({
#             'User-Agent': 'Seoul-Startup-Location-Recommender/1.0'
#         })
    
#     def debug_api_response(self, url: str) -> Optional[Dict]:
#         """API 응답 구조 디버깅"""
#         try:
#             print(f"\n🔍 API URL 디버깅: {url}")
            
#             response = self.session.get(url, timeout=self.timeout)
#             print(f"📡 HTTP 상태 코드: {response.status_code}")
#             print(f"📋 응답 헤더: {dict(response.headers)}")
            
#             # 응답 내용 출력 (처음 1000자만)
#             response_text = response.text
#             print(f"📄 응답 내용 (처음 1000자):")
#             print("-" * 50)
#             print(response_text[:1000])
#             print("-" * 50)
            
#             # JSON 파싱 시도
#             try:
#                 data = response.json()
#                 print(f"✅ JSON 파싱 성공")
#                 print(f"📊 응답 데이터 구조:")
#                 self._print_dict_structure(data, max_depth=3)
#                 return data
#             except json.JSONDecodeError as e:
#                 print(f"❌ JSON 파싱 실패: {e}")
#                 return None
                
#         except Exception as e:
#             print(f"❌ 디버깅 중 오류 발생: {e}")
#             return None
    
#     def _print_dict_structure(self, data: dict, indent: int = 0, max_depth: int = 3) -> None:
#         """딕셔너리 구조를 트리 형태로 출력"""
#         if indent > max_depth:
#             return
            
#         for key, value in data.items():
#             spaces = "  " * indent
#             if isinstance(value, dict):
#                 print(f"{spaces}📁 {key}: (dict with {len(value)} keys)")
#                 if indent < max_depth:
#                     self._print_dict_structure(value, indent + 1, max_depth)
#             elif isinstance(value, list):
#                 print(f"{spaces}📋 {key}: (list with {len(value)} items)")
#                 if value and indent < max_depth:
#                     print(f"{spaces}  └─ 첫 번째 항목 타입: {type(value[0])}")
#                     if isinstance(value[0], dict):
#                         self._print_dict_structure(value[0], indent + 2, max_depth)
#             else:
#                 value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
#                 print(f"{spaces}📄 {key}: {value_str}")
    
#     def _make_request(self, url: str, max_retries: int = None) -> Optional[Dict]:
#         """안전한 API 요청 수행 - 디버깅 강화"""
#         max_retries = max_retries or self.max_retries
        
#         for attempt in range(max_retries):
#             try:
#                 logger.info(f"API 요청 시도 {attempt + 1}/{max_retries}: {url}")
                
#                 response = self.session.get(url, timeout=self.timeout)
                
#                 # 상태 코드 체크
#                 if response.status_code != 200:
#                     logger.warning(f"HTTP 에러: {response.status_code}")
#                     continue
                
#                 # JSON 파싱
#                 try:
#                     data = response.json()
#                 except json.JSONDecodeError as e:
#                     logger.warning(f"JSON 파싱 실패: {e}")
#                     logger.warning(f"응답 내용: {response.text[:500]}")
#                     continue
                
#                 # API 응답 상태 체크 (더 유연하게)
#                 if self._check_api_response_flexible(data):
#                     logger.info(f"API 요청 성공")
#                     return data
#                 else:
#                     logger.warning(f"API 응답 에러 또는 데이터 없음")
#                     # 디버깅을 위해 무조건 데이터 반환
#                     return data
                    
#             except requests.exceptions.Timeout:
#                 logger.warning(f"API 요청 타임아웃 (시도 {attempt + 1}/{max_retries})")
#             except requests.exceptions.RequestException as e:
#                 logger.warning(f"API 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            
#             # 재시도 전 대기
#             if attempt < max_retries - 1:
#                 wait_time = 2 ** attempt
#                 logger.info(f"{wait_time}초 후 재시도...")
#                 time.sleep(wait_time)
        
#         logger.error(f"모든 재시도 실패: {url}")
#         return None
    
#     def _check_api_response_flexible(self, data: Dict) -> bool:
#         """API 응답 상태 확인 - 더 유연한 버전"""
#         if not data:
#             return False
        
#         # 여러 가능한 응답 구조 확인
#         result = data.get('RESULT', {})
        
#         # 기본 응답 구조 확인
#         if result:
#             code = result.get('CODE', '') or result.get('resultCode', '')
#             message = result.get('MESSAGE', '') or result.get('resultMsg', '')
            
#             if code == 'INFO-000':
#                 return True
#             elif code == 'INFO-200':
#                 logger.info("요청 데이터가 없습니다")
#                 return False
#             else:
#                 logger.warning(f"API 결과: 코드={code}, 메시지={message}")
        
#         # 실제 데이터가 있는지 확인
#         has_population_data = 'SeoulRtd.citydata_ppltn' in data
#         has_commercial_data = 'LIVE_CMRCL_STTS' in data  # 수정된 부분
        
#         if has_population_data or has_commercial_data:
#             logger.info("데이터가 포함된 응답 확인")
#             return True
        
#         # 다른 가능한 키들 확인
#         logger.info(f"응답에 포함된 키들: {list(data.keys())}")
#         return True  # 디버깅을 위해 항상 True 반환
    
#     def get_population_data(self, area_name: str) -> Optional[Dict]:
#         """실시간 인구 현황 데이터 조회"""
#         encoded_area = quote(area_name.encode('utf-8'))
#         url = f"{self.base_url}/{self.api_key}/json/citydata_ppltn/1/5/{encoded_area}"
        
#         raw_data = self._make_request(url)
#         if not raw_data:
#             return None
        
#         # 데이터 추출 시도
#         try:
#             # 인구 데이터는 SeoulRtd.citydata_ppltn 키에 있음
#             population_list = raw_data.get('SeoulRtd.citydata_ppltn')
            
#             if not population_list:
#                 logger.warning(f"인구 데이터를 찾을 수 없음. 사용 가능한 키: {list(raw_data.keys())}")
#                 return None
            
#             if isinstance(population_list, list) and len(population_list) > 0:
#                 return self._process_population_data(population_list[0])
#             else:
#                 logger.warning(f"예상치 못한 데이터 형태: {type(population_list)}")
#                 return None
                
#         except Exception as e:
#             logger.error(f"인구 데이터 파싱 실패: {e}")
#             return None
    
#     def get_commercial_data(self, area_name: str) -> Optional[Dict]:
#         """실시간 상권 현황 데이터 조회"""
#         encoded_area = quote(area_name.encode('utf-8'))
#         url = f"{self.base_url}/{self.api_key}/json/citydata_cmrcl/1/5/{encoded_area}"
        
#         raw_data = self._make_request(url)
#         if not raw_data:
#             return None
        
#         # 데이터 추출 시도
#         try:
#             # 상권 데이터는 최상위 레벨에 바로 있음
#             commercial_data = raw_data.get('LIVE_CMRCL_STTS')
            
#             if commercial_data:
#                 # LIVE_CMRCL_STTS 데이터와 최상위 레벨 데이터 병합
#                 merged_data = commercial_data.copy()
#                 merged_data['AREA_NM'] = raw_data.get('AREA_NM', '')
#                 merged_data['AREA_CD'] = raw_data.get('AREA_CD', '')
                
#                 logger.info(f"상권 데이터를 'LIVE_CMRCL_STTS' 키에서 발견")
#                 return self._process_commercial_data(merged_data)
#             else:
#                 logger.warning(f"상권 데이터를 찾을 수 없음. 사용 가능한 키: {list(raw_data.keys())}")
#                 return None
                
#         except Exception as e:
#             logger.error(f"상권 데이터 파싱 실패: {e}")
#             return None
    
#     def _process_population_data(self, raw_data: Dict) -> Dict:
#         """인구 데이터 전처리 - 더 안전한 버전"""
#         def safe_float(value, default=0.0):
#             try:
#                 if value is None or value == '':
#                     return default
#                 return float(value)
#             except (ValueError, TypeError):
#                 return default
        
#         def safe_int(value, default=0):
#             try:
#                 if value is None or value == '':
#                     return default
#                 return int(float(value))  # float로 먼저 변환 후 int
#             except (ValueError, TypeError):
#                 return default
        
#         # 가능한 모든 키를 확인하여 매핑
#         processed = {
#             'area_name': raw_data.get('AREA_NM', ''),
#             'area_code': raw_data.get('AREA_CD', ''),
#             'congestion_level': raw_data.get('AREA_CONGEST_LVL', ''),
#             'congestion_message': raw_data.get('AREA_CONGEST_MSG', ''),
#             'population_min': safe_int(raw_data.get('AREA_PPLTN_MIN')),
#             'population_max': safe_int(raw_data.get('AREA_PPLTN_MAX')),
#             'age_distribution': {
#                 '0-10': safe_float(raw_data.get('PPLTN_RATE_0')),
#                 '10s': safe_float(raw_data.get('PPLTN_RATE_10')),
#                 '20s': safe_float(raw_data.get('PPLTN_RATE_20')),
#                 '30s': safe_float(raw_data.get('PPLTN_RATE_30')),
#                 '40s': safe_float(raw_data.get('PPLTN_RATE_40')),
#                 '50s': safe_float(raw_data.get('PPLTN_RATE_50')),
#                 '60s': safe_float(raw_data.get('PPLTN_RATE_60')),
#                 '70s': safe_float(raw_data.get('PPLTN_RATE_70'))
#             },
#             'gender_distribution': {
#                 'male': safe_float(raw_data.get('MALE_PPLTN_RATE')),
#                 'female': safe_float(raw_data.get('FEMALE_PPLTN_RATE'))
#             },
#             'resident_ratio': safe_float(raw_data.get('RESNT_PPLTN_RATE')),
#             'non_resident_ratio': safe_float(raw_data.get('NON_RESNT_PPLTN_RATE')),
#             'update_time': raw_data.get('PPLTN_TIME', ''),
#             'forecast_available': (raw_data.get('FCST_YN', 'N')) == 'Y',
#             'raw_data_keys': list(raw_data.keys())[:10]  # 디버깅용 (처음 10개만)
#         }
        
#         # 예측 데이터가 있으면 추가
#         if processed['forecast_available'] and 'FCST_PPLTN' in raw_data:
#             processed['forecast_data'] = raw_data['FCST_PPLTN']
        
#         return processed
    
#     def _process_commercial_data(self, raw_data: Dict) -> Dict:
#         """상권 데이터 전처리 - 더 안전한 버전"""
#         def safe_float(value, default=0.0):
#             try:
#                 if value is None or value == '':
#                     return default
#                 return float(value)
#             except (ValueError, TypeError):
#                 return default
        
#         def safe_int(value, default=0):
#             try:
#                 if value is None or value == '':
#                     return default
#                 # 문자열인 경우 처리
#                 if isinstance(value, str):
#                     value = value.replace(',', '')  # 천 단위 구분자 제거
#                 return int(float(value))
#             except (ValueError, TypeError):
#                 return default
        
#         processed = {
#             'area_name': raw_data.get('AREA_NM', ''),
#             'area_code': raw_data.get('AREA_CD', ''),
#             'area_commercial_level': raw_data.get('AREA_CMRCL_LVL', ''),
#             'area_payment_count': safe_int(raw_data.get('AREA_SH_PAYMENT_CNT')),
#             'area_payment_amount': {
#                 'min': safe_int(raw_data.get('AREA_SH_PAYMENT_AMT_MIN')),
#                 'max': safe_int(raw_data.get('AREA_SH_PAYMENT_AMT_MAX'))
#             },
#             'consumer_demographics': {
#                 'gender': {
#                     'male': safe_float(raw_data.get('CMRCL_MALE_RATE')),
#                     'female': safe_float(raw_data.get('CMRCL_FEMALE_RATE'))
#                 },
#                 'age': {
#                     '10s': safe_float(raw_data.get('CMRCL_10_RATE')),
#                     '20s': safe_float(raw_data.get('CMRCL_20_RATE')),
#                     '30s': safe_float(raw_data.get('CMRCL_30_RATE')),
#                     '40s': safe_float(raw_data.get('CMRCL_40_RATE')),
#                     '50s': safe_float(raw_data.get('CMRCL_50_RATE')),
#                     '60s': safe_float(raw_data.get('CMRCL_60_RATE'))
#                 },
#                 'type': {
#                     'personal': safe_float(raw_data.get('CMRCL_PERSONAL_RATE')),
#                     'corporation': safe_float(raw_data.get('CMRCL_CORPORATION_RATE'))
#                 }
#             },
#             'update_time': raw_data.get('CMRCL_TIME', ''),
#             'raw_data_keys': list(raw_data.keys())[:10]  # 디버깅용 (처음 10개만)
#         }
        
#         # 업종별 상세 정보가 있으면 추가
#         if 'CMRCL_RSB' in raw_data:
#             processed['business_categories'] = []
#             for biz in raw_data['CMRCL_RSB']:
#                 processed['business_categories'].append({
#                     'large_category': biz.get('RSB_LRG_CTGR', ''),
#                     'mid_category': biz.get('RSB_MID_CTGR', ''),
#                     'payment_level': biz.get('RSB_PAYMENT_LVL', ''),
#                     'payment_count': safe_int(biz.get('RSB_SH_PAYMENT_CNT')),
#                     'payment_amount_min': safe_int(biz.get('RSB_SH_PAYMENT_AMT_MIN')),
#                     'payment_amount_max': safe_int(biz.get('RSB_SH_PAYMENT_AMT_MAX')),
#                     'merchant_count': safe_int(biz.get('RSB_MCT_CNT'))
#                 })
        
#         return processed
    
# ### 여기서부터 다시 추가 
#     # [1] API 오류 처리 강화 (fallback과 retry 포함)
#     def handle_api_errors(self, url, max_retries=3):
#         for attempt in range(max_retries):
#             try:
#                 response = self.session.get(url, timeout=self.timeout)
#                 response.raise_for_status()
#                 data = response.json()

#                 result_code = data.get('RESULT', {}).get('CODE', '')
#                 if result_code == 'INFO-000':
#                     return data
#                 elif result_code == 'INFO-200':  # 데이터가 없음
#                     logger.warning(f"No data available: {url}")
#                     return None
#                 else:
#                     logger.warning(f"API error {result_code}, retrying...")

#             except requests.RequestException as e:
#                 logger.error(f"Request error: {e}, retrying...")

#             time.sleep(2 ** attempt)
#         logger.error(f"All retries failed for {url}")
#         return None


#     # [2] 데이터 안정성 (이동평균을 이용한 이상치 보정)
#     def smooth_population_data(self, population_values, window=3):
#         smoothed_values = population_values.copy()
#         if len(population_values) >= window:
#             rolling_mean = pd.Series(population_values).rolling(window=window, min_periods=1).mean().tolist()
#             smoothed_values = rolling_mean
#         return smoothed_values


#     # [3] AHP 기반 종합 점수 계산
#     def calculate_score(self, commercial_data, population_data, weights=None):
#         if weights is None:
#             weights = [0.4, 0.3, 0.2, 0.1]  # 기본 가중치 [상권활성도, 인구매칭도, 경쟁강도, 성장잠재력]

#         commercial_score = commercial_data.get('area_payment_count', 0)
#         population_score = (population_data.get('population_min', 0) + population_data.get('population_max', 0)) / 2
#         competition_score = sum(biz['merchant_count'] for biz in commercial_data.get('business_categories', []))
#         growth_potential = population_data.get('forecast_available', False) * 100

#         scores = np.array([commercial_score, population_score, -competition_score, growth_potential])
#         normalized_scores = scores / np.linalg.norm(scores)

#         final_score = np.dot(normalized_scores, weights)

#         return final_score


#     # [4] 상권-인구 데이터 융합 (다변량 선형회귀 활용)
#     def integrate_population_commercial(self, commercial_data, population_data, regression_model=None):
#         if regression_model is None:
#             regression_model = LinearRegression()

#         X = np.array([
#             population_data['age_distribution']['20s'],
#             population_data['age_distribution']['30s'],
#             population_data['gender_distribution']['male'],
#             population_data['non_resident_ratio']
#         ]).reshape(1, -1)

#         y = commercial_data.get('area_payment_amount', {}).get('max', 0)

#         regression_model.fit(X, [y])

#         predicted_y = regression_model.predict(X)[0]

#         commercial_data['predicted_payment_amount'] = predicted_y

#         return commercial_data


#     # [5] 예측 정확도 개선 (Prophet 기반)
#     def improve_forecast_accuracy(self, forecast_data):
#         df = pd.DataFrame([{
#             'ds': pd.to_datetime(forecast['FCST_TIME']),
#             'y': (int(forecast['FCST_PPLTN_MIN']) + int(forecast['FCST_PPLTN_MAX'])) / 2
#         } for forecast in forecast_data])

#         model = Prophet(daily_seasonality=True, weekly_seasonality=True)
#         model.fit(df)

#         future = model.make_future_dataframe(periods=3, freq='H')
#         forecast_result = model.predict(future)

#         return forecast_result[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].to_dict(orient='records')


# def main():
#     """디버깅 메인 함수"""
#     print("=" * 60)
#     print("🔍 서울시 API 디버깅 클라이언트")
#     print("=" * 60)
    
#     client = SeoulDataAPIClient()
    
#     # 1. 기본 연결 및 응답 구조 확인
#     print("\n🔍 API 응답 구조 분석")
#     print("-" * 40)
    
#     # Config에서 테스트 지역 가져오기
#     test_areas = Config.TEST_AREAS
    
#     for area in test_areas:
#         print(f"\n📍 {area} 테스트")
#         print("=" * 30)
        
#         # 인구 데이터 디버깅
#         print("\n👥 인구 데이터 API 디버깅:")
#         encoded_area = quote(area.encode('utf-8'))
#         population_url = f"{client.base_url}/{client.api_key}/json/citydata_ppltn/1/5/{encoded_area}"
#         population_debug = client.debug_api_response(population_url)
        
#         if population_debug:
#             population_data = client.get_population_data(area)
#             if population_data:
#                 print(f"✅ 인구 데이터 처리 성공: {area}")
#                 print(f"   📊 인구: {population_data['population_min']:,}~{population_data['population_max']:,}")
#                 print(f"   🚦 혼잡도: {population_data['congestion_level']}")
#                 print(f"   ⏰ 업데이트: {population_data['update_time']}")
#                 print(f"   👥 연령대별 분포:")
#                 for age, rate in population_data['age_distribution'].items():
#                     if rate > 0:
#                         print(f"      {age}: {rate}%")
#             else:
#                 print(f"❌ 인구 데이터 처리 실패: {area}")
        
#         # 상권 데이터 디버깅
#         print(f"\n🏪 상권 데이터 API 디버깅:")
#         commercial_url = f"{client.base_url}/{client.api_key}/json/citydata_cmrcl/1/5/{encoded_area}"
#         commercial_debug = client.debug_api_response(commercial_url)
        
#         if commercial_debug:
#             commercial_data = client.get_commercial_data(area)
#             if commercial_data:
#                 print(f"✅ 상권 데이터 처리 성공: {area}")
#                 print(f"   📈 상권레벨: {commercial_data['area_commercial_level']}")
#                 print(f"   💳 결제건수: {commercial_data['area_payment_count']:,}")
#                 print(f"   💰 결제금액: {commercial_data['area_payment_amount']['min']:,}~{commercial_data['area_payment_amount']['max']:,}")
#                 print(f"   ⏰ 업데이트: {commercial_data['update_time']}")
                
#                 if 'business_categories' in commercial_data:
#                     print(f"   🏢 업종별 현황 (상위 3개):")
#                     for i, biz in enumerate(commercial_data['business_categories'][:3]):
#                         print(f"      {i+1}. {biz['large_category']} - {biz['mid_category']}: {biz['payment_level']} ({biz['payment_count']:,}건)")
#             else:
#                 print(f"❌ 상권 데이터 처리 실패: {area}")
        
#         print("\n" + "-" * 40)

# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
"""
서울시 열린데이터광장 API 클라이언트
- 실시간 인구 현황 데이터
- 실시간 상권 현황 데이터
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional, Union
from urllib.parse import quote

# 로깅 설정
logger = logging.getLogger(__name__)


class Config:
    """설정 클래스"""
    # API 설정
    API_KEY = "51504b7a6861646b35314b797a7771"
    BASE_URL = "http://openapi.seoul.go.kr:8088"
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    
    # 서울시 주요 지역 - 82개 공식 지역명 (API 지원 확인됨)
    AVAILABLE_AREAS = [
        "강남 MICE 관광특구", "동대문 관광특구", "명동 관광특구", "이태원 관광특구", 
        "잠실 관광특구", "종로·청계 관광특구", "홍대 관광특구", "광화문·덕수궁", 
        "보신각", "가산디지털단지역", "강남역", "건대입구역", "고덕역", "고속터미널역", 
        "교대역", "구로디지털단지역", "구로역", "군자역", "대림역", "동대문역", 
        "뚝섬역", "미아사거리역", "발산역", "사당역", "서울대입구역", 
        "서울식물원·마곡나루역", "서울역", "선릉역", "성신여대입구역", "수유역", 
        "신논현역·논현역", "신도림역", "신림역", "신촌·이대역", "양재역", 
        "역삼역", "연신내역", "오목교역·목동운동장", "왕십리역", "용산역", 
        "이태원역", "장지역", "장한평역", "천호역", "총신대입구(이수)역", 
        "충정로역", "합정역", "혜화역", "홍대입구역(2호선)", "회기역", 
        "가락시장", "가로수길", "광장(전통)시장", "김포공항", "노량진", 
        "덕수궁길·정동길", "북촌한옥마을", "서촌", "성수카페거리", "쌍문역", 
        "압구정로데오거리", "여의도", "연남동", "영등포 타임스퀘어", "용리단길", 
        "이태원 앤틱가구거리", "인사동", "창동 신경제 중심지", "청담동 명품거리", 
        "청량리 제기동 일대 전통시장", "해방촌·경리단길", "DDP(동대문디자인플라자)", 
        "DMC(디지털미디어시티)", "북창동 먹자골목", "남대문시장", "익선동", 
        "신정네거리역", "잠실새내역", "잠실역", "잠실롯데타워 일대", 
        "송리단길·호수단길", "신촌 스타광장"
    ]
    
    # 테스트용 주요 지역 (실제 API 지원 확인된 정확한 명칭)
    TEST_AREAS = [
        "광화문·덕수궁",      # POI009
        "명동 관광특구",      # POI003
        "홍대 관광특구",      # POI007
        "강남역",            # POI014
        "잠실 관광특구"       # POI005
    ]


class SeoulDataAPIClient:
    """서울시 열린데이터광장 API 클라이언트"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.API_KEY
        self.base_url = Config.BASE_URL
        self.timeout = Config.REQUEST_TIMEOUT
        self.max_retries = Config.MAX_RETRIES
        
        # 세션 생성
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def _make_request(self, url: str, max_retries: int = None) -> Optional[Dict]:
        """안전한 API 요청 수행"""
        max_retries = max_retries or self.max_retries
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"API 요청 시도 {attempt + 1}/{max_retries}: {url}")
                
                response = self.session.get(url, timeout=60)  # 타임아웃 증가
                
                # 상태 코드 체크
                if response.status_code != 200:
                    logger.warning(f"HTTP 에러: {response.status_code}")
                    logger.warning(f"응답: {response.text[:200]}")
                    continue
                
                # JSON 파싱
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 파싱 실패: {e}")
                    logger.warning(f"응답 텍스트: {response.text[:200]}")
                    continue
                
                # 성공적으로 데이터를 받았으면 반환
                return data
                    
            except requests.exceptions.Timeout:
                logger.warning(f"API 요청 타임아웃 (시도 {attempt + 1}/{max_retries})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"연결 오류 (시도 {attempt + 1}/{max_retries})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"API 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            
            # 재시도 전 대기
            if attempt < max_retries - 1:
                wait_time = min(5, 2 ** attempt)  # 최대 5초
                logger.info(f"{wait_time}초 후 재시도...")
                time.sleep(wait_time)
        
        logger.error(f"모든 재시도 실패: {url}")
        return None
    
    def _check_api_response(self, data: Dict) -> bool:
        """API 응답 상태 확인"""
        if not data:
            return False
        
        # 에러 응답 체크
        if 'RESULT' in data:
            result = data['RESULT']
            code = result.get('CODE', '')
            message = result.get('MESSAGE', '')
            
            if code == 'INFO-000':
                return True
            elif code == 'INFO-200':
                logger.info(f"데이터 없음: {message}")
                return False
            elif code:
                logger.warning(f"API 에러: {code} - {message}")
                return False
        
        # 실제 데이터가 있는지 확인
        has_population_data = 'SeoulRtd.citydata_ppltn' in data
        has_commercial_data = 'LIVE_CMRCL_STTS' in data
        
        if has_population_data or has_commercial_data:
            return True
        
        # citydata_ppltn 형태로도 체크 (다른 응답 형식)
        if 'citydata_ppltn' in data:
            return True
        
        # 데이터 구조 로깅
        logger.debug(f"응답 키: {list(data.keys())[:5]}")  # 처음 5개 키만
        return True
    
    def get_population_data(self, area_name: str) -> Optional[Dict]:
        """실시간 인구 현황 데이터 조회"""
        encoded_area = quote(area_name.encode('utf-8'))
        url = f"{self.base_url}/{self.api_key}/json/citydata_ppltn/1/5/{encoded_area}"
        
        logger.debug(f"인구 API 호출: {area_name}")
        raw_data = self._make_request(url)
        
        if not raw_data:
            logger.warning(f"인구 데이터 없음: {area_name}")
            return None
        
        # 데이터 추출 시도
        try:
            # 여러 가능한 키 확인
            population_data = None
            
            # 1. SeoulRtd.citydata_ppltn 형태
            if 'SeoulRtd.citydata_ppltn' in raw_data:
                population_list = raw_data['SeoulRtd.citydata_ppltn']
                if isinstance(population_list, list) and len(population_list) > 0:
                    population_data = population_list[0]
            
            # 2. citydata_ppltn 형태
            elif 'citydata_ppltn' in raw_data:
                if 'row' in raw_data['citydata_ppltn']:
                    rows = raw_data['citydata_ppltn']['row']
                    if isinstance(rows, list) and len(rows) > 0:
                        population_data = rows[0]
            
            # 3. 직접 데이터가 있는 경우
            elif 'AREA_NM' in raw_data:
                population_data = raw_data
            
            if population_data:
                return self._process_population_data(population_data)
            else:
                logger.warning(f"인구 데이터 형식 인식 실패. 키: {list(raw_data.keys())}")
                return None
                
        except Exception as e:
            logger.error(f"인구 데이터 파싱 실패 ({area_name}): {e}", exc_info=True)
            return None
    
    def get_commercial_data(self, area_name: str) -> Optional[Dict]:
        """실시간 상권 현황 데이터 조회"""
        encoded_area = quote(area_name.encode('utf-8'))
        url = f"{self.base_url}/{self.api_key}/json/citydata_cmrcl/1/5/{encoded_area}"
        
        logger.debug(f"상권 API 호출: {area_name}")
        raw_data = self._make_request(url)
        
        if not raw_data:
            logger.warning(f"상권 데이터 없음: {area_name}")
            return None
        
        # 데이터 추출 시도
        try:
            commercial_data = None
            
            # 1. LIVE_CMRCL_STTS 키로 접근
            if 'LIVE_CMRCL_STTS' in raw_data:
                commercial_data = raw_data['LIVE_CMRCL_STTS'].copy()
                commercial_data['AREA_NM'] = raw_data.get('AREA_NM', area_name)
                commercial_data['AREA_CD'] = raw_data.get('AREA_CD', '')
            
            # 2. citydata_cmrcl 형태
            elif 'citydata_cmrcl' in raw_data:
                if 'row' in raw_data['citydata_cmrcl']:
                    rows = raw_data['citydata_cmrcl']['row']
                    if isinstance(rows, list) and len(rows) > 0:
                        commercial_data = rows[0]
            
            # 3. 직접 데이터가 있는 경우
            elif 'AREA_CMRCL_LVL' in raw_data:
                commercial_data = raw_data
            
            if commercial_data:
                return self._process_commercial_data(commercial_data)
            else:
                logger.warning(f"상권 데이터 형식 인식 실패. 키: {list(raw_data.keys())}")
                return None
                
        except Exception as e:
            logger.error(f"상권 데이터 파싱 실패 ({area_name}): {e}", exc_info=True)
            return None
    
    def _process_population_data(self, raw_data: Dict) -> Dict:
        """인구 데이터 전처리"""
        def safe_float(value, default=0.0):
            try:
                if value is None or value == '':
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            try:
                if value is None or value == '':
                    return default
                return int(float(value))  # float로 먼저 변환 후 int
            except (ValueError, TypeError):
                return default
        
        processed = {
            'area_name': raw_data.get('AREA_NM', ''),
            'area_code': raw_data.get('AREA_CD', ''),
            'congestion_level': raw_data.get('AREA_CONGEST_LVL', ''),
            'congestion_message': raw_data.get('AREA_CONGEST_MSG', ''),
            'population_min': safe_int(raw_data.get('AREA_PPLTN_MIN')),
            'population_max': safe_int(raw_data.get('AREA_PPLTN_MAX')),
            'age_distribution': {
                '0-10': safe_float(raw_data.get('PPLTN_RATE_0')),
                '10s': safe_float(raw_data.get('PPLTN_RATE_10')),
                '20s': safe_float(raw_data.get('PPLTN_RATE_20')),
                '30s': safe_float(raw_data.get('PPLTN_RATE_30')),
                '40s': safe_float(raw_data.get('PPLTN_RATE_40')),
                '50s': safe_float(raw_data.get('PPLTN_RATE_50')),
                '60s': safe_float(raw_data.get('PPLTN_RATE_60')),
                '70s': safe_float(raw_data.get('PPLTN_RATE_70'))
            },
            'gender_distribution': {
                'male': safe_float(raw_data.get('MALE_PPLTN_RATE')),
                'female': safe_float(raw_data.get('FEMALE_PPLTN_RATE'))
            },
            'resident_ratio': safe_float(raw_data.get('RESNT_PPLTN_RATE')),
            'non_resident_ratio': safe_float(raw_data.get('NON_RESNT_PPLTN_RATE')),
            'update_time': raw_data.get('PPLTN_TIME', ''),
            'forecast_available': (raw_data.get('FCST_YN', 'N')) == 'Y'
        }
        
        # 예측 데이터가 있으면 추가
        if processed['forecast_available'] and 'FCST_PPLTN' in raw_data:
            processed['forecast_data'] = raw_data['FCST_PPLTN']
        
        return processed
    
    def _process_commercial_data(self, raw_data: Dict) -> Dict:
        """상권 데이터 전처리"""
        def safe_float(value, default=0.0):
            try:
                if value is None or value == '':
                    return default
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            try:
                if value is None or value == '':
                    return default
                # 문자열인 경우 처리
                if isinstance(value, str):
                    value = value.replace(',', '')  # 천 단위 구분자 제거
                return int(float(value))
            except (ValueError, TypeError):
                return default
        
        processed = {
            'area_name': raw_data.get('AREA_NM', ''),
            'area_code': raw_data.get('AREA_CD', ''),
            'area_commercial_level': raw_data.get('AREA_CMRCL_LVL', ''),
            'area_payment_count': safe_int(raw_data.get('AREA_SH_PAYMENT_CNT')),
            'area_payment_amount': {
                'min': safe_int(raw_data.get('AREA_SH_PAYMENT_AMT_MIN')),
                'max': safe_int(raw_data.get('AREA_SH_PAYMENT_AMT_MAX'))
            },
            'consumer_demographics': {
                'gender': {
                    'male': safe_float(raw_data.get('CMRCL_MALE_RATE')),
                    'female': safe_float(raw_data.get('CMRCL_FEMALE_RATE'))
                },
                'age': {
                    '10s': safe_float(raw_data.get('CMRCL_10_RATE')),
                    '20s': safe_float(raw_data.get('CMRCL_20_RATE')),
                    '30s': safe_float(raw_data.get('CMRCL_30_RATE')),
                    '40s': safe_float(raw_data.get('CMRCL_40_RATE')),
                    '50s': safe_float(raw_data.get('CMRCL_50_RATE')),
                    '60s': safe_float(raw_data.get('CMRCL_60_RATE'))
                },
                'type': {
                    'personal': safe_float(raw_data.get('CMRCL_PERSONAL_RATE')),
                    'corporation': safe_float(raw_data.get('CMRCL_CORPORATION_RATE'))
                }
            },
            'update_time': raw_data.get('CMRCL_TIME', ''),
            'business_categories': []
        }
        
        # 업종별 상세 정보가 있으면 추가
        if 'CMRCL_RSB' in raw_data:
            for biz in raw_data['CMRCL_RSB']:
                processed['business_categories'].append({
                    'large_category': biz.get('RSB_LRG_CTGR', ''),
                    'mid_category': biz.get('RSB_MID_CTGR', ''),
                    'payment_level': biz.get('RSB_PAYMENT_LVL', ''),
                    'payment_count': safe_int(biz.get('RSB_SH_PAYMENT_CNT')),
                    'payment_amount_min': safe_int(biz.get('RSB_SH_PAYMENT_AMT_MIN')),
                    'payment_amount_max': safe_int(biz.get('RSB_SH_PAYMENT_AMT_MAX')),
                    'merchant_count': safe_int(biz.get('RSB_MCT_CNT'))
                })
        
        return processed


def main():
    """테스트용 메인 함수"""
    print("=" * 60)
    print("🔍 서울시 API 클라이언트 테스트")
    print("=" * 60)
    
    client = SeoulDataAPIClient()
    
    # Config에서 테스트 지역 가져오기
    test_areas = Config.TEST_AREAS[:2]  # 처음 2개만 테스트
    
    for area in test_areas:
        print(f"\n📍 {area} 테스트")
        print("=" * 30)
        
        # 인구 데이터 테스트
        print("\n👥 인구 데이터:")
        population_data = client.get_population_data(area)
        if population_data:
            print(f"✅ 성공")
            print(f"   - 인구: {population_data['population_min']:,}~{population_data['population_max']:,}")
            print(f"   - 혼잡도: {population_data['congestion_level']}")
            print(f"   - 업데이트: {population_data['update_time']}")
        else:
            print(f"❌ 실패")
        
        # 상권 데이터 테스트
        print(f"\n🏪 상권 데이터:")
        commercial_data = client.get_commercial_data(area)
        if commercial_data:
            print(f"✅ 성공")
            print(f"   - 상권레벨: {commercial_data['area_commercial_level']}")
            print(f"   - 결제건수: {commercial_data['area_payment_count']:,}")
            print(f"   - 업데이트: {commercial_data['update_time']}")
            
            if commercial_data['business_categories']:
                print(f"   - 업종수: {len(commercial_data['business_categories'])}개")
        else:
            print(f"❌ 실패")
        
        print("\n" + "-" * 40)


if __name__ == "__main__":
    main()