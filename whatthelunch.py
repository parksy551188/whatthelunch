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

@st.cache_data(ttl=60)
def get_visit_data():
    return sheet_visit.get_all_values()

@st.cache_data(ttl=60)
def get_restaurant_list():
    return [r.strip() for r in sheet_store.col_values(1)[1:]]

restaurant_lst = get_restaurant_list()

# --- 페이지 분기 ---
page = st.sidebar.selectbox("페이지 선택", [ "📝 리뷰","🍽️ 음식점 추천", "📊 방문 통계"])

# ============================================
# ✅ 추천 기능 페이지
# ============================================
if page == "🍽️ 음식점 추천":
    st.title("🍽️ 점심 뭐먹🤔")

    @st.cache_data(ttl=60)
    def get_name_list():
        return sheet_visit.row_values(1)[1:]

    names = get_name_list()
    person_name = st.selectbox("이름을 선택하세요", names)

    if not person_name:
        st.warning("⚠️ 이름을 선택해 주세요.")
        st.stop()

    col_idx = names.index(person_name) + 2
    visit_records = sheet_visit.col_values(col_idx)[1:]
    recent = [r.strip() for r in visit_records if r][-5:]

    st.markdown(f"최근 **{person_name}**님의 방문 음식점: {' / '.join(recent)}")

    # 🔄 후보 음식점은 매번 새로 계산 (최근 5곳만 제외)
    restaurant_cleaned = [r.strip() for r in restaurant_lst]
    candidates = [r for r in restaurant_cleaned if r not in recent]

    if not candidates:
        st.warning("추천할 음식점이 없습니다.")
        st.stop()

    if st.button('추천'):
        current_choice = random.choice(candidates)
        st.session_state.current_choice = current_choice

    if 'current_choice' in st.session_state and st.session_state.current_choice:
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
                del st.session_state.current_choice

        with col2:
            if st.button("다른 음식점 선택하기"):
                current_choice = random.choice(candidates)
                st.session_state.current_choice = current_choice

# ============================================
# ✅ 리뷰 작성 및 보기 페이지
# ============================================
elif page == "📝 리뷰":
    st.title("📝 음식점 리뷰")

    restaurant_options = ['전체']+restaurant_lst
    selected_store = st.selectbox('음식점을 선택하세요', restaurant_options, index=0)

    # 입력창은 '전체'가 아닌 경우에만 표시 
    if selected_store != '전체':
        if st.session_state.get("clear_review_input"):
            st.session_state["review_input"] = ""
            st.session_state["clear_review_input"] = False  # 플래그 해제

        # 입력란 렌더링 (이후에는 값 변경 금지)
        review_text = st.text_area(
            "리뷰 내용을 입력하세요",
            placeholder="자유롭게 리뷰를 작성해주세요",
            key="review_input"
        )

        # 등록 버튼
        if st.button("리뷰 등록"):
            if review_text.strip() == "":
                st.warning("리뷰 내용을 입력해주세요.")
            else:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_row = [selected_store, now, review_text]
                sheet_review.append_row(new_row, value_input_option='RAW')
                st.success("✅ 리뷰가 등록되었습니다!")

                # 다음 렌더링 때 초기화되도록 플래그 설정
                st.session_state["clear_review_input"] = True
                st.rerun() 

    st.divider()
    # st.subheader(f"📋 '{selected_store}'에 대한 리뷰 목록")

    # 전체 리뷰 불러오기
    reviews = sheet_review.get_all_values()[1:]  # 헤더 제외
    reviews = sorted(reviews, key=lambda x: x[1], reverse=True)

    # 필터링
    if selected_store == '전체':
        filtered_reviews = reviews
        st.subheader('📋 전체 음식점 리뷰')
    else:
        filtered_reviews = [r for r in reviews if r[0].strip() == selected_store.strip()]
        st.subheader(f"📋 '{selected_store}'에 대한 리뷰 목록")
    
    if filtered_reviews:
        for r in filtered_reviews:
            st.markdown(f"### 🍽️ {r[0]}")
            st.markdown(f"**🕒 {r[1]}**")
            st.write(r[2])
            st.markdown("---")
    else:
        st.info('아직 등록된 리뷰가 없습니다. ')

    # store_reviews = [r for r in reviews if r[0].strip() == selected_store.strip()]
    # store_reviews = sorted(store_reviews, key=lambda x: x[1], reverse=True)

    # if store_reviews:
    #     for r in store_reviews:
    #         st.markdown(f"**🕒 {r[1]}**")
    #         st.write(r[2])
    #         st.markdown("---")
    # else:
    #     st.info("아직 등록된 리뷰가 없습니다.")

# ============================================
# ✅ EDA 페이지
# ============================================
elif page == "📊 방문 통계":
    st.title("📊 방문 통계 분석")

    # 시트 데이터 전체 한 번만 가져오기 (사용량 최소화)
    visit_data = get_visit_data()
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

