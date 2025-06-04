"""
카페 창업 입지 추천 시스템 - Streamlit Web App
반응형 디자인 & 상세 분석 통합 버전

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

# 반응형 CSS 스타일
st.markdown("""
<style>
    /* 반응형 기본 설정 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* 메인 헤더 반응형 */
    .main-header {
        font-size: clamp(1.8rem, 5vw, 2.5rem);
        font-weight: bold;
        margin-bottom: 1.5rem;
        text-align: center;
        color: #1976D2;
    }
    
    .sub-header {
        font-size: clamp(1rem, 3vw, 1.2rem);
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    
    /* 카드 스타일 */
    .recommendation-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-left: 5px solid #1976D2;
        transition: all 0.3s ease;
    }
    
    .recommendation-card:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    /* 순위 뱃지 */
    .rank-badge {
        font-size: clamp(2rem, 4vw, 3rem);
        font-weight: bold;
        text-align: center;
        padding: 0.5rem;
    }
    
    /* 메트릭 카드 */
    .metric-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        height: 100%;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #666;
        margin-bottom: 0.3rem;
    }
    
    .metric-value {
        font-size: 1.2rem;
        font-weight: bold;
        color: #333;
    }
    
    /* 확장 가능한 섹션 */
    .expandable-section {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-top: 1rem;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* 모바일 반응형 */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        
        .recommendation-card {
            padding: 1rem;
        }
        
        [data-testid="column"] {
            padding: 0.2rem !important;
        }
    }
    
    /* 태블릿 반응형 */
    @media (min-width: 768px) and (max-width: 1024px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    
    /* 상세 분석 섹션 */
    .detail-section {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin-top: 1rem;
    }
    
    .chart-container {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    /* 인사이트 박스 */
    .insight-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1976D2;
        margin-bottom: 0.8rem;
    }
    
    /* 성공/경고/정보 색상 */
    .success-box {
        background-color: #e8f5e9;
        border-left-color: #4CAF50;
    }
    
    .warning-box {
        background-color: #fff3e0;
        border-left-color: #FF9800;
    }
    
    .info-box {
        background-color: #e3f2fd;
        border-left-color: #2196F3;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'optimizer' not in st.session_state:
    st.session_state.optimizer = None
    st.session_state.data_loaded = False
    st.session_state.recommendations = []
    st.session_state.analysis_done = False
    st.session_state.expanded_cards = set()

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
    analyze_button = st.button("🚀 입지 분석 시작", type="primary", use_container_width=True)

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

def format_number_for_display(value, type="currency"):
    """숫자를 사용자 친화적으로 포맷팅"""
    if type == "currency":
        if value >= 100000000:  # 1억 이상
            return f"{value/100000000:.1f}억원"
        elif value >= 10000000:  # 1천만원 이상
            return f"{value/10000000:.1f}천만원"
        elif value >= 10000:  # 1만원 이상
            return f"{value/10000:.0f}만원"
        else:
            return f"{value:,.0f}원"
    elif type == "count":
        return f"{int(value):,}개"
    elif type == "percent":
        return f"{value:.1f}%"
    elif type == "price":
        return f"{int(value):,}원"
    else:
        return f"{value:,.0f}"

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
        st.session_state.expanded_cards = set()  # 확장된 카드 초기화
        progress_bar.progress(100)
        
        if recommendations:
            st.success(f"✅ 분석 완료! {len(recommendations)}개의 추천 지역을 찾았습니다.")
        else:
            st.warning("⚠️ 조건에 맞는 지역을 찾을 수 없습니다. 조건을 완화해보세요.")

def get_competition_level(store_count):
    """경쟁 수준 판단"""
    if store_count <= 10:
        return "🟢 블루오션", "success"
    elif store_count <= 30:
        return "🟡 적당한 경쟁", "warning"
    else:
        return "🔴 경쟁 활발", "danger"

def display_results():
    """결과 표시"""
    if not st.session_state.recommendations:
        st.info("📍 좌측에서 조건을 설정하고 '입지 분석 시작' 버튼을 클릭하세요.")
        return
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["📊 추천 결과", "📈 비교 분석", "💡 인사이트"])
    
    with tab1:
        display_recommendations_with_details()
    
    with tab2:
        display_comparison()
    
    with tab3:
        display_insights()

def display_recommendations_with_details():
    """추천 결과와 상세 분석 통합 표시"""
    st.markdown("## 🏆 카페 창업 추천 입지 TOP 5")
    
    for i, rec in enumerate(st.session_state.recommendations):
        rank = i + 1
        card_key = f"card_{rank}"
        
        # 순위별 색상
        rank_colors = {1: "#4CAF50", 2: "#2196F3", 3: "#FF9800", 4: "#9E9E9E", 5: "#757575"}
        rank_color = rank_colors.get(rank, "#757575")
        
        # 추천 카드 컨테이너
        with st.container():
            # 메인 카드
            st.markdown(f"""
            <div class="recommendation-card">
            """, unsafe_allow_html=True)
            
            # 기본 정보 행
            col1, col2, col3 = st.columns([1, 4, 2])
            
            with col1:
                st.markdown(f"""
                <div class="rank-badge" style="color: {rank_color};">
                    #{rank}
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"### {rec.dong_name}")
                st.markdown(f"**{rec.gu_name}** | 종합 점수: ⭐ {rec.score:.2f}")
            
            with col3:
                # 상세보기 토글 버튼
                if st.button(
                    "📊 상세 분석 보기" if card_key not in st.session_state.expanded_cards else "📉 상세 분석 닫기",
                    key=f"toggle_{rank}",
                    use_container_width=True
                ):
                    if card_key in st.session_state.expanded_cards:
                        st.session_state.expanded_cards.remove(card_key)
                    else:
                        st.session_state.expanded_cards.add(card_key)
                    st.rerun()
            
            # 핵심 지표 (항상 표시)
            st.markdown("---")
            
            # 반응형 컬럼 설정
            if st.session_state.get('screen_width', 1200) < 768:
                # 모바일: 2x2 그리드
                metrics_cols = 2
            else:
                # 데스크톱/태블릿: 4x1 그리드
                metrics_cols = 4
            
            cols = st.columns(metrics_cols)
            
            metrics = [
                ("💰 월매출", format_number_for_display(rec.avg_revenue_per_store, "currency")),
                ("🏪 카페", f"{rec.store_count}개"),
                ("📉 폐업률", f"{rec.closure_rate*100:.1f}%"),
                ("🚇 지하철", "있음" if rec.subway_access else "없음")
            ]
            
            for idx, (label, value) in enumerate(metrics):
                with cols[idx % metrics_cols]:
                    st.markdown(f"""
                    <div class="metric-container">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # 상세 분석 섹션 (확장 시에만 표시)
            if card_key in st.session_state.expanded_cards:
                st.markdown("---")
                display_detailed_analysis(rec, rank)
            
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("")  # 카드 간 여백

def display_detailed_analysis(rec, rank):
    """개별 지역 상세 분석"""
    # 상세 분석 컨테이너
    st.markdown('<div class="detail-section">', unsafe_allow_html=True)
    
    # 1. 매출 상세 분석
    st.markdown("#### 💰 매출 상세 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 매출 정보
        revenue_data = {
            "구분": ["전체 매출", "점포당 매출", "일 평균", "객단가"],
            "금액": [
                format_number_for_display(rec.total_revenue, "currency"),
                format_number_for_display(rec.avg_revenue_per_store, "currency"),
                format_number_for_display(rec.avg_revenue_per_store / 30, "currency"),
                format_number_for_display(rec.avg_price, "price")
            ]
        }
        
        for idx, row in enumerate(revenue_data["구분"]):
            st.markdown(f"**{row}**: {revenue_data['금액'][idx]}")
    
    with col2:
        # 매출 구성 차트
        fig_revenue = go.Figure(data=[
            go.Bar(
                x=['여성', '남성'],
                y=[rec.female_ratio * 100, (1 - rec.female_ratio) * 100],
                marker_color=['#FF6B6B', '#4ECDC4'],
                text=[f'{rec.female_ratio * 100:.1f}%', f'{(1 - rec.female_ratio) * 100:.1f}%'],
                textposition='auto'
            )
        ])
        fig_revenue.update_layout(
            title="성별 매출 비율",
            yaxis_title="비율 (%)",
            height=250,
            showlegend=False,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig_revenue, use_container_width=True, key=f"gender_{rank}")
    
    # 2. 시간대별 분석
    st.markdown("#### ⏰ 시간대별 매출 패턴")
    
    # 시간대별 매출 데이터 (실제로는 rec에서 가져와야 함)
    time_data = {
        '시간대': ['06-11시', '11-14시', '14-17시', '17-21시', '21-24시'],
        '매출 비율': [rec.morning_sales_ratio * 100, 25, 20, 30, 10]  # 예시 데이터
    }
    
    fig_time = px.line(
        time_data, 
        x='시간대', 
        y='매출 비율',
        markers=True,
        title='시간대별 매출 분포'
    )
    fig_time.update_traces(line_color='#1976D2', line_width=3, marker_size=10)
    fig_time.update_layout(
        yaxis_title="매출 비율 (%)",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    st.plotly_chart(fig_time, use_container_width=True, key=f"time_{rank}")
    
    # 3. 경쟁 환경 분석
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏪 경쟁 환경")
        
        competition_level, comp_type = get_competition_level(rec.store_count)
        
        st.markdown(f"**경쟁 수준**: {competition_level}")
        st.markdown(f"**카페 점포수**: {rec.store_count}개")
        st.markdown(f"**폐업률**: {rec.closure_rate * 100:.1f}%")
        
        # 안정성 지표
        stability_score = (1 - rec.closure_rate) * 100
        st.metric("안정성 지수", f"{stability_score:.1f}점", help="100점 만점, 폐업률이 낮을수록 높음")
    
    with col2:
        st.markdown("#### 📊 주중/주말 분석")
        
        # 요일별 매출 차트
        weekday_data = {
            '구분': ['주중', '주말'],
            '비율': [rec.weekday_ratio * 100, (1 - rec.weekday_ratio) * 100]
        }
        
        fig_weekday = go.Figure(data=[
            go.Pie(
                labels=weekday_data['구분'],
                values=weekday_data['비율'],
                hole=0.3,
                marker_colors=['#1976D2', '#FF6B6B']
            )
        ])
        fig_weekday.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True
        )
        st.plotly_chart(fig_weekday, use_container_width=True, key=f"weekday_{rank}")
    
    # 4. 지역 특성 인사이트
    st.markdown("#### 💡 이 지역의 특징")
    
    # 인사이트 생성
    insights = generate_location_insights(rec)
    
    for insight in insights:
        box_class = insight.get('type', 'info') + '-box'
        st.markdown(f"""
        <div class="insight-box {box_class}">
            {insight['icon']} {insight['text']}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def generate_location_insights(rec):
    """지역별 맞춤 인사이트 생성"""
    insights = []
    
    # 매출 인사이트
    if rec.avg_revenue_per_store >= 30000 * 10000:  # 3억원 이상
        insights.append({
            'icon': '🚀',
            'text': f'이 지역은 <b>{format_number_for_display(rec.avg_revenue_per_store, "currency")}</b>의 높은 매출을 기록하는 프리미엄 상권입니다.',
            'type': 'success'
        })
    elif rec.avg_revenue_per_store < 10000 * 10000:  # 1억원 미만
        insights.append({
            'icon': '💡',
            'text': f'월 매출이 <b>{format_number_for_display(rec.avg_revenue_per_store, "currency")}</b>로 상대적으로 낮습니다. 원가 관리가 중요합니다.',
            'type': 'warning'
        })
    
    # 여성 고객 인사이트
    if rec.female_ratio > 0.6:
        insights.append({
            'icon': '👩',
            'text': f'여성 고객 비율이 {rec.female_ratio*100:.0f}%로 높습니다. 디저트 카페나 브런치 콘셉트를 고려해보세요.',
            'type': 'info'
        })
    
    # 경쟁 인사이트
    if rec.store_count < 10:
        insights.append({
            'icon': '🌊',
            'text': '카페 점포수가 적어 선점 효과를 기대할 수 있습니다. 단, 수요 검증이 필요합니다.',
            'type': 'info'
        })
    elif rec.store_count > 30:
        insights.append({
            'icon': '⚔️',
            'text': '경쟁이 치열한 지역입니다. 명확한 차별화 전략과 충성 고객 확보가 필수입니다.',
            'type': 'warning'
        })
    
    # 폐업률 인사이트
    if rec.closure_rate < 0.1:
        insights.append({
            'icon': '🛡️',
            'text': f'폐업률이 {rec.closure_rate*100:.1f}%로 매우 낮아 안정적인 상권입니다.',
            'type': 'success'
        })
    elif rec.closure_rate > 0.2:
        insights.append({
            'icon': '⚠️',
            'text': f'폐업률이 {rec.closure_rate*100:.1f}%로 높은 편입니다. 신중한 사업 계획이 필요합니다.',
            'type': 'warning'
        })
    
    # 지하철 인사이트
    if rec.subway_access:
        insights.append({
            'icon': '🚇',
            'text': '지하철역과 가까워 유동인구가 많습니다. 테이크아웃 전문점도 고려해보세요.',
            'type': 'info'
        })
    
    # 시간대 인사이트
    if rec.morning_sales_ratio > 0.3:
        insights.append({
            'icon': '🌅',
            'text': '아침 시간대 매출이 높습니다. 출근길 고객을 위한 빠른 서비스가 중요합니다.',
            'type': 'info'
        })
    
    # 주중/주말 인사이트
    if rec.weekday_ratio > 0.7:
        insights.append({
            'icon': '💼',
            'text': '주중 매출 비중이 높은 직장인 상권입니다. 업무 미팅 공간 제공을 고려하세요.',
            'type': 'info'
        })
    elif rec.weekday_ratio < 0.5:
        insights.append({
            'icon': '🎉',
            'text': '주말 매출 비중이 높습니다. 가족 단위 고객을 위한 공간 구성이 유리합니다.',
            'type': 'info'
        })
    
    return insights

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
    
    # 반응형 레이아웃
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 매출 비교 차트
        fig1 = px.bar(
            df, 
            x='지역', 
            y='월평균 매출',
            title='월평균 매출 비교 (만원)',
            color='월평균 매출',
            color_continuous_scale='Blues',
            text='월평균 매출'
        )
        fig1.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig1.update_layout(
            showlegend=False,
            height=400,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # 경쟁 vs 매출 산점도
        fig2 = px.scatter(
            df, 
            x='카페 수', 
            y='월평균 매출',
            size='종합 점수',
            color='지역',
            title='경쟁 환경 vs 매출',
            hover_data={
                '객단가': ':,',
                '폐업률': ':.1f',
                '카페 수': ':,',
                '월평균 매출': ':,.0f',
                '종합 점수': ':.1f'
            },
            labels={
                '카페 수': '카페 수 (개)',
                '월평균 매출': '월평균 매출 (만원)',
                '객단가': '객단가 (원)',
                '폐업률': '폐업률 (%)',
                '종합 점수': '점수'
            }
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    
    # 종합 비교 레이더 차트
    st.markdown("### 🎯 상위 3개 지역 종합 비교")
    
    categories = ['매출력', '안정성', '경쟁우위', '고객매력', '접근성']
    
    fig3 = go.Figure()
    
    colors = ['#1976D2', '#FF6B6B', '#4ECDC4']
    
    # 최대값 찾기 (정규화용)
    max_revenue = max(r.avg_revenue_per_store for r in st.session_state.recommendations[:3])
    
    for i, rec in enumerate(st.session_state.recommendations[:3]):
        # 각 지표 정규화 (0-100)
        values = [
            (rec.avg_revenue_per_store / max_revenue) * 100,  # 매출력 (상대 비교)
            (1 - rec.closure_rate) * 100,  # 안정성
            max(100 - (rec.store_count / 50 * 100), 0),  # 경쟁우위
            rec.female_ratio * 100,  # 고객매력 (여성비율 기준)
            100 if rec.subway_access else 50  # 접근성
        ]
        
        fig3.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name=rec.dong_name,
            line_color=colors[i],
            fillcolor=colors[i],
            opacity=0.6
        ))
    
    fig3.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickmode='linear',
                tick0=0,
                dtick=20
            )
        ),
        showlegend=True,
        height=500,
        title="다차원 경쟁력 분석"
    )
    
    st.plotly_chart(fig3, use_container_width=True)
    
    # 상세 비교 테이블
    st.markdown("### 📋 상세 수치 비교")
    
    # 테이블 데이터 포맷팅
    comparison_df = df.copy()
    comparison_df['월평균 매출'] = comparison_df['월평균 매출'].apply(lambda x: format_number_for_display(x*10000, "currency"))
    comparison_df['폐업률'] = comparison_df['폐업률'].apply(lambda x: f"{x:.1f}%")
    comparison_df['여성 비율'] = comparison_df['여성 비율'].apply(lambda x: f"{x:.0f}%")
    comparison_df['객단가'] = comparison_df['객단가'].apply(lambda x: format_number_for_display(x, "price"))
    comparison_df['종합 점수'] = comparison_df['종합 점수'].apply(lambda x: f"{x:.1f}점")
    
    # 순위 열 제거 (이미 정렬되어 있음)
    comparison_df = comparison_df.drop('순위', axis=1)
    
    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "지역": st.column_config.TextColumn("지역", width="medium"),
            "월평균 매출": st.column_config.TextColumn("월평균 매출", width="small"),
            "카페 수": st.column_config.NumberColumn("카페 수", width="small"),
            "폐업률": st.column_config.TextColumn("폐업률", width="small"),
            "여성 비율": st.column_config.TextColumn("여성 비율", width="small"),
            "객단가": st.column_config.TextColumn("객단가", width="small"),
            "종합 점수": st.column_config.TextColumn("종합 점수", width="small"),
        }
    )

def display_insights():
    """인사이트 표시"""
    st.markdown("## 💡 종합 분석 인사이트")
    
    if not st.session_state.recommendations:
        return
    
    # 분석 요약
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "추천 지역 수",
            f"{len(st.session_state.recommendations)}개",
            help="설정하신 조건에 맞는 지역 수"
        )
    
    with col2:
        avg_revenue = sum(r.avg_revenue_per_store for r in st.session_state.recommendations) / len(st.session_state.recommendations)
        st.metric(
            "평균 예상 매출",
            format_number_for_display(avg_revenue, "currency"),
            help="추천 지역들의 평균 월매출"
        )
    
    with col3:
        avg_competition = sum(r.store_count for r in st.session_state.recommendations) / len(st.session_state.recommendations)
        st.metric(
            "평균 경쟁 강도",
            f"{avg_competition:.0f}개 카페",
            help="추천 지역들의 평균 카페 수"
        )
    
    st.markdown("---")
    
    # 주요 인사이트
    insights_container = st.container()
    
    with insights_container:
        # 1위 지역 분석
        top_rec = st.session_state.recommendations[0]
        st.markdown(f"""
        <div class="insight-box success-box">
            🏆 <b>최우수 추천 지역</b><br>
            {top_rec.dong_name}({top_rec.gu_name})이(가) 종합 1위입니다. 
            월평균 <b>{format_number_for_display(top_rec.avg_revenue_per_store, "currency")}</b>의 매출이 예상되며, 
            {'지하철역이 있어 접근성이 우수합니다.' if top_rec.subway_access else '도보 고객 위주의 상권입니다.'}
        </div>
        """, unsafe_allow_html=True)
        
        # 최고 매출 지역
        top_revenue = max(st.session_state.recommendations, key=lambda x: x.avg_revenue_per_store)
        if top_revenue != top_rec:
            st.markdown(f"""
            <div class="insight-box info-box">
                💰 <b>최고 매출 지역</b><br>
                {top_revenue.dong_name}이(가) 가장 높은 매출(<b>{format_number_for_display(top_revenue.avg_revenue_per_store, "currency")}</b>)을 
                기록하고 있습니다. 프리미엄 전략이 유효한 지역입니다.
            </div>
            """, unsafe_allow_html=True)
        
        # 블루오션 지역
        min_competition = min(st.session_state.recommendations, key=lambda x: x.store_count)
        st.markdown(f"""
        <div class="insight-box info-box">
            🌊 <b>블루오션 기회</b><br>
            {min_competition.dong_name}은(는) 카페가 {min_competition.store_count}개로 가장 적습니다. 
            선점 효과를 노릴 수 있지만, 수요 검증이 필요합니다.
        </div>
        """, unsafe_allow_html=True)
        
        # 안정성 분석
        min_closure = min(st.session_state.recommendations, key=lambda x: x.closure_rate)
        st.markdown(f"""
        <div class="insight-box success-box">
            🛡️ <b>가장 안정적인 지역</b><br>
            {min_closure.dong_name}의 폐업률은 {min_closure.closure_rate*100:.1f}%로 매우 낮습니다. 
            장기적 운영에 유리한 안정적 상권입니다.
        </div>
        """, unsafe_allow_html=True)
    
    # 창업 체크리스트
    st.markdown("### ✅ 창업 전 체크리스트")
    
    checklist = [
        "선정 지역 현장 답사 (평일/주말, 다양한 시간대)",
        "주변 카페 콘셉트 및 가격대 조사",
        "임대료 및 권리금 시세 확인",
        "목표 고객층 라이프스타일 분석",
        "필요 인허가 및 규제 사항 확인",
        "초기 투자금 및 운영자금 계획 (6개월분)",
        "차별화 콘셉트 및 메뉴 개발",
        "온/오프라인 마케팅 전략 수립"
    ]
    
    for item in checklist:
        st.checkbox(item, key=f"checklist_{checklist.index(item)}")
    
    # 추가 리소스
    st.markdown("### 📚 유용한 자료")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **정부 지원**
        - [소상공인시장진흥공단](https://www.semas.or.kr)
        - [서울신용보증재단](https://www.seoulshinbo.co.kr)
        - [서울시 자영업지원센터](https://www.seoulsbdc.or.kr)
        """)
    
    with col2:
        st.markdown("""
        **시장 분석**
        - [서울시 우리마을가게 상권분석](https://golmok.seoul.go.kr)
        - [소상공인 상권정보시스템](https://sg.sbiz.or.kr)
        - [KB부동산 상업용부동산](https://kbland.kr)
        """)

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
<div style="text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;">
    <p>© 2024 Seoul Cafe Location Optimizer | Seoul Data Analysis Team</p>
    <p>데이터 출처: 서울 열린데이터광장 | 문의: example@seoul.go.kr</p>
</div>
""", unsafe_allow_html=True)