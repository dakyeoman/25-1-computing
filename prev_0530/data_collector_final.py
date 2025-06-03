#!/usr/bin/env python3
"""
data_collector_debug.py - Flow 디버깅을 위한 개선된 버전
"""

import json
import logging
import requests
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from prev_0602.seoul_api_client import SeoulDataAPIClient

logger = logging.getLogger(__name__)


class MaximumFlowNetwork:
    """Maximum Flow 네트워크 - 디버깅 기능 추가"""
    
    def __init__(self):
        self.graph = defaultdict(dict)
        self.residual_graph = defaultdict(dict)
        self.nodes = set()
        self.edge_count = 0
        self.total_capacity = 0
        
    def add_edge(self, u: str, v: str, capacity: int):
        """간선 추가"""
        if capacity <= 0:
            return
            
        self.graph[u][v] = capacity
        self.residual_graph[u][v] = capacity
        
        if u not in self.residual_graph[v]:
            self.residual_graph[v][u] = 0
            
        self.nodes.add(u)
        self.nodes.add(v)
        self.edge_count += 1
        self.total_capacity += capacity
        
        logger.debug(f"간선 추가: {u} -> {v}, 용량: {capacity:,}")
    
    def get_network_info(self) -> Dict:
        """네트워크 정보 반환"""
        return {
            'node_count': len(self.nodes),
            'edge_count': self.edge_count,
            'total_capacity': self.total_capacity,
            'nodes': list(self.nodes),
            'source_edges': len(self.graph.get('SOURCE', {})),
            'sink_edges': sum(1 for node in self.graph if 'SINK' in self.graph[node])
        }
    
    def bfs(self, source: str, sink: str, parent: Dict[str, str]) -> bool:
        """BFS로 증가 경로 찾기"""
        visited = set([source])
        queue = deque([source])
        
        while queue:
            u = queue.popleft()
            
            for v in self.residual_graph[u]:
                if v not in visited and self.residual_graph[u][v] > 0:
                    visited.add(v)
                    parent[v] = u
                    
                    if v == sink:
                        return True
                        
                    queue.append(v)
        
        return False
    
    def edmonds_karp(self, source: str, sink: str) -> Tuple[int, Dict[str, Dict[str, int]]]:
        """Edmonds-Karp 알고리즘 - 디버깅 정보 추가"""
        parent = {}
        max_flow = 0
        flow_dict = defaultdict(lambda: defaultdict(int))
        path_count = 0
        
        logger.info(f"Maximum Flow 계산 시작...")
        logger.info(f"네트워크 정보: {self.get_network_info()}")
        
        while self.bfs(source, sink, parent):
            path_flow = float('inf')
            s = sink
            path = []
            
            # 경로 추적
            while s != source:
                path.append(s)
                path_flow = min(path_flow, self.residual_graph[parent[s]][s])
                s = parent[s]
            path.append(source)
            path.reverse()
            
            # 경로 로깅
            path_count += 1
            logger.debug(f"경로 {path_count}: {' -> '.join(path)}, 유량: {path_flow:,}")
            
            # 유량 업데이트
            v = sink
            while v != source:
                u = parent[v]
                self.residual_graph[u][v] -= path_flow
                self.residual_graph[v][u] += path_flow
                flow_dict[u][v] += path_flow
                v = parent[v]
            
            max_flow += path_flow
            parent = {}
        
        logger.info(f"Maximum Flow 계산 완료: {max_flow:,} (경로 수: {path_count})")
        return max_flow, dict(flow_dict)


class DataCollector:
    """통합 데이터 수집기 - 개선된 Flow Network"""
    
    def __init__(self, api_key: str = "51504b7a6861646b35314b797a7771"):
        self.api_key = api_key
        self.base_url = "http://openapi.seoul.go.kr:8088"
        self.seoul_client = SeoulDataAPIClient()
        
        # 세션 설정
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 캐시
        self.population_cache = {}
        self.commercial_cache = {}
        self.sales_cache = {}
        
        # 확장된 인접 지역 맵 (더 많은 연결)
        self.adjacency_map = {
            '강남역': ['역삼역', '신논현역', '삼성역', '선릉역', '교대역', '서초역'],
            '역삼역': ['강남역', '선릉역', '논현역', '언주역'],
            '신논현역': ['강남역', '논현역', '신사역'],
            '홍대입구역': ['합정역', '상수역', '신촌역', '서교동'],
            '합정역': ['홍대입구역', '망원역', '상수역'],
            '신촌역': ['홍대입구역', '이대역', '신촌·이대역'],
            '명동': ['을지로입구역', '충무로역', '종각역', '명동 관광특구'],
            '종로': ['종각역', '안국역', '종로3가역', '종로·청계 관광특구'],
            '이태원역': ['녹사평역', '한강진역', '이태원 관광특구'],
            '건대입구역': ['성수역', '구의역', '화양동'],
            '성수역': ['건대입구역', '뚝섬역', '성수카페거리'],
            '잠실역': ['잠실새내역', '잠실 관광특구', '송파역'],
            '광화문·덕수궁': ['시청역', '종각역', '경복궁역'],
            '명동 관광특구': ['명동', '을지로입구역', '충무로역'],
            '홍대 관광특구': ['홍대입구역', '상수역', '합정역'],
            '강남 MICE 관광특구': ['강남역', '삼성역', '코엑스'],
            '이태원 관광특구': ['이태원역', '녹사평역', '한강진역'],
            '잠실 관광특구': ['잠실역', '잠실새내역', '올림픽공원']
        }
    
    def collect_data(self, areas: List[str]) -> Tuple[List[Dict], Optional[MaximumFlowNetwork]]:
        """데이터 수집 및 Flow Network 구성"""
        logger.info(f"데이터 수집 시작: {len(areas)}개 지역")
        
        # 1. 기본 데이터 수집
        location_data = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._collect_area_data, area): area for area in areas}
            
            for future in as_completed(futures):
                try:
                    data = future.result()
                    if data:
                        location_data.append(data)
                        logger.info(f"수집 완료: {data['area_name']}")
                except Exception as e:
                    logger.error(f"데이터 수집 실패: {e}")
        
        # 2. Flow Network 구성
        flow_network = self._build_flow_network(location_data) if location_data else None
        
        logger.info(f"수집 완료: {len(location_data)}개 지역")
        return location_data, flow_network
    
    def _collect_area_data(self, area_name: str) -> Optional[Dict]:
        """개별 지역 데이터 수집"""
        try:
            pop_data = self.seoul_client.get_population_data(area_name)
            com_data = self.seoul_client.get_commercial_data(area_name)
            
            if pop_data and com_data:
                # 데이터 검증 로깅
                logger.debug(f"{area_name} - 인구: {pop_data.get('population_max', 0):,}, "
                           f"결제건수: {com_data.get('area_payment_count', 0):,}")
                
                return {
                    'area_name': area_name,
                    'population': pop_data,
                    'commercial': com_data,
                    'sales': None
                }
        except Exception as e:
            logger.error(f"{area_name} 수집 오류: {e}")
        return None
    
    def _build_flow_network(self, locations: List[Dict]) -> MaximumFlowNetwork:
        """Flow Network 구성 - 용량 증가 버전"""
        network = MaximumFlowNetwork()
        
        logger.info("Flow Network 구성 시작...")
        
        # 1. SOURCE → 지역 (유입 인구) - 용량 증가
        for loc in locations:
            area = loc['area_name']
            pop_max = loc['population'].get('population_max', 0)
            non_resident = loc['population'].get('non_resident_ratio', 50) / 100
            
            # 최소 1000 보장, 스케일 증가 (10% → 30%)
            capacity = max(1000, int(pop_max * non_resident * 0.3))
            network.add_edge('SOURCE', area, capacity)
            logger.debug(f"SOURCE -> {area}: {capacity:,}")
        
        # 2. 지역 간 연결 - 더 많은 연결 추가
        for i, loc1 in enumerate(locations):
            area1 = loc1['area_name']
            pop1 = loc1['population'].get('population_max', 0)
            
            for j, loc2 in enumerate(locations):
                if i >= j:
                    continue
                area2 = loc2['area_name']
                pop2 = loc2['population'].get('population_max', 0)
                
                # 모든 지역 간 최소 연결 보장
                base_capacity = max(100, int(min(pop1, pop2) * 0.05))
                
                # 인접 지역은 더 강한 연결
                if area2 in self.adjacency_map.get(area1, []) or area1 in self.adjacency_map.get(area2, []):
                    capacity = base_capacity * 3
                else:
                    capacity = base_capacity
                
                network.add_edge(area1, area2, capacity)
                network.add_edge(area2, area1, capacity)
        
        # 3. 지역 → SINK (구매 전환) - 용량 증가
        for loc in locations:
            area = loc['area_name']
            payment_count = loc['commercial'].get('area_payment_count', 0)
            
            capacity = max(5000, int(pop_max * non_resident * 0.5))
            network.add_edge('SOURCE', area, capacity)
            logger.debug(f"SOURCE -> {area}: {capacity:,}")
        
        # 네트워크 정보 출력
        info = network.get_network_info()
        logger.info(f"Flow Network 구성 완료:")
        logger.info(f"  - 노드 수: {info['node_count']}")
        logger.info(f"  - 간선 수: {info['edge_count']}")
        logger.info(f"  - 총 용량: {info['total_capacity']:,}")
        
        return network
    
    def analyze_flow(self, network: MaximumFlowNetwork, locations: List[Dict]) -> Dict:
        """Flow 분석 실행"""
        logger.info("Flow 분석 시작...")
        
        max_flow, flow_dict = network.edmonds_karp('SOURCE', 'SINK')
        
        flow_analysis = {
            'max_flow': max_flow,
            'areas': {},
            'network_info': network.get_network_info()
        }
        
        # 각 지역별 분석
        for loc in locations:
            area = loc['area_name']
            
            # SOURCE에서의 유입
            inflow = flow_dict.get('SOURCE', {}).get(area, 0)
            
            # SINK로의 유출
            outflow = flow_dict.get(area, {}).get('SINK', 0)
            
            # 다른 지역으로부터의 유입
            from_others = sum(flow_dict.get(other, {}).get(area, 0) 
                            for other in flow_dict if other not in ['SOURCE', area])
            
            # 다른 지역으로의 유출
            to_others = sum(flow_dict.get(area, {}).get(other, 0) 
                          for other in flow_dict.get(area, {}) if other != 'SINK')
            
            total_inflow = inflow + from_others
            total_outflow = outflow + to_others
            
            flow_analysis['areas'][area] = {
                'inflow': total_inflow,
                'outflow': outflow,  # SINK로의 유출만
                'from_source': inflow,
                'to_sink': outflow,
                'from_others': from_others,
                'to_others': to_others,
                'efficiency': outflow / total_inflow if total_inflow > 0 else 0,
                'balance': total_inflow - total_outflow
            }
            
            logger.debug(f"{area} - 유입: {total_inflow:,}, 전환: {outflow:,}, "
                       f"효율: {flow_analysis['areas'][area]['efficiency']:.2%}")
        
        logger.info(f"Flow 분석 완료 - 최대 유량: {max_flow:,}")
        return flow_analysis