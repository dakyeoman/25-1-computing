import streamlit as st
import pandas as pd
import json
from datetime import datetime

# 기존 모듈 import
from data_collector_final_updated import DataCollector
from realistic_optimizer import RealisticOptimizer, RealisticStartupConstraints
from prev_0602.report_generator import ReportGenerator, create_user_friendly_output
from prev_0602.seoul_api_client import Config

# 페이지 설정
st.set_page_config(
    page_title="서울시 창업 입지 추천 시스템",
    page_icon="🏪",
    layout="wide"
)

# 헬퍼 함수들을 먼저 정의
def _display_all_areas_tab(results, constraints):
    """전체 지역 목록 표시"""
    st.subheader("📍 전체 분석 지역 목록")
    
    all_scored = results.get('scored_locations', [])
    if all_scored:
        # 정렬 옵션
        sort_by = st.selectbox(
            "정렬 기준",
            ["종합점수", "수익성", "안정성", "접근성", "지역명"]
        )
        
        # 필터 옵션
        col1, col2 = st.columns(2)
        with col1:
            min_score = st.slider("최소 종합점수", 0, 300, 0)
        with col2:
            show_only_pareto = st.checkbox("파레토 최적해만 표시", value=False)
        
        # 데이터 준비
        all_data = []
        pareto_areas = [loc.area_name for loc in results.get('pareto_optimal', [])]
        
        for loc in all_scored:
            total_score = loc.profitability + loc.stability + loc.accessibility
            if total_score >= min_score:
                if not show_only_pareto or loc.area_name in pareto_areas:
                    all_data.append({
                        "지역명": loc.area_name,
                        "수익성": f"{loc.profitability:.1f}",
                        "안정성": f"{loc.stability:.1f}",
                        "접근성": f"{loc.accessibility:.1f}",
                        "종합점수": f"{total_score:.1f}",
                        "파레토": "✅" if loc.area_name in pareto_areas else "❌"
                    })
        
        if all_data:
            all_df = pd.DataFrame(all_data)
            
            # 정렬
            if sort_by == "종합점수":
                all_df['정렬키'] = all_df['종합점수'].str.replace('.', '').astype(float)
                all_df = all_df.sort_values('정렬키', ascending=False).drop('정렬키', axis=1)
            elif sort_by == "수익성":
                all_df['정렬키'] = all_df['수익성'].str.replace('.', '').astype(float)
                all_df = all_df.sort_values('정렬키', ascending=False).drop('정렬키', axis=1)
            elif sort_by == "안정성":
                all_df['정렬키'] = all_df['안정성'].str.replace('.', '').astype(float)
                all_df = all_df.sort_values('정렬키', ascending=False).drop('정렬키', axis=1)
            elif sort_by == "접근성":
                all_df['정렬키'] = all_df['접근성'].str.replace('.', '').astype(float)
                all_df = all_df.sort_values('정렬키', ascending=False).drop('정렬키', axis=1)
            else:  # 지역명
                all_df = all_df.sort_values('지역명')
            
            st.info(f"총 {len(all_df)}개 지역 표시 중")
            st.dataframe(all_df, use_container_width=True, hide_index=True)
        else:
            st.warning("조건에 맞는 지역이 없습니다.")

def _display_save_tab(results, constraints, pareto_optimal, all_locations, filtered_locations):
    """데이터 저장 탭"""
    st.subheader("💾 분석 결과 저장")
    
    # 보고서 생성
    if pareto_optimal:
        generator = ReportGenerator()
        report = generator.generate_comprehensive_report(results, constraints)
        
        # JSON 형식으로 저장 데이터 준비
        save_data = {
            "분석일시": report['generated_at'],
            "분석설정": {
                "업종": constraints.business_type,
                "타겟고객": constraints.target_customers,
                "예산범위": f"{constraints.budget_min:,}~{constraints.budget_max:,}원",
                "최대경쟁": constraints.max_competition,
                "최소타겟매칭": f"{constraints.min_target_match}%",
                "성별타겟": constraints.target_gender,
                "최소성별비율": f"{constraints.min_gender_ratio}%" if constraints.target_gender != 'all' else "N/A",
                "상권선호": {
                    "관광지": constraints.prefer_tourist_area,
                    "오피스": constraints.prefer_office_area,
                    "주거지": constraints.prefer_residential_area,
                    "대학가": constraints.prefer_university_area
                }
            },
            "분석요약": {
                "전체지역": len(all_locations),
                "조건충족": len(filtered_locations),
                "파레토최적": len(pareto_optimal),
                "Flow분석": "포함" if st.session_state.get('use_flow', False) else "미포함"
            },
            "추천지역": report.get('top_recommendations', [])
        }
        
        # 다운로드 버튼들
        col1, col2 = st.columns(2)
        
        with col1:
            # JSON 다운로드
            json_str = json.dumps(save_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 JSON 파일 다운로드",
                data=json_str,
                file_name=f"startup_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            # 텍스트 보고서 다운로드
            text_report = create_user_friendly_output(results, constraints)
            st.download_button(
                label="📄 텍스트 보고서 다운로드",
                data=text_report,
                file_name=f"startup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # 상세 데이터 다운로드 옵션
        with st.expander("📊 상세 데이터 다운로드"):
            # 전체 점수 데이터
            if results.get('scored_locations'):
                scores_data = []
                for loc in results['scored_locations']:
                    scores_data.append({
                        "지역명": loc.area_name,
                        "수익성": loc.profitability,
                        "안정성": loc.stability,
                        "접근성": loc.accessibility,
                        "네트워크효율": loc.network_efficiency,
                        "종합점수": loc.profitability + loc.stability + loc.accessibility,
                        "유동인구점수": loc.population_score,
                        "결제활성도": loc.payment_activity_score,
                        "타겟매칭": loc.target_match_score,
                        "경쟁적정성": loc.competition_score,
                        "예산적합도": loc.budget_fit_score,
                        "성별매칭": loc.gender_match_score,
                        "상권특성": loc.area_type_score
                    })
                
                scores_df = pd.DataFrame(scores_data)
                csv = scores_df.to_csv(index=False, encoding='utf-8-sig')
                
                st.download_button(
                    label="📊 전체 점수 데이터 (CSV)",
                    data=csv,
                    file_name=f"startup_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        # 보고서 미리보기
        st.markdown("---")
        st.markdown("### 📋 보고서 미리보기")
        
        if report.get('top_recommendations'):
            for i, rec in enumerate(report['top_recommendations'][:3], 1):
                with st.expander(f"{rec['rank']}위. {rec['area']} {rec['level']}"):
                    st.write(f"**{rec['one_line_summary']}**")
                    st.write(f"- 예상 월매출: {rec['expected_monthly_revenue']}")
                    st.write(f"- 예상 일고객: {rec['expected_daily_customers']}")
                    st.write(f"- 경쟁상황: {rec['competition']}")
                    
                    if rec.get('best_features'):
                        st.write("**주요 강점:**")
                        for feature in rec['best_features']:
                            st.write(f"  - {feature}")
                    
                    if rec.get('quick_tips'):
                        st.write("**창업 팁:**")
                        for tip in rec['quick_tips']:
                            st.write(f"  - {tip}")
    else:
        st.warning("저장할 분석 결과가 없습니다. 먼저 분석을 실행해주세요.")

# 메인 UI 시작
st.title("🏪 서울시 창업 입지 추천 시스템")
st.markdown("Maximum Flow 기반 다중 기준 의사결정 시스템")

# 세션 상태 초기화
if 'results' not in st.session_state:
    st.session_state.results = None
if 'analyzing' not in st.session_state:
    st.session_state.analyzing = False

# 사이드바 입력
with st.sidebar:
    st.header("📋 창업 조건 설정")
    
    # 업종 선택
    business_type = st.selectbox(
        "업종 선택",
        ["카페", "음식점", "주점", "편의점", "학원", "미용실", "약국", "헬스장"]
    )
    
    # 타겟 고객
    target_customers = st.multiselect(
        "타겟 고객",
        ["직장인", "학생", "주민", "관광객"],
        default=["직장인"]
    )
    
    # 예산 범위
    st.write("목표 객단가 (원)")
    col1, col2 = st.columns(2)
    with col1:
        budget_min = st.number_input("최소", value=5000, step=1000, min_value=1000)
    with col2:
        budget_max = st.number_input("최대", value=15000, step=1000, min_value=1000)
    
    # 경쟁 및 타겟
    max_competition = st.number_input(
        "최대 허용 경쟁 매장 수",
        value=50,
        min_value=1,
        max_value=200
    )
    
    min_target_match = st.slider(
        "최소 타겟 매칭률 (%)",
        min_value=0,
        max_value=100,
        value=50
    )
    
    # 고급 옵션
    with st.expander("고급 옵션"):
        target_gender = st.radio(
            "성별 타겟",
            ["all", "male", "female"],
            format_func=lambda x: {"all": "전체", "male": "남성 중심", "female": "여성 중심"}[x]
        )
        
        min_gender_ratio = 40.0
        if target_gender != "all":
            min_gender_ratio = st.slider(
                "최소 성별 비율 (%)",
                min_value=40,
                max_value=90,
                value=60
            )
        
        st.write("선호 상권 특성")
        col1, col2 = st.columns(2)
        with col1:
            prefer_tourist = st.checkbox("관광지")
            prefer_office = st.checkbox("오피스 지역")
        with col2:
            prefer_residential = st.checkbox("주거 지역")
            prefer_university = st.checkbox("대학가")
    
    # 지역 선택
    st.markdown("### 🗺️ 분석 지역 선택")
    area_option = st.radio(
        "분석 범위",
        ["주요 5개 (빠른 테스트)", "주요 20개 (일반 분석)", "전체 82개 (전체 분석)", "사용자 선택"]
    )
    
    use_flow = True  # 기본값
    
    if area_option == "사용자 선택":
        selected_areas = st.multiselect(
            "지역 선택 (최대 82개)",
            Config.AVAILABLE_AREAS,
            default=Config.TEST_AREAS
        )
        st.info(f"선택된 지역: {len(selected_areas)}개")
    elif area_option == "주요 5개 (빠른 테스트)":
        selected_areas = Config.TEST_AREAS
        st.info("빠른 테스트를 위한 5개 주요 지역")
    elif area_option == "주요 20개 (일반 분석)":
        selected_areas = Config.AVAILABLE_AREAS[:20]
        st.info("상위 20개 주요 지역 분석")
    else:  # "전체 82개 (전체 분석)"
        selected_areas = Config.AVAILABLE_AREAS
        st.warning("⚠️ 82개 전체 지역 분석은 5-10분 정도 소요될 수 있습니다.")
        use_flow = st.checkbox("Flow Network 분석 포함", value=False)
        st.caption("Flow 분석을 제외하면 속도가 빨라집니다.")
    
    # 선택된 지역 표시
    with st.expander("선택된 지역 목록 보기"):
        for i, area in enumerate(selected_areas, 1):
            st.text(f"{i}. {area}")
    
    # 분석 버튼
    st.markdown("---")
    analyze_button = st.button("🔍 분석 시작", type="primary", use_container_width=True)

# 메인 영역
if analyze_button and not st.session_state.analyzing:
    st.session_state.analyzing = True
    
    # 진행 상황 표시
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    try:
        # 1. 데이터 수집
        status_placeholder.text(f"🔄 {len(selected_areas)}개 지역 데이터 수집 중...")
        progress_bar.progress(10)
        
        collector = DataCollector()
        
        # Flow 분석 여부에 따라 다르게 처리
        if not use_flow:
            # Flow 분석 없이 데이터만 수집
            location_data = []
            for i, area in enumerate(selected_areas):
                try:
                    pop_data = collector.seoul_client.get_population_data(area)
                    com_data = collector.seoul_client.get_commercial_data(area)
                    
                    if pop_data and com_data:
                        location_data.append({
                            'area_name': area,
                            'population': pop_data,
                            'commercial': com_data,
                            'sales': None
                        })
                        status_placeholder.text(f"✅ {area} 수집 완료 ({i+1}/{len(selected_areas)})")
                    
                    # 진행률 업데이트
                    progress = 10 + (40 * (i + 1) / len(selected_areas))
                    progress_bar.progress(int(progress))
                    
                except Exception as e:
                    st.warning(f"⚠️ {area} 데이터 수집 실패: {str(e)}")
            
            flow_network = None
            flow_analysis = None
        else:
            # Flow 분석 포함 수집
            location_data, flow_network = collector.collect_data(selected_areas)
            progress_bar.progress(50)
        
        if not location_data:
            st.error("데이터 수집 실패. API 연결을 확인해주세요.")
            st.stop()
        
        status_placeholder.text(f"✅ {len(location_data)}개 지역 데이터 수집 완료")
        
        # 2. Flow 분석 (선택적)
        flow_analysis = None
        if use_flow and flow_network:
            status_placeholder.text("🌊 Flow Network 분석 중...")
            progress_bar.progress(60)
            
            flow_analysis = collector.analyze_flow(flow_network, location_data)
            if flow_analysis:
                status_placeholder.text(f"✅ Maximum Flow: {flow_analysis['max_flow']:,}")
        
        # 3. 최적화
        status_placeholder.text("🎯 파레토 최적해 계산 중...")
        progress_bar.progress(70)
        
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
            prefer_tourist_area=prefer_tourist,
            prefer_office_area=prefer_office,
            prefer_residential_area=prefer_residential,
            prefer_university_area=prefer_university
        )
        
        optimizer = RealisticOptimizer()
        results = optimizer.optimize(location_data, constraints, flow_analysis)
        
        # 결과 저장
        st.session_state.results = results
        st.session_state.constraints = constraints
        st.session_state.location_data = location_data
        st.session_state.flow_analysis = flow_analysis
        st.session_state.use_flow = use_flow
        
        progress_bar.progress(100)
        status_placeholder.text("✅ 분석 완료!")
        
    except Exception as e:
        st.error(f"분석 중 오류 발생: {str(e)}")
        import traceback
        with st.expander("상세 오류 정보"):
            st.code(traceback.format_exc())
    
    finally:
        st.session_state.analyzing = False

# 결과 표시
if st.session_state.results:
    results = st.session_state.results
    constraints = st.session_state.constraints
    
    # 파레토 최적해 가져오기
    pareto_optimal = results.get('pareto_optimal', [])
    filtered_locations = results.get('filtered_locations', [])
    all_locations = results.get('all_locations', [])
    
    # 요약 정보
    st.markdown("### 📊 분석 요약")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("전체 지역", f"{len(all_locations)}개")
    with col2:
        st.metric("조건 충족", f"{len(filtered_locations)}개")
    with col3:
        st.metric("파레토 최적해", f"{len(pareto_optimal)}개")
    with col4:
        if st.session_state.flow_analysis:
            st.metric("Max Flow", f"{st.session_state.flow_analysis['max_flow']:,}")
        else:
            st.metric("Flow 분석", "미사용")
    
    # 탭 구성
    if st.session_state.use_flow:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 추천 결과", "📈 상세 분석", "🌊 Flow 분석", "📍 전체 지역 목록", "💾 데이터 저장"])
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 추천 결과", "📈 상세 분석", "📍 전체 지역 목록", "💾 데이터 저장"])
    
    with tab1:
        if pareto_optimal:
            st.subheader(f"🏆 추천 지역 (전체 {len(pareto_optimal)}개)")
            
            # 표시할 개수 선택
            if len(pareto_optimal) > 10:
                show_count = st.slider(
                    "표시할 지역 수", 
                    min_value=5, 
                    max_value=min(50, len(pareto_optimal)), 
                    value=min(20, len(pareto_optimal))
                )
            else:
                show_count = len(pareto_optimal)
            
            # ReportGenerator를 사용하여 정확한 예상 매출 계산
            generator = ReportGenerator()
            
            # 결과 테이블 생성
            with st.spinner("상세 분석 중..."):
                data = []
                for i, loc in enumerate(pareto_optimal[:show_count], 1):
                    # 정확한 예상 고객수와 매출 계산
                    insight = generator._analyze_location(loc, constraints)
                    
                    data.append({
                        "순위": i,
                        "지역명": loc.area_name,
                        "수익성": f"{loc.profitability:.1f}",
                        "안정성": f"{loc.stability:.1f}",
                        "접근성": f"{loc.accessibility:.1f}",
                        "네트워크 효율": f"{loc.network_efficiency:.1f}%",
                        "종합점수": f"{loc.profitability + loc.stability + loc.accessibility:.1f}",
                        "예상 일 고객": f"{insight.expected_daily_customers:,}명",
                        "예상 월매출": f"{insight.expected_monthly_revenue:,}원",
                        "추천등급": insight.recommendation_level
                    })
            
            df = pd.DataFrame(data)
            
            # 스타일링된 데이터프레임 (열 너비 조정)
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "순위": st.column_config.NumberColumn(width="small"),
                    "지역명": st.column_config.TextColumn(width="medium"),
                    "수익성": st.column_config.NumberColumn(width="small"),
                    "안정성": st.column_config.NumberColumn(width="small"),
                    "접근성": st.column_config.NumberColumn(width="small"),
                    "네트워크 효율": st.column_config.TextColumn(width="small"),
                    "종합점수": st.column_config.TextColumn(width="small"),
                    "추천등급": st.column_config.TextColumn(width="medium")
                }
            )
            
            # 1위 지역 상세
            st.markdown("---")
            st.subheader("🥇 최우수 추천 지역 상세 분석")
            
            top = pareto_optimal[0]
            top_insight = generator._analyze_location(top, constraints)
            
            # 성공 메시지와 함께 지역명 강조
            st.success(f"🏆 **{top.area_name}** - {top_insight.one_line_summary if hasattr(top_insight, 'one_line_summary') else '최적의 창업 입지입니다!'}")
            
            # 3개 컬럼으로 주요 정보 표시
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("##### 📊 주요 지표")