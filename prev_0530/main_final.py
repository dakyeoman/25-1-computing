#!/usr/bin/env python3
"""
main_with_realistic.py - 기존 main에 성별/상권 특성 입력 추가
"""

import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

from data_collector_final import DataCollector
from realistic_optimizer import RealisticOptimizer, RealisticStartupConstraints
from prev_0602.seoul_api_client import Config
from prev_0602.report_generator import ReportGenerator, create_user_friendly_output

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('startup_analysis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def get_user_input() -> Tuple[List[str], RealisticStartupConstraints]:
    """사용자 입력 (성별/상권 특성 기본 포함)"""
    print("\n" + "="*60)
    print("🏪 서울시 창업 입지 추천 시스템")
    print("="*60)
    
    # === 기본 정보 (공통) ===
    
    # 업종
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
    print("\n💰 목표 객단가 (고객 1인당 평균 결제금액):")
    print("  예시: 카페 5,000~8,000원, 식당 10,000~15,000원")
    budget_min = int(input("  최소 객단가 (원): "))
    budget_max = int(input("  최대 객단가 (원): "))
    
    # 경쟁
    print("\n🏢 최대 허용 경쟁 매장 수:")
    print("  예시: 카페 30~50개, 편의점 10~20개")
    max_competition = int(input("  개수: "))
    
    # 타겟 매칭
    print("\n🎯 최소 타겟 매칭률 (%):")
    print("  예시: 50% = 절반 이상이 내 타겟 고객")
    min_target_match = float(input("  비율: "))
    
    # === 추가 입력 (성별/상권 특성) ===
    
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
        print("  남성 고객이 전체의 몇 % 이상이어야 하나요?")
        min_gender_ratio = float(input("  최소 비율 (예: 60): "))
    elif gender_choice == '3':
        target_gender = 'female'
        print("  여성 고객이 전체의 몇 % 이상이어야 하나요?")
        min_gender_ratio = float(input("  최소 비율 (예: 60): "))
    
    # 상권 특성
    print("\n🏙️ 선호하는 상권 특성 (복수 선택 가능):")
    print("  1. 관광지 (명동, 인사동, 북촌 등)")
    print("  2. 오피스 지역 (강남, 여의도, 종로 등)")
    print("  3. 주거 지역 (아파트 밀집 지역)")
    print("  4. 대학가 (신촌, 홍대, 건대 등)")
    print("  (예: 1,2 또는 엔터=상관없음)")
    
    area_input = input("선택: ").strip()
    prefer_tourist_area = '1' in area_input
    prefer_office_area = '2' in area_input
    prefer_residential_area = '3' in area_input
    prefer_university_area = '4' in area_input
    
    # 지역
    print("\n📍 분석 지역:")
    print("  1. 주요 5개 (빠른 테스트)")
    print("  2. 주요 20개 (일반 분석)")
    print("  3. 전체 82개 (전체 분석)")
    print("  4. 직접 입력")
    area_choice = input("선택: ").strip()
    
    if area_choice == '1':
        areas = Config.TEST_AREAS
    elif area_choice == '2':
        areas = Config.AVAILABLE_AREAS[:20]
    elif area_choice == '3':
        areas = Config.AVAILABLE_AREAS
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


def analyze_failure_reasons(location_data: List[Dict], filtered: List[Dict], 
                          constraints: RealisticStartupConstraints) -> Dict:
    """실패 원인 분석 (확장된 버전)"""
    reasons = {
        'total_analyzed': len(location_data),
        'passed_filter': len(filtered),
        'filter_failures': {
            'budget_mismatch': 0,
            'too_much_competition': 0,
            'low_target_match': 0,
            'gender_mismatch': 0,
            'area_type_mismatch': 0
        },
        'detailed_failures': []
    }
    
    # RealisticOptimizer 인스턴스 생성
    optimizer = RealisticOptimizer()
    
    # 필터링 실패 지역 분석
    failed_areas = [loc for loc in location_data if loc not in filtered]
    
    for loc in failed_areas:
        area_name = loc['area_name']
        failures = []
        
        # 객단가 체크
        com_data = loc.get('commercial', {})
        avg_payment = optimizer._calculate_average_payment_per_person(com_data, constraints.business_type)
        
        if avg_payment > 0:
            if avg_payment < constraints.budget_min:
                failures.append(f"객단가 낮음 ({avg_payment:,.0f}원 < {constraints.budget_min:,}원)")
                reasons['filter_failures']['budget_mismatch'] += 1
            elif avg_payment > constraints.budget_max:
                failures.append(f"객단가 높음 ({avg_payment:,.0f}원 > {constraints.budget_max:,}원)")
                reasons['filter_failures']['budget_mismatch'] += 1
        
        # 경쟁 체크
        competition = optimizer._count_competition(com_data, constraints.business_type)
        if competition > constraints.max_competition:
            failures.append(f"경쟁 과다 ({competition}개 > {constraints.max_competition}개)")
            reasons['filter_failures']['too_much_competition'] += 1
        
        # 타겟 매칭 체크
        target_match = optimizer._calculate_target_match(loc.get('population', {}), constraints.target_customers)
        if target_match < constraints.min_target_match:
            failures.append(f"타겟 부족 ({target_match:.0f}% < {constraints.min_target_match:.0f}%)")
            reasons['filter_failures']['low_target_match'] += 1
        
        # 성별 체크 (고급 모드)
        if constraints.target_gender != 'all':
            gender_data = loc['population'].get('gender_distribution', {})
            if constraints.target_gender == 'male':
                gender_ratio = gender_data.get('male', 50)
            else:
                gender_ratio = gender_data.get('female', 50)
            
            if gender_ratio < constraints.min_gender_ratio:
                failures.append(f"성별 타겟 부족 ({gender_ratio:.1f}% < {constraints.min_gender_ratio:.1f}%)")
                reasons['filter_failures']['gender_mismatch'] += 1
        
        if failures:
            reasons['detailed_failures'].append({
                'area': area_name,
                'reasons': failures
            })
    
    return reasons


def display_failure_analysis(failure_reasons: Dict, constraints: RealisticStartupConstraints):
    """실패 원인 출력 (확장된 버전)"""
    print("\n" + "="*60)
    print("⚠️  조건을 만족하는 지역을 찾을 수 없습니다")
    print("="*60)
    
    print(f"\n📊 분석 요약:")
    print(f"  - 전체 분석 지역: {failure_reasons['total_analyzed']}개")
    print(f"  - 조건 통과 지역: {failure_reasons['passed_filter']}개")
    
    print(f"\n❌ 주요 탈락 원인:")
    failures = failure_reasons['filter_failures']
    
    if failures['budget_mismatch'] > 0:
        print(f"  - 객단가 불일치: {failures['budget_mismatch']}개 지역")
        print(f"    목표: {constraints.budget_min:,}~{constraints.budget_max:,}원")
    
    if failures['too_much_competition'] > 0:
        print(f"  - 과도한 경쟁: {failures['too_much_competition']}개 지역")
        print(f"    기준: 최대 {constraints.max_competition}개 매장")
    
    if failures['low_target_match'] > 0:
        print(f"  - 타겟 고객 부족: {failures['low_target_match']}개 지역")
        print(f"    기준: 최소 {constraints.min_target_match}%")
    
    if failures['gender_mismatch'] > 0:
        print(f"  - 성별 타겟 부족: {failures['gender_mismatch']}개 지역")
        gender_str = '남성' if constraints.target_gender == 'male' else '여성'
        print(f"    기준: {gender_str} {constraints.min_gender_ratio}% 이상")
    
    print(f"\n📍 상세 탈락 지역 (상위 5개):")
    for i, detail in enumerate(failure_reasons['detailed_failures'][:5], 1):
        print(f"\n  {i}. {detail['area']}:")
        for reason in detail['reasons']:
            print(f"     - {reason}")
    
    print(f"\n💡 제안사항:")
    print("  1. 조건을 완화해보세요:")
    
    if failures['budget_mismatch'] > failures['too_much_competition']:
        print(f"     - 객단가 범위를 넓혀보세요 (예: ±20%)")
    
    if failures['too_much_competition'] > failures['budget_mismatch']:
        print(f"     - 경쟁 매장 수 기준을 높여보세요")
    
    if failures['low_target_match'] > 0:
        print(f"     - 타겟 매칭률을 낮추거나 타겟 고객을 다양화하세요")
    
    if failures['gender_mismatch'] > 0:
        print(f"     - 성별 비율 기준을 완화하세요")
    
    print("\n  2. 다른 지역을 추가로 분석해보세요")
    print("  3. 업종을 변경하여 재분석해보세요")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='창업 입지 추천')
    parser.add_argument('--areas', nargs='+', help='분석 지역')
    parser.add_argument('--no-flow', action='store_true', help='Flow 분석 제외')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    parser.add_argument('--mode', choices=['basic', 'advanced'], default='advanced',
                       help='입력 모드 (기본값: advanced)')
    
    args = parser.parse_args()
    
    # 디버그 모드 설정
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 입력
        if args.areas:
            areas = args.areas
            constraints = RealisticStartupConstraints(
                business_type='카페',
                target_customers=['직장인'],
                budget_min=5000,
                budget_max=20000,
                max_competition=50,
                min_target_match=50,
                target_gender='all',
                min_gender_ratio=40.0,
                prefer_tourist_area=False,
                prefer_office_area=False,
                prefer_residential_area=False,
                prefer_university_area=False
            )
        else:
            areas, constraints = get_user_input()
        
        print(f"\n🔄 분석 시작: {len(areas)}개 지역...")
        
        # 데이터 수집
        collector = DataCollector()
        location_data, flow_network = collector.collect_data(areas)
        
        if not location_data:
            print("\n❌ 데이터 수집 실패: API 응답이 없습니다.")
            print("   네트워크 연결을 확인하고 다시 시도해주세요.")
            return
        
        # Flow 분석
        flow_analysis = None
        if flow_network and not args.no_flow:
            try:
                flow_analysis = collector.analyze_flow(flow_network, location_data)
                print(f"🌊 Maximum Flow 분석 완료: {flow_analysis['max_flow']:,}")
            except Exception as e:
                logger.warning(f"Flow 분석 실패: {e}")
        
        # 최적화 (RealisticOptimizer 사용)
        optimizer = RealisticOptimizer()
        results = optimizer.optimize(location_data, constraints, flow_analysis)
        
        # 결과 확인
        if not results.get('pareto_optimal'):
            # 실패 원인 분석
            failure_reasons = analyze_failure_reasons(
                location_data, 
                results.get('filtered_locations', []), 
                constraints
            )
            display_failure_analysis(failure_reasons, constraints)
            
            # 조건 완화 제안
            print("\n\n🔄 조건을 완화하여 다시 분석하시겠습니까? (y/n): ", end='')
            if input().lower() == 'y':
                print("\n💡 자동으로 조건을 20% 완화하여 재분석합니다...")
                
                # 조건 완화
                relaxed_constraints = RealisticStartupConstraints(
                    business_type=constraints.business_type,
                    target_customers=constraints.target_customers,
                    budget_min=int(constraints.budget_min * 0.8),
                    budget_max=int(constraints.budget_max * 1.2),
                    max_competition=int(constraints.max_competition * 1.5),
                    min_target_match=constraints.min_target_match * 0.8,
                    # 고급 모드 필드들도 완화
                    target_gender=constraints.target_gender,
                    min_gender_ratio=constraints.min_gender_ratio * 0.8,
                    prefer_tourist_area=constraints.prefer_tourist_area,
                    prefer_office_area=constraints.prefer_office_area,
                    prefer_residential_area=constraints.prefer_residential_area,
                    prefer_university_area=constraints.prefer_university_area
                )
                
                # 재분석
                results = optimizer.optimize(location_data, relaxed_constraints, flow_analysis)
                
                if results.get('pareto_optimal'):
                    print("\n✅ 완화된 조건으로 추천 지역을 찾았습니다!")
                    # User-friendly 출력
                    output = create_user_friendly_output(results, relaxed_constraints)
                    print(output)
                else:
                    print("\n❌ 완화된 조건에서도 적합한 지역을 찾을 수 없습니다.")
                    print("   업종이나 지역을 변경하여 다시 시도해주세요.")
            
        else:
            # 성공: User-friendly 출력
            output = create_user_friendly_output(results, constraints)
            print(output)
            
            # 추가 정보 출력 (성별/상권 특성)
            print("\n" + "="*60)
            print("🔍 추가 분석 결과")
            print("="*60)
            
            # 성별 매칭 최고 지역
            if 'best_gender_match' in results['recommendations'] and constraints.target_gender != 'all':
                best_gender = results['recommendations']['best_gender_match']
                gender_str = '남성' if constraints.target_gender == 'male' else '여성'
                gender_data = best_gender.raw_data['population']['gender_distribution']
                gender_ratio = gender_data.get(constraints.target_gender, 50)
                print(f"\n👫 {gender_str} 타겟 최적 지역: {best_gender.area_name}")
                print(f"   - {gender_str} 비율: {gender_ratio:.1f}%")
            
            # 상권 특성 최고 지역
            if 'best_area_type' in results['recommendations']:
                best_area = results['recommendations']['best_area_type']
                prefs = []
                if constraints.prefer_tourist_area: prefs.append('관광지')
                if constraints.prefer_office_area: prefs.append('오피스')
                if constraints.prefer_residential_area: prefs.append('주거지')
                if constraints.prefer_university_area: prefs.append('대학가')
                if prefs:
                    print(f"\n🏙️ 상권 특성 최적 지역: {best_area.area_name}")
                    print(f"   - 선호 상권: {', '.join(prefs)}")
                    print(f"   - 매칭 점수: {best_area.area_type_score:.1f}")
        
        # 저장 옵션
        save = input("\n\n💾 분석 결과를 저장하시겠습니까? (y/n): ").lower() == 'y'
        if save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 1. 상세 JSON 저장
            filename_json = f"results_{timestamp}.json"
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'mode': args.mode,
                'constraints': {
                    'business_type': constraints.business_type,
                    'target_customers': constraints.target_customers,
                    'budget_min': constraints.budget_min,
                    'budget_max': constraints.budget_max,
                    'max_competition': constraints.max_competition,
                    'min_target_match': constraints.min_target_match,
                    'target_gender': constraints.target_gender,
                    'min_gender_ratio': constraints.min_gender_ratio,
                    'prefer_tourist_area': constraints.prefer_tourist_area,
                    'prefer_office_area': constraints.prefer_office_area,
                    'prefer_residential_area': constraints.prefer_residential_area,
                    'prefer_university_area': constraints.prefer_university_area
                },
                'summary': {
                    'total': len(results.get('all_locations', [])),
                    'filtered': len(results.get('filtered_locations', [])),
                    'pareto': len(results.get('pareto_optimal', []))
                },
                'top_locations': [
                    {
                        'area': loc.area_name,
                        'scores': {
                            'profitability': loc.profitability,
                            'stability': loc.stability,
                            'accessibility': loc.accessibility,
                            'network': loc.network_efficiency,
                            'gender_match': loc.gender_match_score,
                            'area_type': loc.area_type_score
                        },
                        'flow': loc.flow_data
                    }
                    for loc in results.get('pareto_optimal', [])[:10]
                ]
            }
            
            with open(filename_json, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 2. 보고서 텍스트 저장
            filename_txt = f"report_{timestamp}.txt"
            with open(filename_txt, 'w', encoding='utf-8') as f:
                if results.get('pareto_optimal'):
                    report_output = create_user_friendly_output(results, constraints)
                    f.write(report_output)
                else:
                    f.write("조건을 만족하는 지역을 찾을 수 없습니다.\n")
            
            print(f"\n✅ 저장 완료:")
            print(f"   - 상세 데이터: {filename_json}")
            print(f"   - 분석 보고서: {filename_txt}")
        
        print("\n\n감사합니다! 창업 성공을 기원합니다! 🎉")
        
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
    except Exception as e:
        logger.error(f"오류: {e}", exc_info=True)
        print(f"\n❌ 오류가 발생했습니다: {e}")
        print("   로그 파일(startup_analysis.log)을 확인해주세요.")


if __name__ == "__main__":
    main()