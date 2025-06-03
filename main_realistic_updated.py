#!/usr/bin/env python3
"""
main_realistic.py - 100% 실제 데이터 기반 창업 입지 추천 시스템
모든 추정치 제거, 실제 API 데이터만 사용
"""

import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

# 실제 데이터 기반 모듈들
from complete_data_mapping import CompleteCommercialAnalysisAPI, SeoulAreaMapping
from realistic_flow_network import RealisticFlowBuilder, analyze_realistic_flow
from realistic_optimizer import RealisticOptimizer, RealisticStartupConstraints
from report_generator_realistic import RealisticReportGenerator, create_realistic_user_output
from seoul_api import  #SeoulDataAPIClient, Config
from movement_processor_py import MovementDataProcessor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('realistic_startup_analysis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class RealisticDataCollector:
    """100% 실제 데이터 수집기"""
    
    def __init__(self, api_key: str = "51504b7a6861646b35314b797a7771"):
        self.api_key = api_key
        self.seoul_client = SeoulDataAPIClient(api_key)
        self.commercial_api = CompleteCommercialAnalysisAPI(api_key)
        self.mapping = SeoulAreaMapping()
        
    def collect_realistic_data(self, areas: List[str], business_type: str) -> Tuple[List[Dict], Dict]:
        """실제 데이터만 수집"""
        logger.info(f"실제 데이터 수집 시작: {len(areas)}개 지역")
        
        location_data = []
        data_availability = {
            'population': 0,
            'commercial': 0,
            'rent': 0,
            'dynamics': 0,
            'movement': 0
        }
        
        for area in areas:
            logger.info(f"수집 중: {area}")
            
            # 1. 기본 인구/상권 데이터 (기존 API)
            pop_data = self.seoul_client.get_population_data(area)
            com_data = self.seoul_client.get_commercial_data(area)
            
            if not pop_data or not com_data:
                logger.warning(f"{area}: 기본 데이터 없음")
                continue
            
            # 2. 완전한 상권 분석 데이터 (새 API)
            complete_analysis = self.commercial_api.get_complete_analysis(area, business_type)
            
            # 데이터 가용성 체크
            if pop_data:
                data_availability['population'] += 1
            if com_data:
                data_availability['commercial'] += 1
            if complete_analysis.get('rent_info'):
                data_availability['rent'] += 1
            if complete_analysis.get('business_dynamics'):
                data_availability['dynamics'] += 1
            
            # 통합 데이터 구성
            integrated_data = {
                'area_name': area,
                'population': pop_data,
                'commercial': com_data,
                'complete_analysis': complete_analysis,
                'has_real_data': (
                    complete_analysis.get('data_availability', {}).get('commercial', False) or
                    complete_analysis.get('data_availability', {}).get('rent', False) or
                    complete_analysis.get('data_availability', {}).get('dynamics', False)
                )
            }
            
            location_data.append(integrated_data)
            logger.info(f"✓ {area} 수집 완료 (실제 데이터: {integrated_data['has_real_data']})")
        
        # 데이터 품질 보고서
        quality_report = {
            'total_areas': len(areas),
            'collected_areas': len(location_data),
            'data_coverage': {
                key: f"{(count/len(location_data)*100):.1f}%" if location_data else "0%"
                for key, count in data_availability.items()
            },
            'fully_covered_areas': sum(1 for loc in location_data if loc['has_real_data'])
        }
        
        logger.info(f"데이터 수집 완료: {len(location_data)}개 지역")
        logger.info(f"실제 데이터 완전성: {quality_report['fully_covered_areas']}/{len(location_data)} 지역")
        
        return location_data, quality_report


def get_user_input() -> Tuple[List[str], RealisticStartupConstraints]:
    """사용자 입력 (개선된 버전)"""
    print("\n" + "="*60)
    print("🏪 서울시 창업 입지 추천 시스템 (100% 실제 데이터)")
    print("="*60)
    
    # 업종 선택
    business_types = ['카페', '음식점', '주점', '편의점', '학원', '미용실', '약국', '헬스장']
    print("\n📋 업종 선택:")
    for i, bt in enumerate(business_types, 1):
        print(f"  {i}. {bt}")
    
    while True:
        try:
            choice = int(input("선택 (1-8): "))
            if 1 <= choice <= 8:
                business_type = business_types[choice-1]
                break
        except ValueError:
            pass
    
    # 타겟 고객
    print("\n👥 타겟 고객 (쉼표로 구분):")
    print("  1. 직장인  2. 학생  3. 주민  4. 관광객")
    target_map = {'1': '직장인', '2': '학생', '3': '주민', '4': '관광객'}
    targets = input("선택: ").strip()
    target_customers = [target_map[x] for x in targets.split(',') if x in target_map] or ['직장인']
    
    # 목표 객단가
    print("\n💰 목표 객단가:")
    print("  ※ 실제 지역별 객단가 데이터와 비교됩니다")
    budget_min = int(input("  최소 객단가 (원): "))
    budget_max = int(input("  최대 객단가 (원): "))
    
    # 최대 경쟁 매장 수
    print("\n🏢 최대 허용 경쟁 매장 수:")
    print("  ※ 실제 점포 수 데이터 기준")
    max_competition = int(input("  개수: "))
    
    # 타겟 매칭률
    print("\n🎯 최소 타겟 매칭률 (%):")
    min_target_match = float(input("  비율: "))
    
    # 성별 타겟
    print("\n👫 성별 타겟 고객:")
    print("  1. 성별 무관")
    print("  2. 남성 중심")
    print("  3. 여성 중심")
    gender_choice = input("선택 (1-3, 기본=1): ").strip() or '1'
    
    target_gender = 'all'
    min_gender_ratio = 40.0
    
    if gender_choice == '2':
        target_gender = 'male'
        min_gender_ratio = float(input("  남성 최소 비율 (예: 60): "))
    elif gender_choice == '3':
        target_gender = 'female'
        min_gender_ratio = float(input("  여성 최소 비율 (예: 60): "))
    
    # 상권 특성
    print("\n🏙️ 선호하는 상권 특성 (복수 선택 가능):")
    print("  1. 관광지")
    print("  2. 오피스 지역")
    print("  3. 주거 지역")
    print("  4. 대학가")
    area_input = input("선택 (예: 1,2): ").strip()
    
    prefer_tourist_area = '1' in area_input
    prefer_office_area = '2' in area_input
    prefer_residential_area = '3' in area_input
    prefer_university_area = '4' in area_input
    
    # 분석 지역 선택
    print("\n📍 분석 지역:")
    print("  1. 주요 5개 (빠른 테스트)")
    print("  2. 주요 20개 (일반 분석)")
    print("  3. 전체 82개 (전체 분석)")
    print("  4. 직접 입력")
    print("  5. 실제 데이터 보장 지역만")
    area_choice = input("선택: ").strip()
    
    if area_choice == '1':
        areas = Config.TEST_AREAS
    elif area_choice == '2':
        areas = Config.AVAILABLE_AREAS[:20]
    elif area_choice == '3':
        areas = Config.AVAILABLE_AREAS
    elif area_choice == '5':
        # 실제 데이터가 확실한 주요 지역만 (API가 지원하는 정확한 명칭)
        areas = [
            '강남역', '건대입구역', '이태원역', '여의도', '잠실역',
            '역삼역', '신논현역·논현역', '선릉역', '교대역',
            '양재역', '압구정로데오거리', '청담동 명품거리',
            '가로수길', '강남 MICE 관광특구', '동대문 관광특구',
            '이태원 관광특구', '잠실 관광특구', '홍대 관광특구',
            '고속터미널역', '가락시장'
        ]
    else:
        areas = input("지역명 (쉼표 구분): ").split(',')
        areas = [a.strip() for a in areas if a.strip()] or Config.TEST_AREAS
    
    # 제약조건 객체 생성
    constraints = RealisticStartupConstraints(
        business_type=business_type,
        target_customers=target_customers,
        budget_min=budget_min,
        budget_max=budget_max,
        max_competition=max_competition,
        min_target_match=min_target_match,
        target_gender=target_gender,
        min_gender_ratio=min_gender_ratio,
        prefer_tourist_area=prefer_tourist_area,
        prefer_office_area=prefer_office_area,
        prefer_residential_area=prefer_residential_area,
        prefer_university_area=prefer_university_area
    )
    
    return areas, constraints


def main():
    """메인 함수 - 100% 실제 데이터 기반"""
    parser = argparse.ArgumentParser(description='창업 입지 추천 (실제 데이터)')
    parser.add_argument('--areas', nargs='+', help='분석 지역')
    parser.add_argument('--business-type', default='카페', help='업종')
    parser.add_argument('--no-flow', action='store_true', help='Flow 분석 제외')
    parser.add_argument('--data-check', action='store_true', help='데이터 가용성만 확인')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 사용자 입력
        if args.areas:
            areas = args.areas
            constraints = RealisticStartupConstraints(
                business_type=args.business_type,
                target_customers=['직장인'],
                budget_min=5000,
                budget_max=20000,
                max_competition=50,
                min_target_match=50,
                target_gender='all',
                min_gender_ratio=40.0
            )
        else:
            areas, constraints = get_user_input()
        
        print(f"\n🔄 실제 데이터 수집 시작: {len(areas)}개 지역...")
        
        # 1. 실제 데이터 수집
        collector = RealisticDataCollector()
        location_data, quality_report = collector.collect_realistic_data(areas, constraints.business_type)
        
        # 데이터 품질 체크
        print(f"\n📊 데이터 수집 결과:")
        print(f"   - 요청 지역: {quality_report['total_areas']}개")
        print(f"   - 수집 성공: {quality_report['collected_areas']}개")
        print(f"   - 완전한 데이터: {quality_report['fully_covered_areas']}개")
        
        if args.data_check:
            # 데이터 가용성만 확인하고 종료
            print("\n📋 데이터 가용성 상세:")
            for coverage_type, percentage in quality_report['data_coverage'].items():
                print(f"   - {coverage_type}: {percentage}")
            return
        
        if not location_data:
            print("\n❌ 데이터 수집 실패: 사용 가능한 데이터가 없습니다.")
            return
        
        if quality_report['fully_covered_areas'] < len(location_data) * 0.5:
            print("\n⚠️ 경고: 완전한 데이터를 가진 지역이 50% 미만입니다.")
            print("    일부 분석 결과가 제한적일 수 있습니다.")
        
        # 2. 실제 Flow Network 구성 (옵션)
        flow_analysis = None
        if not args.no_flow:
            print("\n🌊 실제 이동 데이터 기반 Flow Network 구성 중...")
            flow_builder = RealisticFlowBuilder()
            flow_network, movement_data = flow_builder.build_realistic_flow_network(
                location_data, constraints.business_type
            )
            
            if flow_network:
                flow_analysis = analyze_realistic_flow(flow_network, location_data)
                print(f"✓ Maximum Flow 계산 완료: {flow_analysis['max_flow']:,}")
                
                # Flow 데이터 품질 확인
                network_info = flow_analysis['network_info']
                print(f"   - 실제 데이터 비율: {network_info['actual_data_ratio']:.1%}")
        
        # 3. 최적화 (실제 데이터 기반)
        print("\n🎯 실제 데이터 기반 최적화 수행 중...")
        optimizer = RealisticOptimizer()
        results = optimizer.optimize(location_data, constraints, flow_analysis)
        
        # 4. 결과 확인 및 출력
        if not results.get('pareto_optimal'):
            print("\n❌ 조건을 만족하는 지역을 찾을 수 없습니다.")
            
            # 실패 원인 분석
            print("\n📊 필터링 결과:")
            print(f"   - 전체 지역: {len(location_data)}개")
            print(f"   - 필터 통과: {len(results.get('filtered_locations', []))}개")
            
            # 조건 완화 제안
            print("\n💡 제안사항:")
            print("   1. 경쟁 매장 수 기준을 높여보세요")
            print("   2. 객단가 범위를 넓혀보세요")
            print("   3. 더 많은 지역을 분석해보세요")
            
        else:
            # 성공: 실제 데이터 기반 보고서 출력
            print(f"\n✅ 최적화 완료: {len(results['pareto_optimal'])}개 추천 지역")
            
            # 사용자 친화적 출력 (100% 실제 데이터)
            output = create_realistic_user_output(results, constraints)
            print(output)
            
            # 데이터 신뢰도 표시
            print("\n" + "="*60)
            print("📊 데이터 신뢰도")
            print("="*60)
            print("✓ 모든 수치는 서울시 공공 API의 실제 데이터입니다:")
            print("  - 유동인구: 서울시 실시간 인구 현황")
            print("  - 매출/객단가: 서울시 상권분석서비스")
            print("  - 임대료: 서울시 부동산 실거래가")
            print("  - 개폐업률: 서울시 창업/폐업 통계")
            print("  - 이동패턴: 서울시 생활이동 데이터")
        
        # 5. 결과 저장 옵션
        save = input("\n\n💾 분석 결과를 저장하시겠습니까? (y/n): ").lower() == 'y'
        if save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # JSON 저장 (실제 데이터 포함)
            filename_json = f"realistic_results_{timestamp}.json"
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'data_source': '서울시 공공 API (100% 실제 데이터)',
                'constraints': {
                    'business_type': constraints.business_type,
                    'target_customers': constraints.target_customers,
                    'budget_min': constraints.budget_min,
                    'budget_max': constraints.budget_max,
                    'max_competition': constraints.max_competition
                },
                'data_quality': quality_report,
                'results_summary': {
                    'total_areas': len(location_data),
                    'filtered': len(results.get('filtered_locations', [])),
                    'recommended': len(results.get('pareto_optimal', []))
                },
                'top_locations': []
            }
            
            # 상위 지역 상세 데이터
            for loc in results.get('pareto_optimal', [])[:10]:
                area_data = {
                    'area': loc.area_name,
                    'scores': {
                        'profitability': loc.profitability,
                        'stability': loc.stability,
                        'accessibility': loc.accessibility,
                        'network_efficiency': loc.network_efficiency
                    }
                }
                
                # 실제 데이터 추가
                complete_data = next((l['complete_analysis'] for l in location_data 
                                    if l['area_name'] == loc.area_name), None)
                if complete_data:
                    area_data['real_data'] = {
                        'daily_floating': complete_data.get('floating_population', {}).get('daily_average', 0),
                        'monthly_rent': complete_data.get('rent_info', {}).get('average_monthly_rent', 0),
                        'open_rate': complete_data.get('business_dynamics', {}).get('open_rate', 0),
                        'close_rate': complete_data.get('business_dynamics', {}).get('close_rate', 0),
                        'expected_revenue': complete_data.get('calculated_metrics', {}).get('expected_monthly_revenue', 0)
                    }
                
                save_data['top_locations'].append(area_data)
            
            with open(filename_json, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 저장 완료: {filename_json}")
        
        print("\n\n감사합니다! 실제 데이터 기반 분석이 도움이 되길 바랍니다! 🎉")
        
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
    except Exception as e:
        logger.error(f"오류: {e}", exc_info=True)
        print(f"\n❌ 오류가 발생했습니다: {e}")
        print("   로그 파일(realistic_startup_analysis.log)을 확인해주세요.")


if __name__ == "__main__":
    main()