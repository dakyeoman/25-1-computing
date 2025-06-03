#!/usr/bin/env python3
"""
movement_data_processor.py - 서울시 생활이동 데이터 처리 모듈
행정동 단위 시간대별 이동 데이터를 분석하여 Flow Network에 활용
"""

import os
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime
import glob

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MovementDataProcessor:
    """생활이동 데이터 처리기"""
    
    def __init__(self, data_dir: str = "./movement_data"):
        self.data_dir = data_dir
        
        # 열 이름 정의 (실제 데이터 구조에 맞게 조정)
        self.columns = [
            '대상연월',         # 202504
            '요일',            # 일
            '도착시간',         # 3
            '출발 행정동 코드',  # 출발 행정동
            '도착 행정동 코드',  # 도착 행정동
            '성별',            # M/F
            '나이',            # 연령대
            '이동유형',         # 이동목적 (WH, HW, EE 등)
            '평균 이동 시간(분)', # 평균이동시간
            '이동인구(합)'      # 이동인원
        ]
        
        # 행정동 코드 → 상권명 매핑 (주요 지역 확장)
        self.dong_to_area_map = {
            # 종로구 (1111)
            '1111010100': '종로',           # 청운동
            '1111010200': '광화문·덕수궁',  # 신교동
            '1111010300': '경복궁',         # 궁정동
            '1111010500': '광화문·덕수궁',  # 창성동
            '1111010700': '서촌',           # 익선동
            '1111012600': '종로',           # 종로1가
            '1111013600': '인사동',         # 인사동
            '1111014000': '북촌한옥마을',   # 삼청동
            '1111014100': '북촌한옥마을',   # 안국동
            '1111015600': '종로',           # 종로3가
            '1111016900': '혜화역',         # 혜화동
            
            # 중구 (1114)
            '1114010100': '명동',           # 무교동
            '1114010200': '시청',           # 다동
            '1114010300': '을지로입구역',   # 태평로1가
            '1114010400': '을지로입구역',   # 을지로1가
            '1114010500': '을지로입구역',   # 을지로2가
            '1114011100': '명동',           # 소공동
            '1114011200': '남대문시장',     # 남창동
            '1114011300': '북창동 먹자골목', # 북창동
            '1114012100': '명동 관광특구',  # 회현동2가
            '1114012400': '충무로역',       # 충무로1가
            '1114012600': '명동',           # 명동1가
            '1114012700': '명동',           # 명동2가
            
            # 용산구 (1117)
            '1117010100': '용산역',         # 후암동
            '1117010500': '용산역',         # 남영동
            '1117010900': '용산역',         # 청파동1가
            '1117012400': '용산역',         # 한강로1가
            '1117012900': '이태원역',       # 이촌동
            '1117013000': '이태원역',       # 이태원동
            '1117013100': '이태원 관광특구', # 한남동
            '1117013200': '이태원 앤틱가구거리', # 동빙고동
            
            # 성동구 (1120)
            '1120010100': '왕십리역',       # 상왕십리동
            '1120010200': '왕십리역',       # 하왕십리동
            '1120010700': '뚝섬역',         # 행당동
            '1120011400': '성수역',         # 성수동1가
            '1120011500': '성수카페거리',   # 성수동2가
            
            # 광진구 (1121)
            '1121510100': '건대입구역',     # 중곡동
            '1121510300': '건대입구역',     # 구의동
            '1121510500': '건대입구역',     # 자양동
            '1121510700': '건대입구역',     # 화양동
            
            # 동대문구 (1123)
            '1123010100': 'DDP(동대문디자인플라자)', # 신설동
            '1123010200': '동대문역',       # 용두동
            '1123010300': '청량리 제기동 일대 전통시장', # 제기동
            '1123010700': '청량리 제기동 일대 전통시장', # 청량리동
            '1123010800': '회기역',         # 회기동
            '1123010900': '경희대',         # 휘경동
            
            # 중랑구 (1126)
            '1126010100': '면목역',         # 면목동
            '1126010400': '사가정역',       # 묵동
            '1126010500': '망우역',         # 망우동
            
            # 성북구 (1129)
            '1129010100': '성신여대입구역', # 성북동
            '1129010300': '성신여대입구역', # 돈암동
            '1129011600': '고려대',         # 동선동1가
            '1129013500': '고려대',         # 종암동
            '1129013600': '월곡역',         # 하월곡동
            
            # 강북구 (1130)
            '1130510100': '미아사거리역',   # 미아동
            '1130510300': '수유역',         # 수유동
            
            # 도봉구 (1132)
            '1132010500': '쌍문역',         # 쌍문동
            '1132010600': '방학역',         # 방학동
            '1132010700': '창동 신경제 중심지', # 창동
            '1132010800': '도봉역',         # 도봉동
            
            # 노원구 (1135)
            '1135010200': '노원역',         # 월계동
            '1135010300': '노원역',         # 공릉동
            '1135010400': '노원역',         # 하계동
            '1135010500': '노원역',         # 상계동
            '1135010600': '노원역',         # 중계동
            
            # 은평구 (1138)
            '1138010100': '불광역',         # 수색동
            '1138010400': '연신내역',       # 갈현동
            '1138010500': '구산역',         # 구산동
            '1138010600': '연신내역',       # 대조동
            '1138010700': '불광역',         # 응암동
            '1138010900': 'DMC(디지털미디어시티)', # 신사동
            
            # 서대문구 (1141)
            '1141010100': '충정로역',       # 충정로2가
            '1141010600': '서대문역',       # 천연동
            '1141010900': '독립문역',       # 현저동
            '1141011200': '홍대입구역',     # 대현동
            '1141011400': '신촌역',         # 대신동
            '1141011500': '신촌역',         # 신촌동
            '1141011600': '신촌·이대역',    # 봉원동
            '1141011700': '신촌·이대역',    # 창천동
            '1141011800': '홍대입구역(2호선)', # 연희동
            
            # 마포구 (1144)
            '1144010100': '홍대입구역',     # 아현동
            '1144010300': '공덕역',         # 신공덕동
            '1144010400': '공덕역',         # 도화동
            '1144010800': '마포역',         # 대흥동
            '1144011200': '홍대입구역',     # 현석동
            '1144011500': '상수역',         # 상수동
            '1144012000': '홍대입구역',     # 서교동
            '1144012100': '홍대입구역',     # 동교동
            '1144012200': '합정역',         # 합정동
            '1144012300': '망원역',         # 망원동
            '1144012400': '연남동',         # 연남동
            '1144012500': '홍대 관광특구',  # 성산동
            
            # 양천구 (1147)
            '1147010100': '목동역',         # 신정동
            '1147010200': '오목교역·목동운동장', # 목동
            '1147010300': '신월역',         # 신월동
            
            # 강서구 (1150)
            '1150010100': '염창역',         # 염창동
            '1150010300': '까치산역',       # 화곡동
            '1150010400': '가양역',         # 가양동
            '1150010500': '마곡나루역',     # 마곡동
            '1150010800': '김포공항',       # 공항동
            '1150010900': '발산역',         # 방화동
            '1150011200': '우장산역',       # 오곡동
            
            # 구로구 (1153)
            '1153010100': '신도림역',       # 신도림동
            '1153010200': '구로역',         # 구로동
            '1153010300': '구로디지털단지역', # 가리봉동
            '1153010600': '대림역',         # 고척동
            '1153010700': '개봉역',         # 개봉동
            '1153010800': '오류역',         # 오류동
            
            # 금천구 (1154)
            '1154510100': '가산디지털단지역', # 가산동
            '1154510200': '독산역',         # 독산동
            '1154510300': '시흥역',         # 시흥동
            
            # 영등포구 (1156)
            '1156010100': '영등포역',       # 영등포동
            '1156010200': '영등포 타임스퀘어', # 영등포동1가
            '1156011000': '여의도',         # 여의도동
            '1156011100': '당산역',         # 당산동1가
            '1156011700': '당산역',         # 당산동
            '1156011900': '영등포 타임스퀘어', # 문래동1가
            '1156012300': '영등포 타임스퀘어', # 문래동5가
            '1156013300': '대림역',         # 대림동
            
            # 동작구 (1159)
            '1159010100': '노량진',         # 노량진동
            '1159010400': '신대방역',       # 본동
            '1159010500': '이수역',         # 흑석동
            '1159010700': '사당역',         # 사당동
            '1159010800': '신대방역',       # 대방동
            
            # 관악구 (1162)
            '1162010100': '서울대입구역',   # 봉천동
            '1162010200': '신림역',         # 신림동
            '1162010300': '낙성대역',       # 남현동
            
            # 서초구 (1165)
            '1165010100': '방배역',         # 방배동
            '1165010200': '양재역',         # 양재동
            '1165010400': '신분당선',       # 원지동
            '1165010700': '고속터미널역',   # 반포동
            '1165010800': '서초역',         # 서초동
            '1165010900': '교대역',         # 내곡동
            '1165011000': '양재역',         # 염곡동
            
            # 강남구 (1168)
            '1168010100': '역삼역',         # 역삼동
            '1168010300': '개포동',         # 개포동
            '1168010400': '청담동 명품거리', # 청담동
            '1168010500': '삼성역',         # 삼성동
            '1168010600': '대치역',         # 대치동
            '1168010700': '압구정로데오거리', # 신사동
            '1168010800': '논현역',         # 논현동
            '1168011000': '압구정로데오거리', # 압구정동
            '1168011300': '일원역',         # 율현동
            '1168011400': '일원역',         # 일원동
            '1168011500': '수서역',         # 수서동
            '1168011800': '도곡역',         # 도곡동
            
            # 송파구 (1171)
            '1171010100': '잠실역',         # 잠실동
            '1171010200': '잠실새내역',     # 신천동
            '1171010300': '천호역',         # 풍납동
            '1171010400': '잠실 관광특구',  # 송파동
            '1171010500': '석촌역',         # 석촌동
            '1171010600': '가락시장',       # 삼전동
            '1171010700': '가락시장',       # 가락동
            '1171010800': '문정역',         # 문정동
            '1171010900': '장지역',         # 장지동
            '1171011100': '올림픽공원',     # 방이동
            '1171011200': '오금역',         # 오금동
            '1171011300': '거여역',         # 거여동
            '1171011400': '마천역',         # 마천동
            
            # 강동구 (1174)
            '1174010100': '천호역',         # 명일동
            '1174010200': '고덕역',         # 고덕동
            '1174010300': '상일동역',       # 상일동
            '1174010500': '길동역',         # 길동
            '1174010600': '둔촌역',         # 둔촌동
            '1174010700': '암사역',         # 암사동
            '1174010800': '강동역',         # 성내동
            '1174010900': '천호역',         # 천호동
            '1174011000': '강일역',         # 강일동
        }
        
        # 이동 목적 코드 설명
        self.purpose_codes = {
            'HH': '야간상주지→야간상주지',
            'HW': '야간상주지→주간상주지',  # 출근
            'HE': '야간상주지→기타',        # 집에서 여가/쇼핑
            'WH': '주간상주지→야간상주지',  # 퇴근
            'WW': '주간상주지→주간상주지',  # 업무 중 이동
            'WE': '주간상주지→기타',        # 점심/외근
            'EH': '기타→야간상주지',        # 여가에서 귀가
            'EW': '기타→주간상주지',        # 출근(경유)
            'EE': '기타→기타'               # 여가/쇼핑 간 이동
        }
        
        # 업종별 피크 시간대 정의
        self.business_peak_hours = {
            '카페': [7, 8, 9, 12, 13],       # 출근 + 점심
            '음식점': [12, 13, 18, 19, 20],  # 점심 + 저녁
            '편의점': [7, 8, 19, 20, 21],    # 출퇴근 시간
            '주점': [18, 19, 20, 21, 22],    # 저녁~밤
            '학원': [15, 16, 17, 18, 19],    # 오후~저녁
            '미용실': [10, 11, 14, 15, 16],  # 낮 시간대
            '약국': [9, 10, 11, 18, 19],     # 오전 + 퇴근
            '헬스장': [6, 7, 18, 19, 20]     # 새벽/퇴근 후
        }
        
        # 캐시
        self.cached_data = {}
    
    def load_hour_file(self, hour: int, date: str = "202504") -> pd.DataFrame:
        """특정 시간대 파일 로드"""
        cache_key = f"{date}_{hour:02d}"
        
        if cache_key in self.cached_data:
            return self.cached_data[cache_key]
        
        # 수정된 경로: 하위 폴더 포함
        folder_name = f"생활이동_행정동_{date}"
        folder_path = os.path.join(self.data_dir, folder_name)
        
        # 정확한 파일명 패턴
        filename = f"생활이동_행정동_{date[:4]}.{date[4:]}_{hour:02d}시.csv"
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"파일을 찾을 수 없음: {file_path}")
            return pd.DataFrame()
        
        try:
            logger.info(f"파일 로드 중: {filename}")
            
            # CSV 읽기 - 헤더가 있는 파일
            df = pd.read_csv(file_path, encoding='utf-8')
            
            logger.info(f"로드된 컬럼: {list(df.columns)}")
            logger.info(f"{hour}시 데이터 로드 완료: {len(df):,} rows")
            
            # 별표(*) 처리 - NaN으로 변환
            df = df.replace('*', pd.NA)
            
            # 숫자형 변환
            numeric_cols = ['평균 이동 시간(분)', '이동인구(합)']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 행정동 코드를 문자열로 유지
            df['출발 행정동 코드'] = df['출발 행정동 코드'].astype(str)
            df['도착 행정동 코드'] = df['도착 행정동 코드'].astype(str)
            
            self.cached_data[cache_key] = df
            
            return df
            
        except Exception as e:
            logger.error(f"파일 로드 실패 ({hour}시): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """데이터프레임의 컬럼 자동 감지"""
        column_mapping = {}
        
        for col in df.columns:
            sample = df[col].astype(str).iloc[0] if len(df) > 0 else ""
            
            # 행정동 코드 감지
            if len(sample) in [8, 10] and sample.isdigit():
                if 'from' not in column_mapping:
                    column_mapping['from_dong'] = col
                elif 'to' not in column_mapping:
                    column_mapping['to_dong'] = col
            
            # 성별 감지
            elif set(df[col].unique()) <= {'M', 'F', 'Male', 'Female', '남', '여'}:
                column_mapping['gender'] = col
            
            # 이동 목적 감지
            elif any(purpose in str(df[col].iloc[0]) for purpose in ['HW', 'WH', 'HE', 'EH']):
                column_mapping['purpose'] = col
            
            # 숫자 컬럼 감지
            elif df[col].dtype in ['int64', 'float64'] or df[col].astype(str).str.isdigit().all():
                if 'count' not in column_mapping and df[col].max() > 100:
                    column_mapping['count'] = col
                elif 'time' not in column_mapping:
                    column_mapping['avg_time'] = col
        
        logger.info(f"자동 감지된 컬럼 매핑: {column_mapping}")
        return column_mapping
    
    def load_all_hours(self, date: str = "202504") -> Dict[int, pd.DataFrame]:
        """전체 시간대 데이터 로드"""
        all_data = {}
        
        for hour in range(24):
            df = self.load_hour_file(hour, date)
            if not df.empty:
                all_data[hour] = df
        
        logger.info(f"총 {len(all_data)}개 시간대 데이터 로드 완료")
        return all_data
    
    def get_area_movements(self, hour_data: pd.DataFrame, 
                          target_areas: Optional[List[str]] = None) -> Dict[Tuple[str, str], int]:
        """상권 단위로 이동량 집계"""
        movements = defaultdict(int)
        unmapped_count = 0
        
        if hour_data.empty:
            return dict(movements)
        
        for _, row in hour_data.iterrows():
            try:
                from_dong = str(row['출발 행정동 코드'])
                to_dong = str(row['도착 행정동 코드'])
                
                # 7자리 코드를 10자리로 변환
                if len(from_dong) == 7:
                    from_dong = from_dong + '00'
                if len(to_dong) == 7:
                    to_dong = to_dong + '00'
                
                from_area = self.dong_to_area_map.get(from_dong)
                to_area = self.dong_to_area_map.get(to_dong)
                
                # 매핑 안 된 동 추적
                if not from_area or not to_area:
                    unmapped_count += 1
                    continue
                
                # 타겟 지역 필터링
                if target_areas:
                    if from_area not in target_areas and to_area not in target_areas:
                        continue
                
                # 같은 지역 내 이동은 제외
                if from_area != to_area:
                    count = row['이동인구(합)']
                    if pd.notna(count):  # NaN이 아닌 경우만
                        movements[(from_area, to_area)] += int(count)
                    
            except Exception as e:
                logger.debug(f"행 처리 중 오류: {e}")
                continue
        
        if unmapped_count > 0:
            logger.info(f"매핑되지 않은 이동: {unmapped_count}건")
        
        return dict(movements)
    
    def get_hourly_inflow(self, area: str, hour_data: pd.DataFrame) -> int:
        """특정 지역으로의 시간대별 유입 인구"""
        inflow = 0
        
        if hour_data.empty:
            return inflow
        
        for _, row in hour_data.iterrows():
            to_dong = str(row['도착 행정동 코드'])
            if len(to_dong) == 7:
                to_dong = to_dong + '00'
                
            to_area = self.dong_to_area_map.get(to_dong)
            if to_area == area:
                from_dong = str(row['출발 행정동 코드'])
                if len(from_dong) == 7:
                    from_dong = from_dong + '00'
                    
                from_area = self.dong_to_area_map.get(from_dong)
                # 외부에서 유입 (다른 상권 또는 매핑 안 된 지역)
                if from_area != area:
                    count = row['이동인구(합)']
                    if pd.notna(count):
                        inflow += int(count)
        
        return inflow
    
    def get_hourly_outflow(self, area: str, hour_data: pd.DataFrame) -> int:
        """특정 지역에서의 시간대별 유출 인구"""
        outflow = 0
        
        if hour_data.empty:
            return outflow
        
        for _, row in hour_data.iterrows():
            from_dong = str(row['출발 행정동 코드'])
            if len(from_dong) == 7:
                from_dong = from_dong + '00'
                
            from_area = self.dong_to_area_map.get(from_dong)
            if from_area == area:
                to_dong = str(row['도착 행정동 코드'])
                if len(to_dong) == 7:
                    to_dong = to_dong + '00'
                    
                to_area = self.dong_to_area_map.get(to_dong)
                # 외부로 유출
                if to_area != area:
                    count = row['이동인구(합)']
                    if pd.notna(count):
                        outflow += int(count)
        
        return outflow
    
    def analyze_peak_hours(self, area: str, all_hours_data: Dict[int, pd.DataFrame]) -> List[int]:
        """특정 지역의 피크 시간대 분석"""
        hourly_inflow = {}
        
        for hour, df in all_hours_data.items():
            inflow = self.get_hourly_inflow(area, df)
            hourly_inflow[hour] = inflow
        
        # 상위 30% 시간대 추출
        sorted_hours = sorted(hourly_inflow.items(), key=lambda x: x[1], reverse=True)
        peak_count = max(1, len(sorted_hours) // 3)
        peak_hours = [hour for hour, _ in sorted_hours[:peak_count]]
        
        return sorted(peak_hours)
    
    def get_target_customer_flow(self, hour_data: pd.DataFrame, 
                               target_profile: Dict) -> Dict[str, int]:
        """타겟 고객층의 이동 패턴 분석"""
        target_flow = defaultdict(int)
        
        if hour_data.empty:
            return dict(target_flow)
        
        for _, row in hour_data.iterrows():
            # 타겟 매칭
            if 'age' in target_profile and str(row['나이']) not in target_profile['age']:
                continue
            if 'gender' in target_profile and row['성별'] != target_profile['gender']:
                continue
            if 'purpose' in target_profile and row['이동유형'] not in target_profile['purpose']:
                continue
            
            to_dong = str(row['도착 행정동 코드'])
            if len(to_dong) == 7:
                to_dong = to_dong + '00'
                
            to_area = self.dong_to_area_map.get(to_dong)
            if to_area:
                count = row['이동인구(합)']
                if pd.notna(count):
                    target_flow[to_area] += int(count)
        
        return dict(target_flow)
    
    def analyze_business_type_flow(self, hour_data: pd.DataFrame, business_type: str) -> Dict[str, Dict]:
        """업종별 최적 고객 유형 분석"""
        
        # 업종별 주요 타겟 이동 패턴
        business_target_patterns = {
            '카페': {
                'morning': ['HW'],           # 출근길 고객
                'lunch': ['WE', 'WW'],       # 점심시간 고객
                'evening': ['WH', 'EE'],     # 퇴근길, 여가 고객
            },
            '음식점': {
                'lunch': ['WE', 'WW'],       # 점심 식사
                'dinner': ['WH', 'WE', 'EE'], # 저녁 식사
            },
            '편의점': {
                'all_day': ['HH', 'WH', 'HW', 'EH'],  # 상주지 근처 이동
            },
            '학원': {
                'afternoon': ['HE'],         # 학생 (집→학원)
                'evening': ['WE', 'WH'],     # 직장인 (퇴근 후)
            },
            '주점': {
                'evening': ['WH', 'WE', 'WW', 'EE'],  # 저녁/회식
            }
        }
        
        patterns = business_target_patterns.get(business_type, {})
        result = {}
        
        # 컬럼 매핑
        col_mapping = self.detect_columns(hour_data)
        
        for time_slot, purposes in patterns.items():
            flow_by_area = defaultdict(int)
            
            for _, row in hour_data.iterrows():
                purpose_col = col_mapping.get('purpose', 'purpose')
                if purpose_col in row and row[purpose_col] in purposes:
                    to_dong = str(row.get(col_mapping.get('to_dong', 'to_dong'), ''))
                    if len(to_dong) == 8:
                        to_dong = to_dong + '00'
                        
                    to_area = self.dong_to_area_map.get(to_dong)
                    if to_area:
                        count_col = col_mapping.get('count', 'count')
                        flow_by_area[to_area] += int(row.get(count_col, 0))
            
            result[time_slot] = dict(flow_by_area)
        
        return result
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, any]:
        """데이터 품질 검증"""
        quality_report = {
            'total_rows': len(df),
            'null_counts': df.isnull().sum().to_dict(),
            'unique_purposes': [],
            'count_range': {
                'min': 0,
                'max': 0,
                'mean': 0
            }
        }
        
        # 컬럼 자동 감지
        col_mapping = self.detect_columns(df)
        
        # 이동목적 확인
        if 'purpose' in col_mapping:
            quality_report['unique_purposes'] = df[col_mapping['purpose']].unique().tolist()
        
        # 이동량 통계
        if 'count' in col_mapping:
            count_col = col_mapping['count']
            quality_report['count_range'] = {
                'min': df[count_col].min(),
                'max': df[count_col].max(),
                'mean': df[count_col].mean()
            }
            
            # 이상치 탐지
            q1 = df[count_col].quantile(0.25)
            q3 = df[count_col].quantile(0.75)
            iqr = q3 - q1
            outliers = df[(df[count_col] < q1 - 1.5 * iqr) | (df[count_col] > q3 + 1.5 * iqr)]
            quality_report['outlier_count'] = len(outliers)
        
        return quality_report
    
    def estimate_conversion_rates(self, hour_data: pd.DataFrame, 
                                business_type: str) -> Dict[str, float]:
        """이동 목적별 구매 전환율 추정"""
        
        # 업종별 이동목적에 따른 전환율 (추정치)
        conversion_matrix = {
            '카페': {
                'HW': 0.25,  # 출근길 - 높음
                'WH': 0.15,  # 퇴근길 - 중간
                'WE': 0.20,  # 점심시간/외근 - 높음
                'EE': 0.10,  # 여가 활동 중 - 중간
                'HE': 0.05,  # 집에서 나가는 길 - 낮음
                'EH': 0.08,  # 귀가길 - 낮음
                'WW': 0.12,  # 업무 중 이동 - 중간
            },
            '음식점': {
                'WH': 0.10,  # 퇴근길 저녁
                'WE': 0.40,  # 점심시간 - 매우 높음
                'EE': 0.30,  # 여가/쇼핑 중 식사
                'HE': 0.20,  # 외식 목적 외출
                'WW': 0.25,  # 업무 중 회식
                'EH': 0.15,  # 저녁 후 귀가
            },
            '편의점': {
                'HW': 0.10,  # 출근길 간단한 구매
                'WH': 0.25,  # 퇴근길 장보기 - 높음
                'HH': 0.30,  # 집 근처 이동 - 높음
                'EH': 0.20,  # 귀가 중 들르기
                'HE': 0.15,  # 외출 전 준비
                'EE': 0.15,  # 여가 중 구매
            },
            '학원': {
                'HE': 0.60,  # 야간상주지→학원 (학생)
                'WE': 0.10,  # 주간상주지→학원 (직장인 자기계발)
                'EE': 0.40,  # 다른 학원에서 이동
                'EH': 0.05,  # 학원 후 귀가 준비
            },
            '주점': {
                'WH': 0.05,  # 퇴근 후 한잔
                'WW': 0.15,  # 회식
                'WE': 0.20,  # 저녁 약속
                'EE': 0.25,  # 2차, 3차
                'EH': 0.10,  # 마지막 술집에서 귀가
            }
        }
        
        area_conversions = defaultdict(lambda: {'total': 0, 'converted': 0})
        base_conversion = conversion_matrix.get(business_type, {})
        
        # 컬럼 매핑
        col_mapping = self.detect_columns(hour_data)
        
        for _, row in hour_data.iterrows():
            to_dong = str(row.get(col_mapping.get('to_dong', 'to_dong'), ''))
            if len(to_dong) == 8:
                to_dong = to_dong + '00'
                
            to_area = self.dong_to_area_map.get(to_dong)
            if to_area:
                count = int(row.get(col_mapping.get('count', 'count'), 0))
                purpose = row.get(col_mapping.get('purpose', 'purpose'), '')
                conversion = base_conversion.get(purpose, 0.05)
                
                area_conversions[to_area]['total'] += count
                area_conversions[to_area]['converted'] += count * conversion
        
        # 지역별 평균 전환율 계산
        result = {}
        for area, data in area_conversions.items():
            if data['total'] > 0:
                result[area] = data['converted'] / data['total']
        
        return result
    
    def build_flow_network_data(self, target_areas: List[str], 
                              peak_hours: Optional[List[int]] = None,
                              business_type: str = '카페') -> Dict:
        """Flow Network 구성에 필요한 데이터 생성"""
        
        # 전체 시간대 로드
        all_hours = self.load_all_hours()
        
        if not all_hours:
            logger.error("데이터 로드 실패")
            return {}
        
        # 업종별 피크 시간대 결정
        if peak_hours is None:
            peak_hours = self.business_peak_hours.get(business_type, [8, 12, 18])
        
        # 결과 저장
        flow_data = {
            'movements': defaultdict(lambda: defaultdict(int)),  # (from, to) -> count
            'hourly_inflow': defaultdict(dict),  # area -> hour -> count
            'hourly_outflow': defaultdict(dict),
            'peak_movements': defaultdict(lambda: defaultdict(int)),
            'area_stats': {},
            'unmapped_dongs': set()  # 매핑 안 된 행정동 추적
        }
        
        # 시간대별 처리
        for hour, df in all_hours.items():
            movements = self.get_area_movements(df, target_areas)
            
            # 전체 이동량 누적
            for (from_area, to_area), count in movements.items():
                flow_data['movements'][from_area][to_area] += count
            
            # 피크 시간대 이동량
            if hour in peak_hours:
                for (from_area, to_area), count in movements.items():
                    flow_data['peak_movements'][from_area][to_area] += count
            
            # 지역별 시간대별 유입/유출
            for area in target_areas:
                flow_data['hourly_inflow'][area][hour] = self.get_hourly_inflow(area, df)
                flow_data['hourly_outflow'][area][hour] = self.get_hourly_outflow(area, df)
        
        # 지역별 통계
        for area in target_areas:
            total_inflow = sum(flow_data['hourly_inflow'][area].values())
            total_outflow = sum(flow_data['hourly_outflow'][area].values())
            
            flow_data['area_stats'][area] = {
                'total_daily_inflow': total_inflow,
                'total_daily_outflow': total_outflow,
                'net_flow': total_inflow - total_outflow,
                'peak_hours': self.analyze_peak_hours(area, all_hours),
                'avg_hourly_inflow': total_inflow / 24,
                'peak_hour_inflow': max(flow_data['hourly_inflow'][area].values()) if flow_data['hourly_inflow'][area] else 0
            }
        
        logger.info(f"Flow 데이터 생성 완료: {len(target_areas)}개 지역")
        return dict(flow_data)
    
    def export_for_visualization(self, flow_data: Dict, output_file: str = "flow_visualization.json"):
        """시각화를 위한 데이터 내보내기"""
        import json
        
        viz_data = {
            'nodes': [],
            'links': [],
            'time_series': {}
        }
        
        # 노드 생성
        areas = set()
        for from_area, destinations in flow_data['movements'].items():
            areas.add(from_area)
            areas.update(destinations.keys())
        
        for area in areas:
            stats = flow_data['area_stats'].get(area, {})
            viz_data['nodes'].append({
                'id': area,
                'name': area,
                'total_inflow': stats.get('total_daily_inflow', 0),
                'total_outflow': stats.get('total_daily_outflow', 0)
            })
        
        # 링크 생성 (이동 경로)
        for from_area, destinations in flow_data['movements'].items():
            for to_area, count in destinations.items():
                if count > 100:  # 최소 임계값
                    viz_data['links'].append({
                        'source': from_area,
                        'target': to_area,
                        'value': count
                    })
        
        # 시계열 데이터
        for area, hourly_data in flow_data['hourly_inflow'].items():
            viz_data['time_series'][area] = {
                'hours': list(range(24)),
                'inflow': [hourly_data.get(h, 0) for h in range(24)],
                'outflow': [flow_data['hourly_outflow'][area].get(h, 0) for h in range(24)]
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(viz_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"시각화 데이터 저장: {output_file}")


def main():
    """테스트 및 사용 예시"""
    # 프로세서 초기화
    processor = MovementDataProcessor(data_dir="./movement_data")
    
    # 테스트할 주요 지역
    test_areas = ['강남역', '홍대입구역', '명동', '종로', '신촌역']
    
    # 1. 특정 시간대 데이터 로드 테스트
    print("\n=== 8시 데이터 샘플 ===")
    df_8am = processor.load_hour_file(8)
    if not df_8am.empty:
        print(f"총 {len(df_8am)} 건의 이동 데이터")
        print(f"컬럼: {list(df_8am.columns)}")
        print("\n데이터 샘플:")
        print(df_8am.head())
        
        # 데이터 품질 검증
        quality = processor.validate_data_quality(df_8am)
        print(f"\n데이터 품질:")
        print(f"- 전체 행: {quality['total_rows']:,}")
        print(f"- 이동 목적: {quality['unique_purposes']}")
        print(f"- 이동량 범위: {quality['count_range']['min']:,} ~ {quality['count_range']['max']:,}")
    
    # 2. 지역 간 이동량 분석
    print("\n=== 8시 주요 이동 경로 ===")
    movements = processor.get_area_movements(df_8am, test_areas)
    sorted_movements = sorted(movements.items(), key=lambda x: x[1], reverse=True)[:10]
    for (from_area, to_area), count in sorted_movements:
        print(f"{from_area} → {to_area}: {count:,}명")
    
    # 3. Flow Network 데이터 생성
    print("\n=== Flow Network 데이터 생성 중... ===")
    flow_data = processor.build_flow_network_data(test_areas, peak_hours=[7, 8, 9, 12, 18, 19])
    
    # 4. 결과 출력
    print("\n=== 지역별 일일 통계 ===")
    for area, stats in flow_data['area_stats'].items():
        print(f"\n{area}:")
        print(f"  - 일일 유입: {stats['total_daily_inflow']:,}명")
        print(f"  - 일일 유출: {stats['total_daily_outflow']:,}명")
        print(f"  - 순 유입: {stats['net_flow']:,}명")
        print(f"  - 피크 시간대: {stats['peak_hours']}")
    
    # 5. 시각화 데이터 내보내기
    processor.export_for_visualization(flow_data)
    print("\n시각화 데이터가 'flow_visualization.json'에 저장되었습니다.")


if __name__ == "__main__":
    main()