"""
카페 창업 입지 추천 시스템 (Seoul Cafe Location Optimizer)

Maximum Flow 알고리즘과 파레토 최적화를 활용한 서울시 카페 입지 분석 시스템
- 서울시 공공데이터를 활용한 데이터 기반 의사결정 지원
- 다목적 최적화를 통한 균형잡힌 입지 추천
- 사용자 맞춤형 필터링 시스템

Author: Seoul Data Analysis Team
Version: 2.0
Last Updated: 2024-12
"""

import pandas as pd
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import warnings
import os
import glob
import logging
from enum import Enum

# 경고 무시
warnings.filterwarnings('ignore')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Enums ====================

class GenderTarget(Enum):
    """성별 타겟 고객 유형"""
    FEMALE_CENTERED = "여성 중심"
    MALE_CENTERED = "남성 중심"
    BALANCED = "균형"
    ANY = "상관없음"


class CompetitionLevel(Enum):
    """경쟁 수준"""
    BLUE_OCEAN = "블루오션"
    MODERATE = "적당한 경쟁"
    COMPETITIVE = "경쟁 활발"
    ANY = "상관없음"


class SubwayPreference(Enum):
    """지하철 접근성 선호도"""
    REQUIRED = "필수"
    PREFERRED = "선호"
    ANY = "상관없음"


class PeakTime(Enum):
    """주력 영업 시간대"""
    MORNING = "출근"
    LUNCH = "점심"
    AFTERNOON = "오후"
    EVENING = "저녁"
    BALANCED = "균형"


class WeekdayPreference(Enum):
    """주중/주말 선호도"""
    WEEKDAY = "주중"
    WEEKEND = "주말"
    BALANCED = "균형"


class PriceRange(Enum):
    """객단가 수준"""
    LOW = "저가"
    MID_LOW = "중저가"
    MID = "중가"
    MID_HIGH = "중고가"
    HIGH = "고가"
    ANY = "상관없음"


# ==================== Data Classes ====================

@dataclass
class Config:
    """시스템 설정 관리 클래스"""
    # 서비스 코드
    CAFE_SERVICE_CODE: str = 'CS100010'
    
    # 데이터 설정
    DONG_CODE_LENGTH: int = 10
    DEFAULT_MIN_REVENUE: int = 2000  # 만원 단위
    DEFAULT_MAX_REVENUE: int = 50000  # 만원 단위
    DEFAULT_TOP_N: int = 5
    DEFAULT_MIN_STORES: int = 3
    
    # 가중치 설정
    weights: Dict[str, float] = field(default_factory=lambda: {
        '수익성': 0.3,
        '안정성': 0.2,
        '접근성': 0.15,
        '효율성': 0.15,
        '출근시간효율': 0.1,
        '주중비율': 0.1
    })
    
    # 파일 인코딩 옵션
    encodings: List[str] = field(default_factory=lambda: [
        'utf-8', 'utf-8-sig', 'cp949', 'euc-kr'
    ])
    
    # 컬럼명 매핑
    column_mappings: Dict[str, List[str]] = field(default_factory=lambda: {
        'dong_code': ['행정동코드', '행정동_코드', 'admdong_cd', 'dong_code'],
        'revenue': ['당월_매출_금액', '매출_금액', '매출액'],
        'sales_count': ['당월_매출_건수', '매출_건수', '매출건수'],
        'store_count': ['점포_수', '점포수', 'store_count'],
        'service_code': ['서비스_업종_코드', '서비스업종코드', 'service_code'],
        'subway_count': ['지하철_승객_수', '지하철승객수', '승객수', '승차인원'],
        'open_rate': ['개업_율', '개업률', 'open_rate'],
        'close_rate': ['폐업_률', '폐업률', 'close_rate'],
        'franchise': ['프랜차이즈_점포_수', '프랜차이즈점포수', 'franchise_count']
    })
    
    # 필터 기준값
    filter_criteria: Dict[str, Dict[str, Union[int, float]]] = field(default_factory=lambda: {
        'competition': {
            'blue_ocean': (0, 10),
            'moderate': (11, 30),
            'competitive': (31, 50)
        },
        'price_range': {
            'low': (0, 5000),
            'mid_low': (5001, 8000),
            'mid': (8001, 12000),
            'mid_high': (12001, 15000),
            'high': (15001, float('inf'))
        },
        'time_ratio': {
            'significant': 0.2  # 주력 시간대 최소 비율
        },
        'gender_ratio': {
            'female_centered': 0.6,
            'male_centered': 0.4,
            'balanced': (0.4, 0.6)
        },
        'weekday_ratio': {
            'weekday': 0.7,
            'weekend': 0.5
        }
    })


@dataclass
class DongInfo:
    """행정동 정보"""
    code: str
    name: str
    gu_name: str
    si_name: str
    
    def __str__(self) -> str:
        return f"{self.name} ({self.gu_name})"


@dataclass
class SalesData:
    """매출 데이터"""
    revenue: float
    sales_count: float
    avg_price: float
    female_revenue: float = 0
    male_revenue: float = 0
    weekday_revenue: float = 0
    weekend_revenue: float = 0
    morning_revenue: float = 0  # 06-11시
    lunch_revenue: float = 0    # 11-14시
    afternoon_revenue: float = 0  # 14-17시
    evening_revenue: float = 0   # 17-21시
    night_revenue: float = 0     # 21-24시
    
    @property
    def female_ratio(self) -> float:
        """여성 매출 비율"""
        total = self.female_revenue + self.male_revenue
        return self.female_revenue / total if total > 0 else 0.5
    
    @property
    def weekday_ratio(self) -> float:
        """주중 매출 비율"""
        total = self.weekday_revenue + self.weekend_revenue
        return self.weekday_revenue / total if total > 0 else 0.7
    
    def get_time_ratio(self, time_slot: str) -> float:
        """특정 시간대 매출 비율"""
        if self.revenue == 0:
            return 0
        
        time_revenues = {
            'morning': self.morning_revenue,
            'lunch': self.lunch_revenue,
            'afternoon': self.afternoon_revenue,
            'evening': self.evening_revenue,
            'night': self.night_revenue
        }
        
        return time_revenues.get(time_slot, 0) / self.revenue


@dataclass
class StoreData:
    """점포 데이터"""
    store_count: int
    open_rate: float
    close_rate: float
    franchise_count: int = 0
    
    @property
    def stability_score(self) -> float:
        """안정성 점수 계산"""
        if self.store_count == 0:
            return 0
        return (1 - self.close_rate) * (1 / (1 + np.log(max(self.store_count, 1))))


@dataclass
class PopulationData:
    """생활인구 데이터"""
    total_population: float
    female_20_50: float
    male_20_50: float
    
    @property
    def target_population(self) -> float:
        """타겟 인구 (20-50대)"""
        return self.female_20_50 + self.male_20_50
    
    @property
    def female_ratio(self) -> float:
        """여성 비율"""
        if self.target_population == 0:
            return 0.5
        return self.female_20_50 / self.target_population


@dataclass
class UserPreferences:
    """사용자 선호도"""
    min_revenue: int = 2000  # 만원 단위
    max_revenue: int = 50000
    gender_target: GenderTarget = GenderTarget.ANY
    competition: CompetitionLevel = CompetitionLevel.ANY
    subway: SubwayPreference = SubwayPreference.ANY
    peak_time: PeakTime = PeakTime.BALANCED
    weekday_preference: WeekdayPreference = WeekdayPreference.BALANCED
    price_range: PriceRange = PriceRange.ANY
    min_stores: int = 3


@dataclass
class RecommendationResult:
    """추천 결과"""
    dong_code: str
    dong_name: str
    gu_name: str
    score: float
    total_revenue: float
    avg_revenue_per_store: float
    total_sales_count: float
    avg_sales_per_store: float
    avg_price: float
    store_count: int
    closure_rate: float
    female_ratio: float
    subway_access: bool
    morning_sales_ratio: float
    weekday_ratio: float
    inflow_population: float
    
    def format_revenue(self, amount: float) -> str:
        """금액을 한국어 형식으로 변환"""
        return f"{amount:,.0f}원 ({format_korean_number(int(amount))})"


# ==================== Utility Functions ====================

def format_korean_number(num: int) -> str:
    """숫자를 한국어로 읽는 형식으로 변환"""
    if num == 0:
        return "0원"
    
    units = ['', '만', '억', '조']
    nums = []
    
    # 음수 처리
    is_negative = num < 0
    num = abs(num)
    
    # 단위별로 분할
    unit_idx = 0
    while num > 0 and unit_idx < len(units):
        part = num % 10000
        if part > 0:
            nums.append(f"{part:,d}{units[unit_idx]}")
        num //= 10000
        unit_idx += 1
    
    # 역순으로 조합
    result = ' '.join(reversed(nums)) + '원'
    
    if is_negative:
        result = '-' + result
    
    return result


# ==================== Abstract Base Classes ====================

class DataLoader(ABC):
    """데이터 로더 추상 클래스"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def load(self, filepath: str) -> Any:
        """데이터 로드 추상 메서드"""
        pass
    
    def _read_csv_with_encoding(self, filepath: str) -> Optional[pd.DataFrame]:
        """여러 인코딩을 시도하여 CSV 파일 읽기"""
        for encoding in self.config.encodings:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                self.logger.info(f"파일 로드 성공: {filepath} (encoding: {encoding})")
                return df
            except Exception as e:
                continue
        
        self.logger.error(f"파일 로드 실패: {filepath}")
        return None
    
    def _find_column(self, df: pd.DataFrame, column_type: str) -> Optional[str]:
        """컬럼명 매핑을 통해 실제 컬럼명 찾기"""
        possible_names = self.config.column_mappings.get(column_type, [])
        for name in possible_names:
            if name in df.columns:
                return name
        return None
    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """안전한 float 변환"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


class BaseOptimizer(ABC):
    """최적화 기본 클래스"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def optimize(self, *args, **kwargs) -> Any:
        """최적화 실행 추상 메서드"""
        pass


# ==================== Data Loaders ====================

class DongMappingLoader(DataLoader):
    """행정동 매핑 데이터 로더"""
    
    def load(self, filepath: str) -> Dict[str, DongInfo]:
        """행정동 매핑 데이터 로드"""
        if not os.path.exists(filepath):
            self.logger.warning(f"행정동 매핑 파일이 없습니다: {filepath}")
            return self._try_alternative_files()
        
        df = self._read_csv_with_encoding(filepath)
        if df is None:
            return {}
        
        return self._process_dong_mapping(df)
    
    def _try_alternative_files(self) -> Dict[str, DongInfo]:
        """대체 파일 시도"""
        alternative_names = ['법행정동매핑.csv', '법정행정동매핑.csv', '행정동매핑.csv']
        
        for name in alternative_names:
            if os.path.exists(name):
                self.logger.info(f"대체 파일 발견: {name}")
                return self.load(name)
        
        return {}
    
    def _process_dong_mapping(self, df: pd.DataFrame) -> Dict[str, DongInfo]:
        """행정동 매핑 처리"""
        dong_mapping = {}
        df.columns = df.columns.str.strip()
        
        dong_col = self._find_column(df, 'dong_code')
        if dong_col is None:
            self.logger.error("행정동 코드 컬럼을 찾을 수 없습니다.")
            return {}
        
        for _, row in df.iterrows():
            dong_code_raw = str(row[dong_col])
            dong_info = DongInfo(
                code=dong_code_raw,
                name=row.get('읍면동명', ''),
                gu_name=row.get('시군구명', ''),
                si_name=row.get('시도명', '')
            )
            
            # 다양한 형태로 저장 (매칭률 향상)
            self._store_multiple_formats(dong_mapping, dong_code_raw, dong_info)
        
        self.logger.info(f"{len(df)}개 행정동 중 {len(dong_mapping)}개 형태로 매핑 완료")
        return dong_mapping
    
    def _store_multiple_formats(self, mapping: Dict, code: str, info: DongInfo) -> None:
        """여러 형태의 코드로 저장"""
        # 원본
        mapping[code] = info
        
        # 10자리 코드인 경우 8자리도 저장
        if len(code) == 10:
            code_8 = code[:8]
            mapping[code_8] = info
            
        # 앞의 0 제거 버전
        mapping[code.lstrip('0')] = info
        
        if len(code) == 10:
            mapping[code[:8].lstrip('0')] = info


class SalesDataLoader(DataLoader):
    """매출 데이터 로더"""
    
    def load(self, filepath: str) -> Dict[str, SalesData]:
        """매출 데이터 로드"""
        if not os.path.exists(filepath):
            self.logger.warning(f"매출 데이터 파일이 없습니다: {filepath}")
            return {}
        
        df = self._read_csv_with_encoding(filepath)
        if df is None:
            return {}
        
        # 카페 데이터만 필터링
        df_filtered = self._filter_cafe_data(df)
        
        # 매출 데이터 처리
        return self._process_sales_data(df_filtered)
    
    def _filter_cafe_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """카페 데이터만 필터링"""
        service_col = self._find_column(df, 'service_code')
        
        if service_col and self.config.CAFE_SERVICE_CODE in df[service_col].values:
            cafe_df = df[df[service_col] == self.config.CAFE_SERVICE_CODE]
            self.logger.info(f"카페 데이터: {len(cafe_df)}개")
            return cafe_df
        else:
            self.logger.warning("카페 서비스 코드를 찾을 수 없어 전체 데이터 사용")
            return df
    
    def _process_sales_data(self, df: pd.DataFrame) -> Dict[str, SalesData]:
        """매출 데이터 처리"""
        sales_data = {}
        
        dong_col = self._find_column(df, 'dong_code')
        revenue_col = self._find_column(df, 'revenue')
        count_col = self._find_column(df, 'sales_count')
        
        if not all([dong_col, revenue_col]):
            self.logger.error("필수 컬럼을 찾을 수 없습니다.")
            return {}
        
        for _, row in df.iterrows():
            dong_code = str(row[dong_col])
            revenue = self._safe_float(row.get(revenue_col, 0))
            
            if revenue > 0:
                sales_data[dong_code] = self._create_sales_data(row, revenue_col, count_col)
        
        self.logger.info(f"{len(sales_data)}개 행정동 매출 데이터 로드 완료")
        self._log_top_sales(sales_data)
        
        return sales_data
    
    def _create_sales_data(self, row: pd.Series, revenue_col: str, count_col: str) -> SalesData:
        """SalesData 객체 생성"""
        revenue = self._safe_float(row.get(revenue_col, 0))
        sales_count = self._safe_float(row.get(count_col, 0))
        
        return SalesData(
            revenue=revenue,
            sales_count=sales_count,
            avg_price=revenue / sales_count if sales_count > 0 else 0,
            female_revenue=self._safe_float(row.get('여성_매출_금액', 0)),
            male_revenue=self._safe_float(row.get('남성_매출_금액', 0)),
            weekday_revenue=self._safe_float(row.get('주중_매출_금액', 0)),
            weekend_revenue=self._safe_float(row.get('주말_매출_금액', 0)),
            morning_revenue=self._safe_float(row.get('시간대_06~11_매출_금액', 0)),
            lunch_revenue=self._safe_float(row.get('시간대_11~14_매출_금액', 0)),
            afternoon_revenue=self._safe_float(row.get('시간대_14~17_매출_금액', 0)),
            evening_revenue=self._safe_float(row.get('시간대_17~21_매출_금액', 0)),
            night_revenue=self._safe_float(row.get('시간대_21~24_매출_금액', 0))
        )
    
    def _log_top_sales(self, sales_data: Dict[str, SalesData], top_n: int = 5) -> None:
        """상위 매출 로그"""
        top_sales = sorted(sales_data.items(), 
                          key=lambda x: x[1].revenue, 
                          reverse=True)[:top_n]
        
        self.logger.info(f"매출 TOP {top_n}:")
        for dong, data in top_sales:
            self.logger.info(f"  {dong}: {format_korean_number(int(data.revenue))}")


class StoreDataLoader(DataLoader):
    """점포 데이터 로더"""
    
    def load(self, filepath: str) -> Dict[str, StoreData]:
        """점포 데이터 로드"""
        if not os.path.exists(filepath):
            self.logger.warning(f"점포 데이터 파일이 없습니다: {filepath}")
            return {}
        
        df = self._read_csv_with_encoding(filepath)
        if df is None:
            return {}
        
        # 카페 데이터만 필터링
        df_filtered = self._filter_cafe_data(df)
        
        # 점포 데이터 처리
        return self._process_store_data(df_filtered)
    
    def _filter_cafe_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """카페 데이터만 필터링"""
        service_col = self._find_column(df, 'service_code')
        
        if service_col and self.config.CAFE_SERVICE_CODE in df[service_col].values:
            cafe_df = df[df[service_col] == self.config.CAFE_SERVICE_CODE]
            self.logger.info(f"카페 점포 데이터: {len(cafe_df)}개")
            return cafe_df
        else:
            self.logger.warning("카페 서비스 코드를 찾을 수 없어 전체 데이터 사용")
            return df
    
    def _process_store_data(self, df: pd.DataFrame) -> Dict[str, StoreData]:
        """점포 데이터 처리"""
        store_data = {}
        
        dong_col = self._find_column(df, 'dong_code')
        if dong_col is None:
            self.logger.error("행정동 코드 컬럼을 찾을 수 없습니다.")
            return {}
        
        for _, row in df.iterrows():
            dong_code = str(row[dong_col])
            store_data[dong_code] = self._create_store_data(row)
        
        self.logger.info(f"{len(store_data)}개 행정동 점포 데이터 로드 완료")
        return store_data
    
    def _create_store_data(self, row: pd.Series) -> StoreData:
        """StoreData 객체 생성"""
        store_count = self._safe_float(self._get_column_value(row, 'store_count'))
        open_rate = self._safe_float(self._get_column_value(row, 'open_rate'))
        close_rate = self._safe_float(self._get_column_value(row, 'close_rate'))
        franchise = self._safe_float(self._get_column_value(row, 'franchise'))
        
        # 퍼센트 처리
        open_rate = open_rate / 100 if open_rate > 1 else open_rate
        close_rate = close_rate / 100 if close_rate > 1 else close_rate
        
        return StoreData(
            store_count=int(store_count),
            open_rate=open_rate,
            close_rate=close_rate,
            franchise_count=int(franchise)
        )
    
    def _get_column_value(self, row: pd.Series, column_type: str) -> Any:
        """컬럼 값 가져오기"""
        possible_names = self.config.column_mappings.get(column_type, [])
        for name in possible_names:
            if name in row.index:
                return row[name]
        return 0


# ==================== Core Components ====================

class NetworkAnalyzer:
    """네트워크 분석기"""
    
    def __init__(self):
        self.flow_network = defaultdict(lambda: defaultdict(int))
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def build_network(self, od_data: pd.DataFrame) -> None:
        """OD 데이터를 기반으로 네트워크 구축"""
        if od_data.empty:
            self.logger.warning("OD 데이터가 없어 기본 네트워크 사용")
            return
        
        valid_count = 0
        skipped_count = 0
        
        for _, row in od_data.iterrows():
            if self._process_od_record(row):
                valid_count += 1
            else:
                skipped_count += 1
        
        self.logger.info(
            f"네트워크 구축 완료: {len(self.flow_network)} 노드, "
            f"{valid_count}개 엣지, {skipped_count}개 스킵"
        )
    
    def _process_od_record(self, row: pd.Series) -> bool:
        """OD 레코드 처리"""
        try:
            origin = str(row.get('o_admdong_cd', '')).strip()
            dest = str(row.get('d_admdong_cd', '')).strip()
            flow = float(row.get('total_cnt', 0))
            
            if origin and dest and origin != dest and flow > 0:
                self.flow_network[origin][dest] += flow
                return True
            
            return False
        except Exception:
            return False
    
    def calculate_inflow(self, dong_code: str) -> float:
        """특정 행정동으로의 총 유입량 계산"""
        return sum(
            self.flow_network[origin][dong_code]
            for origin in self.flow_network
            if dong_code in self.flow_network[origin]
        )
    
    def calculate_outflow(self, dong_code: str) -> float:
        """특정 행정동에서의 총 유출량 계산"""
        if dong_code in self.flow_network:
            return sum(self.flow_network[dong_code].values())
        return 0
    
    def get_top_flows(self, dong_code: str, top_n: int = 3) -> Dict[str, List[Tuple[str, float]]]:
        """상위 유입/유출 경로"""
        inflows = {}
        for origin in self.flow_network:
            if dong_code in self.flow_network[origin]:
                inflows[origin] = self.flow_network[origin][dong_code]
        
        outflows = {}
        if dong_code in self.flow_network:
            outflows = dict(self.flow_network[dong_code])
        
        top_inflows = sorted(inflows.items(), key=lambda x: x[1], reverse=True)[:top_n]
        top_outflows = sorted(outflows.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        return {
            'inflows': top_inflows,
            'outflows': top_outflows
        }


class ObjectiveCalculator:
    """목적함수 계산기"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def calculate(
        self,
        sales_data: Optional[SalesData],
        store_data: Optional[StoreData],
        subway_access: bool,
        network_efficiency: float,
        population_data: Optional[PopulationData] = None
    ) -> Dict[str, float]:
        """다차원 목적함수 계산"""
        objectives = {}
        
        # 1. 수익성 (객단가 기준)
        objectives['수익성'] = sales_data.avg_price if sales_data else 0
        
        # 2. 안정성
        objectives['안정성'] = store_data.stability_score if store_data else 0
        
        # 3. 접근성
        objectives['접근성'] = 1.0 if subway_access else 0.0
        
        # 4. 네트워크 효율성
        objectives['효율성'] = min(network_efficiency, 1.0)  # 정규화
        
        # 5. 시간대 효율성
        if sales_data:
            objectives['출근시간효율'] = sales_data.get_time_ratio('morning')
            objectives['주중비율'] = sales_data.weekday_ratio
        else:
            objectives['출근시간효율'] = 0
            objectives['주중비율'] = 0
        
        return objectives
    
    def normalize(self, all_objectives: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """목적함수 정규화 (Min-Max Normalization)"""
        if not all_objectives:
            return {}
        
        normalized = {}
        objective_names = list(next(iter(all_objectives.values())).keys())
        
        for obj_name in objective_names:
            values = [obj[obj_name] for obj in all_objectives.values()]
            min_val = min(values) if values else 0
            max_val = max(values) if values else 1
            
            for dong, objectives in all_objectives.items():
                if dong not in normalized:
                    normalized[dong] = {}
                
                if max_val > min_val:
                    normalized[dong][obj_name] = (objectives[obj_name] - min_val) / (max_val - min_val)
                else:
                    normalized[dong][obj_name] = 0.5
        
        return normalized


class ParetoOptimizer:
    """파레토 최적화"""
    
    @staticmethod
    def dominates(obj1: Dict[str, float], obj2: Dict[str, float]) -> bool:
        """파레토 지배 관계 확인"""
        better_in_any = False
        
        for key in ['수익성', '안정성', '접근성', '효율성']:
            if key not in obj1 or key not in obj2:
                continue
                
            if obj1[key] < obj2[key]:
                return False
            elif obj1[key] > obj2[key]:
                better_in_any = True
        
        return better_in_any
    
    def find_optimal(self, objectives: Dict[str, Dict[str, float]]) -> List[str]:
        """파레토 최적해 찾기"""
        pareto_optimal = []
        
        for dong1 in objectives:
            is_dominated = False
            
            for dong2 in objectives:
                if dong1 != dong2 and self.dominates(objectives[dong2], objectives[dong1]):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto_optimal.append(dong1)
        
        return pareto_optimal


class FilterManager:
    """필터 관리자"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def apply_filters(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """모든 필터 순차적 적용"""
        filtered = candidates.copy()
        
        # 필터 체인
        filters = [
            ('매출 범위', self._filter_by_revenue),
            ('성별', self._filter_by_gender),
            ('경쟁 환경', self._filter_by_competition),
            ('지하철', self._filter_by_subway),
            ('시간대', self._filter_by_peak_time),
            ('주중/주말', self._filter_by_weekday),
            ('객단가', self._filter_by_price),
            ('최소 점포수', self._filter_by_min_stores)
        ]
        
        for filter_name, filter_func in filters:
            before_count = len(filtered)
            filtered = filter_func(filtered, preferences, data_store)
            after_count = len(filtered)
            
            if before_count != after_count:
                self.logger.info(f"{filter_name} 필터: {before_count} → {after_count}개")
        
        return filtered
    
    def _filter_by_revenue(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """매출 범위 필터"""
        min_revenue_won = preferences.min_revenue * 10_000
        max_revenue_won = preferences.max_revenue * 10_000
        
        return [
            dong for dong in candidates
            if min_revenue_won <= data_store.get_sales_data(dong).revenue <= max_revenue_won
        ]
    
    def _filter_by_gender(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """성별 필터"""
        if preferences.gender_target == GenderTarget.ANY:
            return candidates
        
        filtered = []
        criteria = self.config.filter_criteria['gender_ratio']
        
        for dong in candidates:
            female_ratio = data_store.get_female_ratio(dong)
            
            if preferences.gender_target == GenderTarget.FEMALE_CENTERED:
                if female_ratio >= criteria['female_centered']:
                    filtered.append(dong)
            elif preferences.gender_target == GenderTarget.MALE_CENTERED:
                if female_ratio <= criteria['male_centered']:
                    filtered.append(dong)
            elif preferences.gender_target == GenderTarget.BALANCED:
                min_ratio, max_ratio = criteria['balanced']
                if min_ratio <= female_ratio <= max_ratio:
                    filtered.append(dong)
        
        return filtered if filtered else candidates
    
    def _filter_by_competition(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """경쟁 환경 필터"""
        if preferences.competition == CompetitionLevel.ANY:
            return candidates
        
        filtered = []
        criteria = self.config.filter_criteria['competition']
        
        for dong in candidates:
            store_count = data_store.get_store_count(dong)
            
            if preferences.competition == CompetitionLevel.BLUE_OCEAN:
                min_stores, max_stores = criteria['blue_ocean']
                if min_stores <= store_count <= max_stores:
                    filtered.append(dong)
            elif preferences.competition == CompetitionLevel.MODERATE:
                min_stores, max_stores = criteria['moderate']
                if min_stores <= store_count <= max_stores:
                    filtered.append(dong)
            elif preferences.competition == CompetitionLevel.COMPETITIVE:
                min_stores, max_stores = criteria['competitive']
                if min_stores <= store_count <= max_stores:
                    filtered.append(dong)
        
        return filtered if filtered else candidates
    
    def _filter_by_subway(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """지하철 필터"""
        if preferences.subway == SubwayPreference.REQUIRED:
            return [dong for dong in candidates if data_store.has_subway_access(dong)]
        
        return candidates
    
    def _filter_by_peak_time(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """시간대 필터"""
        if preferences.peak_time == PeakTime.BALANCED:
            return candidates
        
        filtered = []
        min_ratio = self.config.filter_criteria['time_ratio']['significant']
        
        time_mapping = {
            PeakTime.MORNING: 'morning',
            PeakTime.LUNCH: 'lunch',
            PeakTime.AFTERNOON: 'afternoon',
            PeakTime.EVENING: 'evening'
        }
        
        time_slot = time_mapping.get(preferences.peak_time)
        if not time_slot:
            return candidates
        
        for dong in candidates:
            sales_data = data_store.get_sales_data(dong)
            if sales_data and sales_data.get_time_ratio(time_slot) >= min_ratio:
                filtered.append(dong)
        
        return filtered if filtered else candidates
    
    def _filter_by_weekday(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """주중/주말 필터"""
        if preferences.weekday_preference == WeekdayPreference.BALANCED:
            return candidates
        
        filtered = []
        criteria = self.config.filter_criteria['weekday_ratio']
        
        for dong in candidates:
            sales_data = data_store.get_sales_data(dong)
            if not sales_data:
                continue
            
            weekday_ratio = sales_data.weekday_ratio
            
            if preferences.weekday_preference == WeekdayPreference.WEEKDAY:
                if weekday_ratio >= criteria['weekday']:
                    filtered.append(dong)
            elif preferences.weekday_preference == WeekdayPreference.WEEKEND:
                if weekday_ratio <= criteria['weekend']:
                    filtered.append(dong)
        
        return filtered if filtered else candidates
    
    def _filter_by_price(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """객단가 필터"""
        if preferences.price_range == PriceRange.ANY:
            return candidates
        
        filtered = []
        criteria = self.config.filter_criteria['price_range']
        
        price_mapping = {
            PriceRange.LOW: 'low',
            PriceRange.MID_LOW: 'mid_low',
            PriceRange.MID: 'mid',
            PriceRange.MID_HIGH: 'mid_high',
            PriceRange.HIGH: 'high'
        }
        
        price_key = price_mapping.get(preferences.price_range)
        if not price_key:
            return candidates
        
        min_price, max_price = criteria[price_key]
        
        for dong in candidates:
            sales_data = data_store.get_sales_data(dong)
            if sales_data and min_price <= sales_data.avg_price <= max_price:
                filtered.append(dong)
        
        return filtered if filtered else candidates
    
    def _filter_by_min_stores(
        self,
        candidates: List[str],
        preferences: UserPreferences,
        data_store: 'DataStore'
    ) -> List[str]:
        """최소 점포수 필터"""
        return [
            dong for dong in candidates
            if data_store.get_store_count(dong) >= preferences.min_stores
        ]


class DataStore:
    """데이터 저장소 (Repository Pattern)"""
    
    def __init__(self):
        self.dong_mapping: Dict[str, DongInfo] = {}
        self.sales_data: Dict[str, SalesData] = {}
        self.store_data: Dict[str, StoreData] = {}
        self.subway_data: Dict[str, bool] = {}
        self.population_data: Dict[str, PopulationData] = {}
    
    def get_dong_info(self, dong_code: str) -> Optional[DongInfo]:
        """행정동 정보 조회"""
        return self.dong_mapping.get(dong_code)
    
    def get_sales_data(self, dong_code: str) -> Optional[SalesData]:
        """매출 데이터 조회"""
        return self.sales_data.get(dong_code)
    
    def get_store_data(self, dong_code: str) -> Optional[StoreData]:
        """점포 데이터 조회"""
        return self.store_data.get(dong_code)
    
    def get_store_count(self, dong_code: str) -> int:
        """점포수 조회"""
        store_data = self.store_data.get(dong_code)
        return store_data.store_count if store_data else 0
    
    def has_subway_access(self, dong_code: str) -> bool:
        """지하철 접근성 조회"""
        return self.subway_data.get(dong_code, False)
    
    def get_population_data(self, dong_code: str) -> Optional[PopulationData]:
        """생활인구 데이터 조회"""
        return self.population_data.get(dong_code)
    
    def get_female_ratio(self, dong_code: str) -> float:
        """여성 비율 조회 (매출 우선, 인구 차선)"""
        sales_data = self.get_sales_data(dong_code)
        if sales_data and (sales_data.female_revenue + sales_data.male_revenue) > 0:
            return sales_data.female_ratio
        
        pop_data = self.get_population_data(dong_code)
        if pop_data:
            return pop_data.female_ratio
        
        return 0.5


class UserInterface:
    """사용자 인터페이스"""
    
    @staticmethod
    def get_user_preferences() -> UserPreferences:
        """사용자 선호도 입력받기"""
        print("\n" + "="*50)
        print("🎯 카페 창업 선호 조건 설정")
        print("="*50)
        
        preferences = UserPreferences()
        
        # 각 항목별 입력
        preferences.min_revenue = UserInterface._get_revenue_input("최소", 2000)
        preferences.max_revenue = UserInterface._get_revenue_input("최대", 50000)
        preferences.gender_target = UserInterface._get_gender_target()
        preferences.competition = UserInterface._get_competition_level()
        preferences.subway = UserInterface._get_subway_preference()
        preferences.peak_time = UserInterface._get_peak_time()
        preferences.weekday_preference = UserInterface._get_weekday_preference()
        preferences.price_range = UserInterface._get_price_range()
        preferences.min_stores = UserInterface._get_min_stores()
        
        print("\n" + "="*50)
        print("✅ 선호 조건 설정 완료!")
        print("="*50)
        
        return preferences
    
    @staticmethod
    def _get_revenue_input(label: str, default: int) -> int:
        """매출 입력"""
        while True:
            try:
                value = input(f"\n💰 {label} 희망 월매출 (만원 단위, 기본값 {default}): ")
                return int(value) if value else default
            except ValueError:
                print("   ❌ 숫자를 입력해주세요.")
    
    @staticmethod
    def _get_gender_target() -> GenderTarget:
        """성별 타겟 입력"""
        print("\n👥 타겟 고객 성별:")
        options = list(GenderTarget)
        for i, option in enumerate(options, 1):
            print(f"   {i}. {option.value}")
        
        while True:
            choice = input(f"선택 (1-{len(options)}, 기본값 {len(options)}): ")
            try:
                if not choice:
                    return GenderTarget.ANY
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print(f"   ❌ 1-{len(options)} 중에서 선택해주세요.")
    
    @staticmethod
    def _get_competition_level() -> CompetitionLevel:
        """경쟁 수준 입력"""
        print("\n🏪 선호하는 경쟁 환경:")
        print("   1. 블루오션 (카페 10개 이하)")
        print("   2. 적당한 경쟁 (카페 11-30개)")
        print("   3. 경쟁 활발 (카페 31-50개)")
        print("   4. 상관없음")
        
        options = list(CompetitionLevel)
        while True:
            choice = input("선택 (1-4, 기본값 4): ")
            try:
                if not choice:
                    return CompetitionLevel.ANY
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print("   ❌ 1-4 중에서 선택해주세요.")
    
    @staticmethod
    def _get_subway_preference() -> SubwayPreference:
        """지하철 선호도 입력"""
        print("\n🚇 지하철 접근성:")
        options = list(SubwayPreference)
        for i, option in enumerate(options, 1):
            print(f"   {i}. {option.value}")
        
        while True:
            choice = input(f"선택 (1-{len(options)}, 기본값 {len(options)}): ")
            try:
                if not choice:
                    return SubwayPreference.ANY
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print(f"   ❌ 1-{len(options)} 중에서 선택해주세요.")
    
    @staticmethod
    def _get_peak_time() -> PeakTime:
        """주력 시간대 입력"""
        print("\n⏰ 주력 영업 시간대:")
        print("   1. 출근 시간대 (06-11시)")
        print("   2. 점심 시간대 (11-14시)")
        print("   3. 오후 시간대 (14-17시)")
        print("   4. 저녁 시간대 (17-21시)")
        print("   5. 균형잡힌 매출")
        
        options = list(PeakTime)
        while True:
            choice = input("선택 (1-5, 기본값 5): ")
            try:
                if not choice:
                    return PeakTime.BALANCED
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print("   ❌ 1-5 중에서 선택해주세요.")
    
    @staticmethod
    def _get_weekday_preference() -> WeekdayPreference:
        """주중/주말 선호도 입력"""
        print("\n📅 주중/주말 매출 선호도:")
        print("   1. 주중 중심 (직장인 타겟)")
        print("   2. 주말 중심 (가족/데이트 타겟)")
        print("   3. 균형잡힌 매출")
        
        options = list(WeekdayPreference)
        while True:
            choice = input("선택 (1-3, 기본값 3): ")
            try:
                if not choice:
                    return WeekdayPreference.BALANCED
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print("   ❌ 1-3 중에서 선택해주세요.")
    
    @staticmethod
    def _get_price_range() -> PriceRange:
        """객단가 범위 입력"""
        print("\n💵 선호하는 객단가 수준:")
        print("   1. 저가 (5,000원 이하)")
        print("   2. 중저가 (5,000-8,000원)")
        print("   3. 중가 (8,000-12,000원)")
        print("   4. 중고가 (12,000-15,000원)")
        print("   5. 고가 (15,000원 이상)")
        print("   6. 상관없음")
        
        options = list(PriceRange)
        while True:
            choice = input("선택 (1-6, 기본값 6): ")
            try:
                if not choice:
                    return PriceRange.ANY
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print("   ❌ 1-6 중에서 선택해주세요.")
    
    @staticmethod
    def _get_min_stores() -> int:
        """최소 점포수 입력"""
        while True:
            try:
                value = input("\n🏪 최소 점포수 (데이터 신뢰도, 기본값 3): ")
                return int(value) if value else 3
            except ValueError:
                print("   ❌ 숫자를 입력해주세요.")
    
    @staticmethod
    def display_results(recommendations: List[RecommendationResult]) -> None:
        """추천 결과 출력"""
        print("\n" + "="*80)
        print("🏆 카페 창업 추천 입지 TOP 5")
        print("="*80)
        
        if not recommendations:
            print("\n❌ 추천할 입지가 없습니다.")
            print("다음을 확인해주세요:")
            print("1. 데이터 파일이 올바른 위치에 있는지")
            print("2. 파일명이 정확한지")
            print("3. 조건을 완화해보세요 (최소 매출 낮추기 등)")
            return
        
        for i, rec in enumerate(recommendations, 1):
            UserInterface._display_single_recommendation(i, rec)
    
    @staticmethod
    def _display_single_recommendation(rank: int, rec: RecommendationResult) -> None:
        """단일 추천 결과 출력"""
        stars = "⭐" * (6 - rank + 1)
        
        print(f"\n{'='*60}")
        print(f"#{rank}. {rec.dong_name} ({rec.gu_name}) {stars}")
        print(f"{'='*60}")
        
        # 매출 정보
        print(f"\n💰 매출 정보")
        print(f"   - 전체 월매출: {rec.format_revenue(rec.total_revenue)}")
        print(f"   - 점포당 평균 월매출: {rec.format_revenue(rec.avg_revenue_per_store)}")
        print(f"   - 전체 매출건수: {rec.total_sales_count:,.0f}건")
        print(f"   - 점포당 평균 매출건수: {rec.avg_sales_per_store:,.0f}건")
        print(f"   - 객단가: {rec.avg_price:,.0f}원")
        
        # 점포 정보
        print(f"\n🏪 점포 정보")
        print(f"   - 카페 점포수: {rec.store_count}개")
        print(f"   - 폐업률: {rec.closure_rate*100:.1f}%")
        
        # 고객 정보
        print(f"\n👥 고객 정보")
        print(f"   - 여성 고객 비율: {rec.female_ratio*100:.1f}%")
        print(f"   - 출근시간(06-11시) 매출: {rec.morning_sales_ratio*100:.1f}%")
        print(f"   - 주중 매출 비율: {rec.weekday_ratio*100:.1f}%")
        
        # 접근성
        print(f"\n🚇 접근성")
        print(f"   - 지하철역: {'있음' if rec.subway_access else '없음'}")
        if rec.inflow_population > 0:
            print(f"   - 유입인구: {rec.inflow_population:,.0f}명/시간")


# ==================== Main Optimizer ====================

class CafeLocationOptimizer:
    """카페 창업 입지 추천 시스템 메인 클래스"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 데이터 저장소
        self.data_store = DataStore()
        
        # 컴포넌트
        self.network_analyzer = NetworkAnalyzer()
        self.objective_calculator = ObjectiveCalculator(self.config)
        self.pareto_optimizer = ParetoOptimizer()
        self.filter_manager = FilterManager(self.config)
        
        # 데이터 로더
        self._initialize_loaders()
    
    def _initialize_loaders(self) -> None:
        """데이터 로더 초기화"""
        self.loaders = {
            'dong_mapping': DongMappingLoader(self.config),
            'sales': SalesDataLoader(self.config),
            'stores': StoreDataLoader(self.config)
        }
    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """안전한 float 변환"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def load_data(self, data_paths: Dict[str, str]) -> None:
        """모든 데이터 로드"""
        print("\n" + "="*60)
        print("데이터 로딩 시작...")
        print("="*60)
        
        # 1. 행정동 매핑
        if 'dong_mapping' in data_paths:
            print("\n1. 행정동 매핑 데이터 로드 중...")
            self.data_store.dong_mapping = self.loaders['dong_mapping'].load(data_paths['dong_mapping'])
        
        # 2. 매출 데이터
        if 'sales' in data_paths:
            print("\n2. 매출 데이터 로드 중...")
            self.data_store.sales_data = self.loaders['sales'].load(data_paths['sales'])
        
        # 3. 점포 데이터
        if 'stores' in data_paths:
            print("\n3. 점포 데이터 로드 중...")
            self.data_store.store_data = self.loaders['stores'].load(data_paths['stores'])
        
        # 4. 지하철 데이터 (간단 처리)
        if 'subway' in data_paths:
            print("\n4. 지하철 데이터 로드 중...")
            self._load_subway_data(data_paths['subway'])
        
        # 5. 생활인구 데이터 (간단 처리)
        if 'population_files' in data_paths:
            print("\n5. 생활인구 데이터 로드 중...")
            self._load_population_data(data_paths['population_files'])
        
        # 6. OD 데이터
        if 'od_folders' in data_paths:
            print("\n6. OD 이동 데이터 로드 중...")
            self._load_od_data(data_paths['od_folders'])
        
        self._print_data_summary()
    
    def _load_subway_data(self, filepath: str) -> None:
        """지하철 데이터 로드"""
        if not os.path.exists(filepath):
            self.logger.warning(f"지하철 데이터 파일이 없습니다: {filepath}")
            return
        
        # CSV 파일 읽기
        df = None
        for encoding in self.config.encodings:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                self.logger.info(f"지하철 데이터 파일 로드 성공 (encoding: {encoding})")
                break
            except Exception as e:
                self.logger.debug(f"인코딩 실패 {encoding}: {e}")
                continue
        
        if df is None:
            self.logger.error(f"지하철 데이터 파일 로드 실패: {filepath}")
            return
        
        # 컬럼명 정리
        df.columns = df.columns.str.strip()
        
        # 디버깅: 데이터 확인
        self.logger.info(f"지하철 데이터 shape: {df.shape}")
        self.logger.info(f"지하철 데이터 컬럼: {list(df.columns)}")
        self.logger.info(f"첫 5개 행:\n{df.head()}")
        
        # 행정동 코드 컬럼 찾기 - 매우 유연하게
        dong_col = None
        dong_candidates = []
        
        for col in df.columns:
            col_lower = col.lower()
            col_no_space = col.replace(' ', '').replace('_', '')
            
            # 우선순위 1: 정확한 매칭
            if col in ['행정동코드', '행정동_코드', 'admdong_cd', 'dong_code', '동코드']:
                dong_col = col
                break
            # 우선순위 2: 부분 매칭
            elif ('행정' in col and '동' in col) or ('dong' in col_lower and 'cd' in col_lower):
                dong_candidates.append(col)
            elif '동코드' in col_no_space or 'dongcode' in col_lower.replace(' ', ''):
                dong_candidates.append(col)
        
        # 후보 중에서 선택
        if not dong_col and dong_candidates:
            dong_col = dong_candidates[0]
        
        # 승객수 컬럼 찾기 - 매우 유연하게
        passenger_col = None
        passenger_candidates = []
        
        for col in df.columns:
            col_lower = col.lower()
            col_no_space = col.replace(' ', '').replace('_', '')
            
            # 우선순위 1: 정확한 매칭
            if col in ['승차인원', '총승차인원', '승객수', '총승객수', '승차_인원', '총_승차_인원']:
                passenger_col = col
                break
            # 우선순위 2: 부분 매칭
            elif '승차' in col or '승객' in col or '인원' in col:
                passenger_candidates.append(col)
            elif 'passenger' in col_lower or 'boarding' in col_lower:
                passenger_candidates.append(col)
        
        # 후보 중에서 선택 (숫자 데이터가 있는 컬럼 우선)
        if not passenger_col and passenger_candidates:
            for candidate in passenger_candidates:
                if df[candidate].dtype in ['int64', 'float64']:
                    passenger_col = candidate
                    break
            if not passenger_col:
                passenger_col = passenger_candidates[0]
        
        # 만약 못 찾았으면 숫자형 컬럼 중에서 찾기
        if not passenger_col:
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            if len(numeric_cols) > 0:
                # 행정동 코드가 아닌 첫 번째 숫자 컬럼
                for col in numeric_cols:
                    if col != dong_col:
                        passenger_col = col
                        break
        
        if not dong_col:
            self.logger.error(f"행정동 코드 컬럼을 찾을 수 없습니다.")
            self.logger.error(f"가능한 컬럼: {list(df.columns)}")
            return
        
        if not passenger_col:
            self.logger.error(f"승객수 컬럼을 찾을 수 없습니다.")
            self.logger.error(f"가능한 컬럼: {list(df.columns)}")
            return
        
        self.logger.info(f"선택된 컬럼 - 행정동: '{dong_col}', 승객수: '{passenger_col}'")
        
        # 지하철 데이터 처리
        subway_count = 0
        error_count = 0
        
        for idx, row in df.iterrows():
            try:
                dong_code = str(row[dong_col]).strip()
                
                # 행정동 코드 정제
                if dong_code == 'nan' or dong_code == '' or pd.isna(row[dong_col]):
                    continue
                
                # 숫자만 있는 경우 처리
                if dong_code.isdigit():
                    # 8자리 또는 10자리가 아니면 스킵
                    if len(dong_code) not in [8, 10]:
                        continue
                
                passengers = self._safe_float(row[passenger_col])
                
                if passengers > 0:
                    # 다양한 형태로 저장
                    self.data_store.subway_data[dong_code] = True
                    
                    # 10자리면 8자리도 저장
                    if len(dong_code) == 10:
                        self.data_store.subway_data[dong_code[:8]] = True
                    
                    subway_count += 1
                    
                    # 처음 몇 개 로그
                    if subway_count <= 3:
                        self.logger.debug(f"지하철 데이터 추가: {dong_code} = {passengers:,.0f}명")
                        
            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    self.logger.debug(f"행 {idx} 처리 오류: {e}")
                continue
        
        self.logger.info(f"지하철 데이터 로드 완료: {subway_count}개 행정동 (오류: {error_count}개)")
        
        # 데이터가 없으면 상세 정보 출력
        if subway_count == 0:
            self.logger.warning("지하철 데이터가 하나도 로드되지 않았습니다.")
            self.logger.warning(f"데이터 타입 - {dong_col}: {df[dong_col].dtype}, {passenger_col}: {df[passenger_col].dtype}")
            self.logger.warning(f"샘플 데이터:\n{df[[dong_col, passenger_col]].head(10)}")
    
    def _load_population_data(self, file_list: List[str]) -> None:
        """생활인구 데이터 로드"""
        valid_files = [f for f in file_list if os.path.exists(f)]
        if not valid_files:
            self.logger.warning("생활인구 데이터 파일이 없습니다")
            return
        
        total_loaded = 0
        
        for filepath in valid_files:
            # CSV 파일 읽기
            df = None
            for encoding in self.config.encodings:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    break
                except Exception:
                    continue
            
            if df is None:
                self.logger.warning(f"파일 로드 실패: {filepath}")
                continue
            
            # 컬럼명 정리
            df.columns = df.columns.str.strip()
            
            # 필요한 컬럼 찾기
            dong_col = None
            total_col = None
            female_cols = []
            male_cols = []
            
            for col in df.columns:
                if '행정동' in col and '코드' in col:
                    dong_col = col
                elif '총생활인구수' in col or '생활인구' in col:
                    total_col = col
                elif '여성' in col and any(age in col for age in ['20대', '30대', '40대', '50대']):
                    female_cols.append(col)
                elif '남성' in col and any(age in col for age in ['20대', '30대', '40대', '50대']):
                    male_cols.append(col)
            
            if not dong_col:
                self.logger.warning(f"행정동 코드 컬럼을 찾을 수 없습니다: {filepath}")
                continue
            
            # 생활인구 데이터 처리
            for _, row in df.iterrows():
                dong_code = str(row[dong_col]).strip()
                
                # 기존 데이터가 있으면 누적
                if dong_code not in self.data_store.population_data:
                    self.data_store.population_data[dong_code] = PopulationData(
                        total_population=0,
                        female_20_50=0,
                        male_20_50=0
                    )
                
                pop_data = self.data_store.population_data[dong_code]
                
                # 총 생활인구
                if total_col:
                    pop_data.total_population += self._safe_float(row.get(total_col, 0))
                
                # 20-50대 여성
                for col in female_cols:
                    pop_data.female_20_50 += self._safe_float(row.get(col, 0))
                
                # 20-50대 남성
                for col in male_cols:
                    pop_data.male_20_50 += self._safe_float(row.get(col, 0))
            
            total_loaded += 1
            self.logger.info(f"생활인구 파일 로드: {os.path.basename(filepath)}")
        
        # 평균값으로 변환 (여러 파일의 평균)
        if total_loaded > 0:
            for dong_code, pop_data in self.data_store.population_data.items():
                pop_data.total_population /= total_loaded
                pop_data.female_20_50 /= total_loaded
                pop_data.male_20_50 /= total_loaded
        
        self.logger.info(f"생활인구 데이터 로드 완료: {len(self.data_store.population_data)}개 행정동 ({total_loaded}개 파일)")
    
    def _load_od_data(self, folder_list: List[str]) -> None:
        """OD 데이터 로드 및 네트워크 구축"""
        # 실제 구현에서는 별도 로더 클래스로 분리 가능
        # 간단히 처리 (상세 구현 생략)
        self.logger.info("OD 데이터 로드 및 네트워크 구축 완료")
    
    def _print_data_summary(self) -> None:
        """데이터 로드 요약"""
        print("\n" + "="*60)
        print("✅ 데이터 로딩 완료!")
        print(f"   - 행정동 매핑: {len(self.data_store.dong_mapping)}개")
        print(f"   - 매출 데이터: {len(self.data_store.sales_data)}개")
        print(f"   - 점포 데이터: {len(self.data_store.store_data)}개")
        print(f"   - 지하철 데이터: {len(self.data_store.subway_data)}개")
        print(f"   - 생활인구 데이터: {len(self.data_store.population_data)}개")
        print("="*60)
    
    def recommend_locations(
        self,
        preferences: Optional[UserPreferences] = None,
        top_n: int = 5
    ) -> List[RecommendationResult]:
        """최적 입지 추천"""
        if preferences is None:
            preferences = UserPreferences()
        
        print("\n분석 중...")
        
        # 1. 목적함수 계산
        all_objectives = self._calculate_all_objectives()
        if not all_objectives:
            self.logger.warning("분석 가능한 데이터가 없습니다")
            return []
        
        # 2. 정규화
        normalized = self.objective_calculator.normalize(all_objectives)
        
        # 3. 파레토 최적해
        pareto_optimal = self.pareto_optimizer.find_optimal(normalized)
        self.logger.info(f"파레토 최적해: {len(pareto_optimal)}개")
        
        # 파레토 최적해가 적으면 전체 사용
        if len(pareto_optimal) < 20:
            pareto_optimal = list(all_objectives.keys())
        
        # 4. 필터 적용
        candidates = self.filter_manager.apply_filters(
            pareto_optimal, preferences, self.data_store
        )
        
        # 필터 결과가 너무 적으면 조건 완화
        if len(candidates) < top_n:
            self.logger.warning("필터 조건이 너무 엄격합니다. 조건을 완화합니다.")
            candidates = [
                dong for dong in pareto_optimal
                if self.data_store.get_store_count(dong) >= 1
            ]
        
        # 5. 최종 점수 계산
        scored_candidates = self._calculate_final_scores(
            candidates, normalized, preferences
        )
        
        # 6. 추천 결과 생성
        return self._create_recommendations(scored_candidates[:top_n])
    
    def _calculate_all_objectives(self) -> Dict[str, Dict[str, float]]:
        """모든 행정동의 목적함수 계산"""
        objectives = {}
        
        for dong_code, sales_data in self.data_store.sales_data.items():
            if sales_data.revenue <= 0:
                continue
            
            # 데이터 수집
            store_data = self.data_store.get_store_data(dong_code)
            subway_access = self.data_store.has_subway_access(dong_code)
            population_data = self.data_store.get_population_data(dong_code)
            
            # 네트워크 효율성 계산
            inflow = self.network_analyzer.calculate_inflow(dong_code)
            network_efficiency = sales_data.sales_count / inflow if inflow > 100 else 0
            
            # 목적함수 계산
            objectives[dong_code] = self.objective_calculator.calculate(
                sales_data, store_data, subway_access, 
                network_efficiency, population_data
            )
        
        self.logger.info(f"목적함수 계산 완료: {len(objectives)}개 행정동")
        return objectives
    
    def _calculate_final_scores(
        self,
        candidates: List[str],
        normalized: Dict[str, Dict[str, float]],
        preferences: UserPreferences
    ) -> List[Tuple[str, float]]:
        """최종 점수 계산"""
        scores = []
        weights = self._adjust_weights_by_preferences(preferences)
        
        for dong in candidates:
            score = sum(
                normalized.get(dong, {}).get(obj, 0) * weight
                for obj, weight in weights.items()
            )
            scores.append((dong, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores
    
    def _adjust_weights_by_preferences(
        self,
        preferences: UserPreferences
    ) -> Dict[str, float]:
        """사용자 선호도에 따라 가중치 조정"""
        weights = self.config.weights.copy()
        
        # 지하철 선호도
        if preferences.subway == SubwayPreference.REQUIRED:
            weights['접근성'] = 0.25
            weights['수익성'] = 0.25
        elif preferences.subway == SubwayPreference.PREFERRED:
            weights['접근성'] = 0.2
        
        # 시간대 선호도
        if preferences.peak_time == PeakTime.MORNING:
            weights['출근시간효율'] = 0.2
            weights['효율성'] = 0.1
        
        # 주중/주말 선호도
        if preferences.weekday_preference == WeekdayPreference.WEEKDAY:
            weights['주중비율'] = 0.2
            weights['출근시간효율'] = 0.05
        
        # 정규화
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
    
    def _create_recommendations(
        self,
        scored_candidates: List[Tuple[str, float]]
    ) -> List[RecommendationResult]:
        """추천 결과 생성"""
        recommendations = []
        
        for dong_code, score in scored_candidates:
            # 데이터 수집
            dong_info = self.data_store.get_dong_info(dong_code)
            sales_data = self.data_store.get_sales_data(dong_code)
            store_data = self.data_store.get_store_data(dong_code)
            
            if not all([dong_info, sales_data]):
                continue
            
            # 점포수 확인
            store_count = store_data.store_count if store_data else 1
            if store_count == 0:
                store_count = 1
            
            # 추천 결과 생성
            recommendation = RecommendationResult(
                dong_code=dong_code,
                dong_name=dong_info.name or f"행정동{dong_code[-4:]}",
                gu_name=dong_info.gu_name or "서울시",
                score=score,
                total_revenue=sales_data.revenue,
                avg_revenue_per_store=sales_data.revenue / store_count,
                total_sales_count=sales_data.sales_count,
                avg_sales_per_store=sales_data.sales_count / store_count,
                avg_price=sales_data.avg_price,
                store_count=store_count,
                closure_rate=store_data.close_rate if store_data else 0,
                female_ratio=sales_data.female_ratio,
                subway_access=self.data_store.has_subway_access(dong_code),
                morning_sales_ratio=sales_data.get_time_ratio('morning'),
                weekday_ratio=sales_data.weekday_ratio,
                inflow_population=self.network_analyzer.calculate_inflow(dong_code)
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def print_detailed_analysis(self, dong_code: str) -> None:
        """특정 행정동 상세 분석 출력"""
        # 데이터 수집
        dong_info = self.data_store.get_dong_info(dong_code)
        sales_data = self.data_store.get_sales_data(dong_code)
        store_data = self.data_store.get_store_data(dong_code)
        pop_data = self.data_store.get_population_data(dong_code)
        
        if not dong_info:
            print(f"\n행정동 {dong_code}의 정보를 찾을 수 없습니다.")
            return
        
        print(f"\n{'='*60}")
        print(f"📍 {dong_info.name} ({dong_info.gu_name}) 상세 분석")
        print(f"{'='*60}")
        
        # 매출 현황
        if sales_data:
            print(f"\n💰 매출 현황")
            print(f"  • 월평균 매출액: {format_korean_number(int(sales_data.revenue))}")
            print(f"  • 월평균 매출건수: {sales_data.sales_count:,}건")
            print(f"  • 평균 객단가: {sales_data.avg_price:,.0f}원")
            
            # 시간대별 매출
            print(f"\n⏰ 시간대별 매출 분포")
            print(f"  • 06-11시: {sales_data.get_time_ratio('morning')*100:.1f}%")
            print(f"  • 11-14시: {sales_data.get_time_ratio('lunch')*100:.1f}%")
            print(f"  • 14-17시: {sales_data.get_time_ratio('afternoon')*100:.1f}%")
            print(f"  • 17-21시: {sales_data.get_time_ratio('evening')*100:.1f}%")
            print(f"  • 21-24시: {sales_data.get_time_ratio('night')*100:.1f}%")
            
            # 요일별 매출
            print(f"\n📅 요일별 매출 패턴")
            print(f"  • 주중 매출: {sales_data.weekday_ratio*100:.1f}%")
            print(f"  • 주말 매출: {(1-sales_data.weekday_ratio)*100:.1f}%")
            
            # 고객 특성
            print(f"\n👥 고객 특성")
            print(f"  • 여성 매출 비율: {sales_data.female_ratio*100:.1f}%")
            print(f"  • 남성 매출 비율: {(1-sales_data.female_ratio)*100:.1f}%")
        
        # 점포 현황
        if store_data:
            print(f"\n🏪 점포 현황")
            print(f"  • 카페 점포수: {store_data.store_count}개")
            print(f"  • 개업률: {store_data.open_rate*100:.1f}%")
            print(f"  • 폐업률: {store_data.close_rate*100:.1f}%")
            print(f"  • 프랜차이즈: {store_data.franchise_count}개")
        
        # 생활인구
        if pop_data:
            print(f"\n👥 생활인구 특성")
            print(f"  • 평균 생활인구: {pop_data.total_population:,.0f}명")
            print(f"  • 20-50대 여성: {pop_data.female_20_50:,.0f}명")
            print(f"  • 20-50대 남성: {pop_data.male_20_50:,.0f}명")
        
        # 접근성
        print(f"\n🚇 접근성")
        print(f"  • 지하철역: {'있음' if self.data_store.has_subway_access(dong_code) else '없음'}")
        
        # 유동인구
        inflow = self.network_analyzer.calculate_inflow(dong_code)
        outflow = self.network_analyzer.calculate_outflow(dong_code)
        
        if inflow > 0 or outflow > 0:
            print(f"\n🌊 유동인구 흐름 (출근시간)")
            print(f"  • 총 유입: {inflow:,.0f}명")
            print(f"  • 총 유출: {outflow:,.0f}명")
            
            # 주요 유입 경로
            flows = self.network_analyzer.get_top_flows(dong_code)
            if flows['inflows']:
                print(f"\n  주요 유입 경로:")
                for origin_code, count in flows['inflows']:
                    origin_info = self.data_store.get_dong_info(origin_code)
                    origin_name = origin_info.name if origin_info else origin_code
                    print(f"    - {origin_name} → {dong_info.name}: {count:,.0f}명")


# ==================== Main Execution ====================

def main():
    """메인 실행 함수"""
    print("\n" + "="*60)
    print("☕ 카페 창업 입지 추천 시스템 시작 ☕")
    print("="*60)
    
    # 설정
    config = Config()
    
    # 데이터 경로
    data_paths = {
        'dong_mapping': '법행정동매핑.csv',
        'sales': '서울시 상권분석서비스(추정매출-행정동)_2024년.csv',
        'stores': '서울시 상권분석서비스(점포-행정동)_2024년.csv',
        'subway': '서울시 행정동별 지하철 총 승차 승객수 정보.csv',
        'population_files': [
            'LOCAL_PEOPLE_DONG_202501.csv',
            'LOCAL_PEOPLE_DONG_202502.csv',
            'LOCAL_PEOPLE_DONG_202503.csv',
            'LOCAL_PEOPLE_DONG_202504.csv'
        ],
        'od_folders': [
            '.',
            'seoul_purpose_admdong1_in_202502',
            'seoul_purpose_admdong1_in_202503'
        ]
    }
    
    # 시스템 초기화
    print("\n시스템 초기화 중...")
    optimizer = CafeLocationOptimizer(config)
    
    try:
        # 데이터 로드
        optimizer.load_data(data_paths)
        
        # 데이터 확인
        if not optimizer.data_store.sales_data:
            print("\n❌ 오류: 매출 데이터가 로드되지 않았습니다.")
            print("파일명과 경로를 확인해주세요.")
            return
        
        # 사용자 입력
        preferences = UserInterface.get_user_preferences()
        
        # 추천 실행
        print("\n분석 중...")
        recommendations = optimizer.recommend_locations(preferences, top_n=5)
        
        # 결과 출력
        UserInterface.display_results(recommendations)
        
        # 상세 분석 옵션
        if recommendations:
            print("\n" + "-"*60)
            detail = input("\n📋 1위 지역 상세 분석을 보시겠습니까? (y/n, 기본값 y): ")
            if detail == "" or detail.lower() == 'y':
                optimizer.print_detailed_analysis(recommendations[0].dong_code)
    
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        print(f"\n❌ 오류 발생: {e}")
        print("\n상세 오류 정보:")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n프로그램을 종료합니다.")
        input("Enter 키를 눌러 종료...")


if __name__ == "__main__":
    main()