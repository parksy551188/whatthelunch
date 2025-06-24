import streamlit as st
import random
from datetime import datetime, timedelta 
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pandas as pd
import plotly.express as px

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDS"], scope)
client = gspread.authorize(creds)

spreadsheet = client.open("ys_store")
sheet_store = spreadsheet.worksheet("음식점리스트")
sheet_visit = spreadsheet.worksheet("방문기록")
sheet_review = spreadsheet.worksheet("리뷰")  # ✅ 리뷰 시트

restaurant_lst = [row[1].strip() for row in sheet_store.get_all_values()[1:] if row[1]]

# --- 페이지 분기 ---
page = st.sidebar.selectbox("페이지 선택", ["📝 리뷰","🍽️ 음식점 추천", "📊 방문 통계"])

# ============================================
# ✅ 추천 기능 페이지
# ============================================
if page == "🍽️ 음식점 추천":
    st.title("🍽️ 점심 뭐먹🤔")

    names = sheet_visit.row_values(1)[1:]
    person_name = st.selectbox("이름을 선택하세요", names)

    if "selected_person" not in st.session_state:
        st.session_state.selected_person = person_name
    elif st.session_state.selected_person != person_name:
        st.session_state.selected_person = person_name
        st.session_state.current_choice = None
        st.session_state.recommend_pool = None

    if not person_name:
        st.warning("⚠️ 이름을 선택해 주세요.")
        st.stop()

    col_idx = names.index(person_name) + 2
    visit_records = sheet_visit.col_values(col_idx)[1:]
    dates = sheet_visit.col_values(1)[1:]
    recent = [r for r in visit_records if r][-5:]

    st.markdown(f"최근 **{person_name}**님의 방문 음식점: {' / '.join(recent)}")

    # ✅ 이 사람이 한 번도 안 간 음식점 우선, 그다음 최근 5일 제외
    visited_total = [r for r in visit_records if r]
    never_visited = list(set(restaurant_lst) - set(visited_total))
    candidates = never_visited if never_visited else list(set(restaurant_lst) - set(recent))

    if not candidates:
        st.warning("추천할 음식점이 없습니다.")
        st.stop()

    if 'recommend_pool' not in st.session_state or st.session_state.recommend_pool is None:
        st.session_state.recommend_pool = candidates.copy()
    if 'current_choice' not in st.session_state:
        st.session_state.current_choice = None

    if st.button('추천'):
        if st.session_state.recommend_pool:
            st.session_state.current_choice = random.choice(st.session_state.recommend_pool)
            st.session_state.recommend_pool.remove(st.session_state.current_choice)
        else:
            st.warning("추천할 음식점이 더 없습니다.")

    if st.session_state.current_choice:
        st.success(f'🍽️ 추천 음식점: **{st.session_state.current_choice}**')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('이 음식점으로 선택'):
                today = datetime.today().strftime('%Y-%m-%d')
                next_row = len(sheet_visit.col_values(1)) + 1
                cell_list = sheet_visit.range(next_row, 1, next_row, col_idx)
                cell_list[0].value = today
                cell_list[-1].value = st.session_state.current_choice
                sheet_visit.update_cells(cell_list)
                st.success("✅ 저장 완료!")
                del st.session_state.recommend_pool
                del st.session_state.current_choice
        with col2:
            if st.button("다른 음식점 선택하기"):
                if st.session_state.recommend_pool:
                    st.session_state.current_choice = random.choice(st.session_state.recommend_pool)
                    st.session_state.recommend_pool.remove(st.session_state.current_choice)
                else:
                    st.warning("추천할 음식점이 더 없습니다.")

# ============================================
# ✅ EDA 페이지
# ============================================
elif page == "📊 방문 통계":
    st.title("📊 방문 통계 분석")

    # 시트 데이터 전체 한 번만 가져오기 (사용량 최소화)
    visit_data = sheet_visit.get_all_values()
    if len(visit_data) < 2:
        st.info('방문 기록이 아직 없습니다.')
        st.stop()

    header = visit_data[0]
    data = visit_data[1:]

    df = pd.DataFrame(data, columns=header)
    df = df.melt(id_vars=header[0], var_name='이름', value_name='음식점')
    df.columns = ['날짜', '이름', '음식점']
    df = df[df['음식점']!='']
    df['날짜'] = pd.to_datetime(df['날짜'])

    # 최근 30일간 방문 음식점 top
    st.subheader('📌 최근 30일 방문 TOP 음식점')
    recent_30 = df[df['날짜'] >= datetime.today() - timedelta(days=30)]
    top_recent = recent_30['음식점'].value_counts().reset_index()
    top_recent.columns = ['음식점', '방문수']

    fig1 = px.bar(top_recent, x='음식점', y='방문수',
                  color='방문수',
                  color_continuous_scale='Blues',
                  title='최근 30일 TOP 음식점',)
    fig1.update_layout(xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True), coloraxis_showscale=False)
    st.plotly_chart(fig1, use_containere_width=True) 


    # 재방문 비율
    st.subheader('🔁 음식점 재방문률')
    visit_counts = df.groupby(['음식점', '이름']).size().reset_index(name='방문횟수')
    revisit_counts = visit_counts[visit_counts['방문횟수'] >= 2].groupby('음식점')['이름'].count()
    total_visitors = visit_counts.groupby('음식점')['이름'].count()

    revisit_rate = (revisit_counts / total_visitors).fillna(0).sort_values(ascending=False)

    fig2 = px.pie(
        names=revisit_rate.index,
        values=revisit_rate.values,
        title='음식점별 재방문 비율 (상위 10개)'
    )

    fig2.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig2, use_container_width=True)



    # 전체 누적 방문수 상위 음식점
    st.subheader('🥇 전체 누적 방문수 상위 음식점')
    top_total = df['음식점'].value_counts().reset_index()
    top_total.columns = ['음식점', '방문수']

    fig3 = px.bar(top_total, x='음식점', y='방문수',
                  color='방문수', color_continuous_scale='Oranges',
                  title='전체 누적 방문 TOP')
    fig3.update_layout(xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True), coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

