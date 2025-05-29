#!/usr/bin/env python3
"""
임대료 데이터 수집 및 활용 개선을 위한 수정 코드
"""

class EnhancedDataCollector:
    """향상된 데이터 수집기 - 수정된 임대료 데이터 처리"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://openapi.seoul.go.kr:8088"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 캐시
        self.sales_cache = {}
        self.rent_cache = {}
        self.rent_data_loaded = False
        
        # 서울시 상가 임대료 API 서비스명들 (여러 개 시도)
        self.rent_api_services = [
            "tbLnOpendataRentV",      # 부동산 전월세가 정보
            "IndividuallyRun",        # 개별공시지가
            "LAND_PRICE",             # 토지가격
            "commRentPrice",          # 상업용부동산 임대시세
            "officetelRent",          # 오피스텔 전월세
            "TbGtnSgguCommercialBldgRent"  # 서울시 자치구별 상가건물 임대료
        ]
    
    def fetch_rent_data(self) -> Dict:
        """서울시 부동산 임대료 정보 수집 - 개선된 버전"""
        if self.rent_data_loaded:
            return self.rent_cache
            
        logger.info("부동산 임대료 데이터 수집 시작...")
        rent_data = {}
        
        # 여러 API 서비스 시도
        for service_name in self.rent_api_services:
            logger.info(f"API 서비스 시도: {service_name}")
            
            # 먼저 1건만 조회해서 API 상태 확인
            test_url = f"{self.base_url}/{self.api_key}/json/{service_name}/1/1/"
            
            try:
                test_response = self.session.get(test_url, timeout=10)
                if test_response.status_code == 200:
                    test_data = test_response.json()
                    
                    # API가 정상적으로 응답하는지 확인
                    if 'RESULT' in test_data:
                        code = test_data['RESULT'].get('CODE', '')
                        if code == 'INFO-000':  # 정상
                            logger.info(f"{service_name} API 사용 가능")
                            
                            # 실제 데이터 수집
                            rent_data = self._fetch_rent_from_service(service_name)
                            if rent_data:
                                logger.info(f"{service_name}에서 {len(rent_data)}개 지역 데이터 수집 성공")
                                break
                        else:
                            logger.debug(f"{service_name} API 응답: {code}")
                            
            except Exception as e:
                logger.debug(f"{service_name} API 오류: {e}")
                continue
        
        # 데이터가 없으면 기본값 생성
        if not rent_data:
            logger.warning("임대료 API 데이터를 가져올 수 없음 - 기본값 사용")
            rent_data = self._generate_default_rent_data()
        
        self.rent_cache = rent_data
        self.rent_data_loaded = True
        return rent_data
    
    def _fetch_rent_from_service(self, service_name: str) -> Dict:
        """특정 서비스에서 임대료 데이터 수집"""
        rent_data = {}
        
        # 더 많은 데이터 수집 (1000건)
        url = f"{self.base_url}/{self.api_key}/json/{service_name}/1/1000/"
        
        try:
            response = self.session.get(url, timeout=60)
            if response.status_code == 200:
                data = response.json()
                
                # 서비스별로 다른 데이터 구조 처리
                if service_name in data and 'row' in data[service_name]:
                    rows = data[service_name]['row']
                    
                    for row in rows:
                        # 각 API 서비스별 필드명이 다를 수 있음
                        area_name = self._extract_area_name(row, service_name)
                        rent_info = self._extract_rent_info(row, service_name)
                        
                        if area_name and rent_info:
                            if area_name not in rent_data:
                                rent_data[area_name] = []
                            rent_data[area_name].append(rent_info)
                    
        except Exception as e:
            logger.error(f"{service_name} 데이터 수집 오류: {e}")
        
        return rent_data
    
    def _extract_area_name(self, row: Dict, service_name: str) -> Optional[str]:
        """API 서비스별로 지역명 추출"""
        # 가능한 주소 필드명들
        address_fields = ['ADRES', 'ADDRESS', 'ADDR', 'LOC', 'LOCATION', 
                         'SGG_NM', 'DONG_NM', 'ADSTRD_NM', 'AREA_NM']
        
        for field in address_fields:
            if field in row and row[field]:
                address = row[field]
                # 주소에서 동 이름 추출
                if '동' in address:
                    parts = address.split()
                    for part in parts:
                        if '동' in part:
                            return part
                elif '역' in address:
                    parts = address.split()
                    for part in parts:
                        if '역' in part:
                            return part
                else:
                    # 구 단위 데이터인 경우
                    return address.split()[0] if address else None
        
        return None
    
    def _extract_rent_info(self, row: Dict, service_name: str) -> Optional[Dict]:
        """API 서비스별로 임대료 정보 추출"""
        rent_info = {}
        
        # 가능한 임대료 필드명들
        rent_fields = ['RENT_FEE', 'MONTHLY_RENT', 'RENT_AMT', 'RENT_PRICE', 'MNTH_RENT']
        deposit_fields = ['RENT_GTN', 'DEPOSIT', 'GTN_AMT', 'GUARANTEE']
        area_fields = ['RENT_AREA', 'AREA', 'BLDG_AREA', 'EXCLUSIVE_AREA']
        
        # 월 임대료
        for field in rent_fields:
            if field in row:
                try:
                    rent_info['monthly_rent'] = int(float(row[field] or 0))
                    break
                except:
                    pass
        
        # 보증금
        for field in deposit_fields:
            if field in row:
                try:
                    rent_info['deposit'] = int(float(row[field] or 0))
                    break
                except:
                    pass
        
        # 면적
        for field in area_fields:
            if field in row:
                try:
                    rent_info['area'] = float(row[field] or 0)
                    break
                except:
                    pass
        
        # 기타 정보
        rent_info['rent_type'] = row.get('RENT_SE', row.get('RENT_TYPE', '월세'))
        rent_info['floor'] = row.get('FLOR_NO', row.get('FLOOR', ''))
        rent_info['contract_date'] = row.get('CNTRCT_DE', row.get('CONTRACT_DATE', ''))
        
        # 최소한 월 임대료나 보증금이 있어야 유효한 데이터
        if rent_info.get('monthly_rent', 0) > 0 or rent_info.get('deposit', 0) > 0:
            return rent_info
        
        return None
    
    def _generate_default_rent_data(self) -> Dict:
        """기본 임대료 데이터 생성 (API 실패 시)"""
        # 서울 주요 상권별 추정 임대료 (평당 기준)
        default_rents = {
            '강남역': {'avg_monthly_rent': 15000000, 'avg_deposit': 150000000},
            '홍대입구역': {'avg_monthly_rent': 8000000, 'avg_deposit': 80000000},
            '명동': {'avg_monthly_rent': 12000000, 'avg_deposit': 120000000},
            '신촌역': {'avg_monthly_rent': 6000000, 'avg_deposit': 60000000},
            '종로': {'avg_monthly_rent': 7000000, 'avg_deposit': 70000000},
            '이태원역': {'avg_monthly_rent': 7500000, 'avg_deposit': 75000000},
            '건대입구역': {'avg_monthly_rent': 5500000, 'avg_deposit': 55000000},
            '성수역': {'avg_monthly_rent': 6500000, 'avg_deposit': 65000000},
            '을지로입구역': {'avg_monthly_rent': 8500000, 'avg_deposit': 85000000},
            '신사역': {'avg_monthly_rent': 9000000, 'avg_deposit': 90000000},
            # 추가 지역들...
        }
        
        # 기본값 형식으로 변환
        rent_data = {}
        for area, values in default_rents.items():
            rent_data[area] = [{
                'rent_type': '월세',
                'deposit': values['avg_deposit'],
                'monthly_rent': values['avg_monthly_rent'],
                'area': 50.0,  # 기본 면적
                'floor': '1층',
                'contract_date': '2025-01'
            }]
        
        return rent_data
    
    def get_area_rent_info(self, area_name: str) -> Dict:
        """특정 지역의 평균 임대료 정보 - 개선된 버전"""
        if not self.rent_data_loaded:
            self.fetch_rent_data()
        
        # 기본값
        default_info = {
            'avg_deposit': 0, 
            'avg_monthly_rent': 0, 
            'sample_count': 0,
            'min_rent': 0,
            'max_rent': 0,
            'median_rent': 0
        }
        
        if not self.rent_cache:
            return default_info
        
        # 지역명 변형 시도
        area_variations = [area_name]
        if '역' in area_name:
            area_variations.append(area_name.replace('역', ''))
            area_variations.append(area_name.replace('역', '') + '동')
        if '동' not in area_name:
            area_variations.append(area_name + '동')
        
        # 근처 지역도 포함 (예: 강남역 -> 강남, 역삼 등)
        if '역' in area_name:
            base_name = area_name.replace('역', '')
            area_variations.extend([
                base_name + '1동', base_name + '2동', 
                base_name + '3동', base_name + '4동'
            ])
        
        all_rents = []
        
        for area in area_variations:
            if area in self.rent_cache:
                area_rents = self.rent_cache[area]
                
                # 월세 데이터 수집
                monthly_rents = [r for r in area_rents 
                               if r.get('rent_type', '') == '월세' and r.get('monthly_rent', 0) > 0]
                
                all_rents.extend(monthly_rents)
        
        if all_rents:
            # 통계 계산
            rent_values = [r['monthly_rent'] for r in all_rents]
            deposit_values = [r['deposit'] for r in all_rents]
            
            return {
                'avg_deposit': sum(deposit_values) / len(deposit_values),
                'avg_monthly_rent': sum(rent_values) / len(rent_values),
                'sample_count': len(all_rents),
                'min_rent': min(rent_values),
                'max_rent': max(rent_values),
                'median_rent': sorted(rent_values)[len(rent_values)//2]
            }
        
        # 데이터가 없으면 주변 지역 평균으로 추정
        return self._estimate_rent_from_nearby(area_name)
    
    def _estimate_rent_from_nearby(self, area_name: str) -> Dict:
        """주변 지역 데이터로 임대료 추정"""
        # 지역별 임대료 수준 (상/중/하)
        high_rent_areas = ['강남', '서초', '송파', '용산']
        mid_rent_areas = ['마포', '영등포', '성동', '광진']
        low_rent_areas = ['은평', '도봉', '강북', '금천']
        
        # 기본 추정값
        if any(area in area_name for area in high_rent_areas):
            return {
                'avg_deposit': 100000000,
                'avg_monthly_rent': 10000000,
                'sample_count': 0,
                'min_rent': 8000000,
                'max_rent': 12000000,
                'median_rent': 10000000
            }
        elif any(area in area_name for area in mid_rent_areas):
            return {
                'avg_deposit': 60000000,
                'avg_monthly_rent': 6000000,
                'sample_count': 0,
                'min_rent': 4000000,
                'max_rent': 8000000,
                'median_rent': 6000000
            }
        else:
            return {
                'avg_deposit': 40000000,
                'avg_monthly_rent': 4000000,
                'sample_count': 0,
                'min_rent': 3000000,
                'max_rent': 5000000,
                'median_rent': 4000000
            }


# MultiCriteriaOptimizer 클래스의 _calculate_objectives 메서드 수정
def _calculate_objectives_improved(self, locations: List[Dict], constraints: StartupConstraints) -> List[LocationScore]:
    """3개 목적함수 계산 - 임대료 활용 강화"""
    scored_locations = []
    
    for loc in locations:
        pop_data = loc['population']
        com_data = loc['commercial']
        
        # 업종별 매출 데이터
        sales_data = self.enhanced_collector.get_area_sales_info(
            loc['area_name'], constraints.business_type
        )
        loc['sales'] = sales_data
        
        # 임대료 데이터 (개선된 버전 사용)
        rent_data = loc.get('rent', {})
        
        scores = LocationScore(area_name=loc['area_name'])
        
        # ... (기존 점수 계산 로직) ...
        
        # 9. 임대료 적정성 점수 - 개선된 계산
        if rent_data.get('avg_monthly_rent', 0) > 0:
            avg_rent = rent_data['avg_monthly_rent']
            
            # 예상 매출 대비 임대료 비율
            if scores.estimated_sales > 0:
                rent_ratio = (avg_rent / scores.estimated_sales) * 100
                
                # 업종별 적정 임대료 비율
                ideal_rent_ratios = {
                    '카페': 12,
                    '음식점': 10,
                    '주점': 8,
                    '편의점': 15,
                    '학원': 20,
                    '미용실': 15,
                    '약국': 12,
                    '헬스장': 18
                }
                
                ideal_ratio = ideal_rent_ratios.get(constraints.business_type, 12)
                
                # 적정 비율에서 벗어날수록 점수 감소
                if rent_ratio <= ideal_ratio:
                    scores.rent_score = 100
                elif rent_ratio <= ideal_ratio * 1.5:
                    scores.rent_score = 100 - (rent_ratio - ideal_ratio) * 2
                else:
                    scores.rent_score = max(0, 70 - (rent_ratio - ideal_ratio * 1.5))
            else:
                # 매출 데이터가 없으면 절대 금액으로 평가
                if avg_rent <= 5000000:
                    scores.rent_score = 90
                elif avg_rent <= 10000000:
                    scores.rent_score = 70
                elif avg_rent <= 15000000:
                    scores.rent_score = 50
                else:
                    scores.rent_score = 30
            
            # 샘플 수가 적으면 신뢰도 감소
            if rent_data.get('sample_count', 0) < 3:
                scores.rent_score *= 0.8
        else:
            scores.rent_score = 50  # 데이터 없음
        
        # 목적함수 계산 - 임대료 가중치 증가
        # 수익성 = 유동인구 + 결제활성도 + 타겟매칭 + 추정매출
        if scores.estimated_sales > 0:
            sales_score = min(100, (scores.estimated_sales / 100000000) * 100)
            scores.profitability = (
                0.25 * scores.population_score +
                0.25 * scores.payment_activity_score +
                0.25 * scores.target_match_score +
                0.25 * sales_score
            )
        else:
            scores.profitability = (
                0.35 * scores.population_score +
                0.35 * scores.payment_activity_score +
                0.30 * scores.target_match_score
            )
        
        # 안정성 = 적정경쟁 + 예산적합도 + 임대료적정성 (가중치 조정)
        scores.stability = (
            0.3 * scores.competition_score +
            0.3 * scores.budget_fit_score +
            0.4 * scores.rent_score  # 임대료 가중치 증가
        )
        
        # 접근성 = 비거주민비율 + 상권레벨
        scores.accessibility = (
            0.6 * scores.non_resident_ratio +
            0.4 * scores.commercial_level_score
        )
        
        scores.raw_data = loc
        scored_locations.append(scores)
    
    return scored_locations