"""
카페 창업 입지 추천 시스템 - Streamlit Web App
간단하고 실용적인 웹 인터페이스

실행 방법:
1. pip install streamlit pandas plotly
2. streamlit run cafe_app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# 메인 코드 임포트 (main__.py가 같은 디렉토리에 있다고 가정)
from main__ import (
    CafeLocationOptimizer, UserPreferences, Config,
    GenderTarget, CompetitionLevel, SubwayPreference,
    PeakTime, WeekdayPreference, PriceRange,
    format_korean_number
)

# 페이지 설정
st.set_page_config(
    page_title="카페 창업 입지 추천 시스템",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 2rem;
        text-align: center;
        color: #1976D2;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .recommendation-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 5px solid #1976D2;
    }
    .stButton > button {
        width: 100%;
        height: 3rem;
        font-size: 1.2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'optimizer' not in st.session_state:
    st.session_state.optimizer = None
    st.session_state.data_loaded = False
    st.session_state.recommendations = []
    st.session_state.analysis_done = False

# 헤더
st.markdown('<h1 class="main-header">☕ 카페 창업 입지 추천 시스템</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">서울시 빅데이터 기반 최적 카페 창업 입지 분석</p>', unsafe_allow_html=True)

# 데이터 경로 설정
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
    'od_folders': ['.', 'seoul_purpose_admdong1_in_202502', 'seoul_purpose_admdong1_in_202503']
}

# 사이드바 - 필터 설정
with st.sidebar:
    st.markdown("## 🔍 분석 조건 설정")
    st.markdown("---")
    
    # 매출 범위
    st.markdown("### 💰 희망 매출 범위")
    col1, col2 = st.columns(2)
    with col1:
        min_revenue = st.number_input(
            "최소 (만원)",
            min_value=0,
            max_value=100000,
            value=2000,
            step=500
        )
    with col2:
        max_revenue = st.number_input(
            "최대 (만원)",
            min_value=0,
            max_value=100000,
            value=50000,
            step=1000
        )
    
    st.markdown(f"선택 범위: **{format_korean_number(min_revenue*10000)}** ~ **{format_korean_number(max_revenue*10000)}**")
    
    # 타겟 고객
    st.markdown("### 👥 타겟 고객")
    gender_target = st.selectbox(
        "주요 고객 성별",
        options=["상관없음", "여성 중심", "남성 중심", "균형"],
        index=0
    )
    
    price_range = st.selectbox(
        "희망 객단가",
        options=["상관없음", "저가 (~5천원)", "중저가 (5~8천원)", 
                "중가 (8~12천원)", "중고가 (12~15천원)", "고가 (15천원~)"],
        index=0
    )
    
    # 경쟁 환경
    st.markdown("### 🏪 경쟁 환경")
    competition = st.selectbox(
        "선호하는 경쟁 환경",
        options=["상관없음", "블루오션 (카페 ~10개)", 
                "적당한 경쟁 (11~30개)", "경쟁 활발 (31~50개)"],
        index=0
    )
    
    min_stores = st.slider(
        "최소 점포수 (데이터 신뢰도)",
        min_value=1,
        max_value=10,
        value=3
    )
    
    # 입지 조건
    st.markdown("### 🚇 입지 조건")
    subway = st.selectbox(
        "지하철 접근성",
        options=["상관없음", "필수", "선호"],
        index=0
    )
    
    # 운영 조건
    st.markdown("### ⏰ 운영 조건")
    peak_time = st.selectbox(
        "주력 시간대",
        options=["균형", "출근 (06-11시)", "점심 (11-14시)", 
                "오후 (14-17시)", "저녁 (17-21시)"],
        index=0
    )
    
    weekday = st.selectbox(
        "주중/주말 선호",
        options=["균형", "주중 중심", "주말 중심"],
        index=0
    )
    
    st.markdown("---")
    
    # 분석 버튼
    analyze_button = st.button("🚀 입지 분석 시작", type="primary")

# 메인 영역
def load_data():
    """데이터 로드"""
    if not st.session_state.data_loaded:
        with st.spinner("📊 데이터를 불러오는 중... (최초 1회만 실행됩니다)"):
            progress_bar = st.progress(0)
            
            try:
                # 옵티마이저 초기화
                config = Config()
                st.session_state.optimizer = CafeLocationOptimizer(config)
                progress_bar.progress(30)
                
                # 데이터 로드
                st.session_state.optimizer.load_data(data_paths)
                progress_bar.progress(100)
                
                st.session_state.data_loaded = True
                st.success("✅ 데이터 로드 완료!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 데이터 로드 실패: {str(e)}")
                st.stop()

def create_user_preferences():
    """사용자 설정을 UserPreferences 객체로 변환"""
    preferences = UserPreferences()
    
    # 매출 범위
    preferences.min_revenue = min_revenue
    preferences.max_revenue = max_revenue
    
    # 성별 타겟
    gender_map = {
        "여성 중심": GenderTarget.FEMALE_CENTERED,
        "남성 중심": GenderTarget.MALE_CENTERED,
        "균형": GenderTarget.BALANCED,
        "상관없음": GenderTarget.ANY
    }
    preferences.gender_target = gender_map.get(gender_target, GenderTarget.ANY)
    
    # 경쟁 환경
    comp_map = {
        "블루오션 (카페 ~10개)": CompetitionLevel.BLUE_OCEAN,
        "적당한 경쟁 (11~30개)": CompetitionLevel.MODERATE,
        "경쟁 활발 (31~50개)": CompetitionLevel.COMPETITIVE,
        "상관없음": CompetitionLevel.ANY
    }
    preferences.competition = comp_map.get(competition, CompetitionLevel.ANY)
    
    # 지하철
    subway_map = {
        "필수": SubwayPreference.REQUIRED,
        "선호": SubwayPreference.PREFERRED,
        "상관없음": SubwayPreference.ANY
    }
    preferences.subway = subway_map.get(subway, SubwayPreference.ANY)
    
    # 시간대
    time_map = {
        "출근 (06-11시)": PeakTime.MORNING,
        "점심 (11-14시)": PeakTime.LUNCH,
        "오후 (14-17시)": PeakTime.AFTERNOON,
        "저녁 (17-21시)": PeakTime.EVENING,
        "균형": PeakTime.BALANCED
    }
    preferences.peak_time = time_map.get(peak_time, PeakTime.BALANCED)
    
    # 주중/주말
    weekday_map = {
        "주중 중심": WeekdayPreference.WEEKDAY,
        "주말 중심": WeekdayPreference.WEEKEND,
        "균형": WeekdayPreference.BALANCED
    }
    preferences.weekday_preference = weekday_map.get(weekday, WeekdayPreference.BALANCED)
    
    # 객단가
    price_map = {
        "저가 (~5천원)": PriceRange.LOW,
        "중저가 (5~8천원)": PriceRange.MID_LOW,
        "중가 (8~12천원)": PriceRange.MID,
        "중고가 (12~15천원)": PriceRange.MID_HIGH,
        "고가 (15천원~)": PriceRange.HIGH,
        "상관없음": PriceRange.ANY
    }
    preferences.price_range = price_map.get(price_range, PriceRange.ANY)
    
    # 최소 점포수
    preferences.min_stores = min_stores
    
    return preferences

def run_analysis():
    """분석 실행"""
    with st.spinner("🔍 최적 입지를 분석하는 중..."):
        progress_bar = st.progress(0)
        
        # 사용자 설정
        preferences = create_user_preferences()
        progress_bar.progress(30)
        
        # 분석 실행
        recommendations = st.session_state.optimizer.recommend_locations(preferences, top_n=5)
        progress_bar.progress(90)
        
        st.session_state.recommendations = recommendations
        st.session_state.analysis_done = True
        progress_bar.progress(100)
        
        if recommendations:
            st.success(f"✅ 분석 완료! {len(recommendations)}개의 추천 지역을 찾았습니다.")
        else:
            st.warning("⚠️ 조건에 맞는 지역을 찾을 수 없습니다. 조건을 완화해보세요.")

def display_results():
    """결과 표시"""
    if not st.session_state.recommendations:
        st.info("📍 좌측에서 조건을 설정하고 '입지 분석 시작' 버튼을 클릭하세요.")
        return
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 추천 결과", "📈 비교 분석", "🗺️ 지도", "💡 인사이트"])
    
    with tab1:
        display_recommendations()
    
    with tab2:
        display_comparison()
    
    with tab3:
        display_map()
    
    with tab4:
        display_insights()

def display_recommendations():
    """추천 결과 표시"""
    st.markdown("## 🏆 카페 창업 추천 입지 TOP 5")
    
    for i, rec in enumerate(st.session_state.recommendations):
        rank = i + 1
        
        # 순위별 색상
        rank_colors = {1: "#4CAF50", 2: "#2196F3", 3: "#FF9800", 4: "#9E9E9E", 5: "#757575"}
        rank_color = rank_colors.get(rank, "#757575")
        
        # 추천 카드
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 2])
            
            with col1:
                st.markdown(f"""
                <div style="text-align: center; font-size: 3rem; font-weight: bold; color: {rank_color};">
                    #{rank}
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"### {rec.dong_name}")
                st.markdown(f"**{rec.gu_name}** | 점수: ⭐ {rec.score:.2f}")
                
                # 핵심 지표
                cols = st.columns(4)
                with cols[0]:
                    st.metric("월평균 매출", rec.format_revenue(rec.avg_revenue_per_store).split('(')[0])
                with cols[1]:
                    st.metric("카페 수", f"{rec.store_count}개")
                with cols[2]:
                    st.metric("폐업률", f"{rec.closure_rate*100:.1f}%")
                with cols[3]:
                    st.metric("지하철", "⭕" if rec.subway_access else "❌")
            
            with col3:
                # 상세보기 버튼
                if st.button(f"상세 분석 보기", key=f"detail_{rank}"):
                    st.session_state.selected_dong = rec
                    st.session_state.show_detail = True
                
                # 간단 차트
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = rec.score * 100,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "종합 점수"},
                    gauge = {
                        'axis': {'range': [None, 100]},
                        'bar': {'color': rank_color},
                        'steps': [
                            {'range': [0, 50], 'color': "lightgray"},
                            {'range': [50, 80], 'color': "gray"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 90
                        }
                    }
                ))
                fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")

def display_comparison():
    """비교 분석 표시"""
    if not st.session_state.recommendations:
        return
    
    st.markdown("## 📊 추천 지역 비교 분석")
    
    # 데이터 준비
    df_data = []
    for i, rec in enumerate(st.session_state.recommendations):
        df_data.append({
            '지역': f"{rec.dong_name}",
            '순위': i + 1,
            '월평균 매출': rec.avg_revenue_per_store / 10000,  # 만원 단위
            '카페 수': rec.store_count,
            '폐업률': rec.closure_rate * 100,
            '여성 비율': rec.female_ratio * 100,
            '객단가': rec.avg_price,
            '종합 점수': rec.score * 100
        })
    
    df = pd.DataFrame(df_data)
    
    # 차트 1: 매출 비교
    col1, col2 = st.columns(2)
    
    with col1:
        fig1 = px.bar(df, x='지역', y='월평균 매출', 
                     title='월평균 매출 비교 (만원)',
                     color='월평균 매출',
                     color_continuous_scale='Blues')
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        fig2 = px.scatter(df, x='카페 수', y='월평균 매출',
                         size='종합 점수', color='지역',
                         title='경쟁 환경 vs 매출',
                         hover_data=['객단가'])
        st.plotly_chart(fig2, use_container_width=True)
    
    # 차트 3: 레이더 차트
    st.markdown("### 🎯 종합 비교")
    
    categories = ['매출', '안정성', '경쟁력', '고객', '접근성']
    
    fig3 = go.Figure()
    
    for i, rec in enumerate(st.session_state.recommendations[:3]):  # 상위 3개만
        values = [
            rec.avg_revenue_per_store / 500000000 * 100,  # 정규화
            (1 - rec.closure_rate) * 100,
            100 - min(rec.store_count / 50 * 100, 100),
            rec.female_ratio * 100,
            100 if rec.subway_access else 50
        ]
        
        fig3.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name=rec.dong_name
        ))
    
    fig3.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=True,
        title="상위 3개 지역 종합 비교"
    )
    
    st.plotly_chart(fig3, use_container_width=True)

def display_map():
    """지도 표시"""
    st.markdown("## 🗺️ 추천 지역 위치")
    
    # 간단한 안내
    st.info("📍 서울시 공식 지도 서비스에서 더 자세한 위치를 확인하실 수 있습니다.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗺️ 서울시 지도 열기"):
            st.markdown("[서울시 지도 서비스](https://map.seoul.go.kr)")
    with col2:
        if st.button("🏪 상권분석 서비스"):
            st.markdown("[서울시 우리마을가게 상권분석서비스](https://golmok.seoul.go.kr)")
    with col3:
        if st.button("📊 서울 열린데이터광장"):
            st.markdown("[서울 열린데이터광장](https://data.seoul.go.kr)")
    
    # 추천 지역 리스트
    st.markdown("### 📌 추천 지역 목록")
    for i, rec in enumerate(st.session_state.recommendations):
        st.write(f"{i+1}. **{rec.dong_name}** ({rec.gu_name})")

def display_insights():
    """인사이트 표시"""
    st.markdown("## 💡 분석 인사이트")
    
    if not st.session_state.recommendations:
        return
    
    # 전체 분석 인사이트
    st.info(f"""
    📊 **분석 결과 요약**
    - 설정하신 조건에 맞는 {len(st.session_state.recommendations)}개 지역을 찾았습니다.
    - 1위 지역인 **{st.session_state.recommendations[0].dong_name}**의 평균 매출은 **{format_korean_number(int(st.session_state.recommendations[0].avg_revenue_per_store))}**입니다.
    """)
    
    # 최고 매출 지역
    top_revenue = max(st.session_state.recommendations, key=lambda x: x.avg_revenue_per_store)
    st.success(f"""
    💰 **최고 매출 지역**
    - **{top_revenue.dong_name}**이(가) 점포당 평균 **{format_korean_number(int(top_revenue.avg_revenue_per_store))}**의 매출을 기록하여 가장 높습니다.
    """)
    
    # 경쟁 환경
    min_competition = min(st.session_state.recommendations, key=lambda x: x.store_count)
    st.info(f"""
    🌊 **블루오션 지역**
    - **{min_competition.dong_name}**은(는) 카페가 **{min_competition.store_count}개**로 경쟁이 가장 적은 지역입니다.
    """)
    
    # 안정성
    min_closure = min(st.session_state.recommendations, key=lambda x: x.closure_rate)
    st.success(f"""
    🛡️ **가장 안정적인 지역**
    - **{min_closure.dong_name}**의 폐업률은 **{min_closure.closure_rate*100:.1f}%**로 가장 낮습니다.
    """)
    
    # 추가 팁
    st.markdown("### 💡 창업 성공 팁")
    
    tips = [
        "📍 **입지 선정 후 현장 답사는 필수입니다.** 평일/주말, 다양한 시간대에 방문해보세요.",
        "💰 **초기 투자금은 여유있게 준비하세요.** 예상 비용의 1.5배를 권장합니다.",
        "☕ **차별화된 콘셉트가 중요합니다.** 주변 카페를 분석하고 독특한 포인트를 만드세요.",
        "👥 **타겟 고객을 명확히 하세요.** 모든 사람을 만족시킬 순 없습니다.",
        "📱 **온라인 마케팅을 준비하세요.** SNS는 필수, 배달앱 입점도 고려해보세요."
    ]
    
    for tip in tips:
        st.write(tip)

# 메인 실행
if not st.session_state.data_loaded:
    load_data()
else:
    if analyze_button:
        run_analysis()
    
    display_results()

# 푸터
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>© 2024 Seoul Cafe Location Optimizer | Seoul Data Analysis Team</p>
    <p>데이터 출처: 서울 열린데이터광장</p>
</div>
""", unsafe_allow_html=True)