import streamlit as st
import random
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDS"], scope)
client = gspread.authorize(creds)

spreadsheet = client.open("ys_store")
sheet_store = spreadsheet.worksheet("음식점리스트")
sheet_visit = spreadsheet.worksheet("방문기록")
sheet_review = spreadsheet.worksheet("리뷰")  # ✅ 리뷰 시트

restaurant_lst = [row[1].strip() for row in sheet_store.get_all_values()[1:] if row[1]]

# --- 페이지 분기 ---
page = st.sidebar.selectbox("페이지 선택", ["🍽️ 음식점 추천", "📝 리뷰"])

# ============================================
# ✅ 추천 기능 페이지
# ============================================
if page == "🍽️ 음식점 추천":
    st.title("🍽️ 점심 뭐먹🤔")

    names = sheet_visit.row_values(1)[1:]
    person_name = st.selectbox("이름을 선택하세요", names)

    if not person_name:
        st.warning("⚠️ 이름을 선택해 주세요.")
        st.stop()

    col_idx = names.index(person_name) + 2
    visit_records = sheet_visit.col_values(col_idx)[1:]
    dates = sheet_visit.col_values(1)[1:]
    recent = [r for r in visit_records if r][-5:]

    if st.session_state.get("current_choice"):
        st.write(f"최근 {person_name}님의 방문 음식점: {recent}")

    candidates = [r for r in restaurant_lst if r not in recent]
    if not candidates:
        st.warning("추천할 음식점이 없습니다.")
        st.stop()

    if 'recommend_pool' not in st.session_state:
        st.session_state.recommend_pool = candidates.copy()
    if 'current_choice' not in st.session_state:
        st.session_state.current_choice = None

    if st.session_state.current_choice is None:
        if st.button('추천'):
            if st.session_state.recommend_pool:
                st.session_state.current_choice = random.choice(st.session_state.recommend_pool)
                st.session_state.recommend_pool.remove(st.session_state.current_choice)
            else:
                st.warning("추천할 음식점이 더 없습니다.")
    else:
        st.success(f'🍽️ 추천 음식점: **{st.session_state.current_choice}**')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('이 음식점으로 선택'):
                today = datetime.today().strftime('%Y-%m-%d')
                next_row = len(sheet_visit.col_values(1)) + 1
                sheet_visit.update_cell(next_row, 1, today)
                sheet_visit.update_cell(next_row, col_idx, st.session_state.current_choice)
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
# ✅ 리뷰 작성 및 보기 페이지
# ============================================
elif page == "📝 리뷰":
    st.title("📝 음식점 리뷰")

    selected_store = st.selectbox("음식점을 선택하세요", restaurant_lst)

    # 입력 초기화 플래그를 먼저 확인
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
            st.rerun()  # ← Streamlit 1.39부터 공식 지원

    st.divider()
    st.subheader(f"📋 '{selected_store}'에 대한 리뷰 목록")

    reviews = sheet_review.get_all_values()[1:]  # 헤더 제외
    store_reviews = [r for r in reviews if r[0].strip() == selected_store.strip()]
    store_reviews = sorted(store_reviews, key=lambda x: x[1], reverse=True)

    if store_reviews:
        for r in store_reviews:
            st.markdown(f"**🕒 {r[1]}**")
            st.write(r[2])
            st.markdown("---")
    else:
        st.info("아직 등록된 리뷰가 없습니다.")