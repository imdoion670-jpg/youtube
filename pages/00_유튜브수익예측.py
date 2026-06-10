import streamlit as st
import pandas as pd
from googleapiclient.discovery import build

# -------------------------
# 설정
# -------------------------
st.set_page_config(
    page_title="YouTube 수익 분석기",
    page_icon="📺",
    layout="wide"
)

API_KEY = st.secrets["YOUTUBE_API_KEY"]

youtube = build(
    "youtube",
    "v3",
    developerKey=API_KEY
)

# -------------------------
# 채널 검색
# -------------------------
def search_channel(channel_name):

    request = youtube.search().list(
        q=channel_name,
        part="snippet",
        type="channel",
        maxResults=1
    )

    response = request.execute()

    if not response["items"]:
        return None

    return response["items"][0]["snippet"]["channelId"]


# -------------------------
# 채널 정보
# -------------------------
def get_channel_stats(channel_id):

    request = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    )

    response = request.execute()

    if not response["items"]:
        return None

    item = response["items"][0]

    return {
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
        "subscribers": int(item["statistics"].get("subscriberCount", 0)),
        "views": int(item["statistics"].get("viewCount", 0)),
        "videos": int(item["statistics"].get("videoCount", 0))
    }


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views):

    # 매우 단순한 추정 모델

    monthly_views = total_views * 0.03

    low_rpm = 1
    avg_rpm = 3
    high_rpm = 8

    return {
        "monthly_low": monthly_views / 1000 * low_rpm,
        "monthly_avg": monthly_views / 1000 * avg_rpm,
        "monthly_high": monthly_views / 1000 * high_rpm,
    }


# -------------------------
# UI
# -------------------------
st.title("📺 유튜브 채널 수익 분석기")

st.markdown(
    """
채널명을 입력하면 구독자, 조회수, 영상 수를 분석하여
예상 광고 수익을 계산합니다.
"""
)

channel_name = st.text_input(
    "유튜브 채널명 입력",
    placeholder="예: 침착맨"
)

if st.button("분석하기"):

    with st.spinner("채널 정보 분석 중..."):

        channel_id = search_channel(channel_name)

        if not channel_id:
            st.error("채널을 찾을 수 없습니다.")
            st.stop()

        data = get_channel_stats(channel_id)

        revenue = estimate_revenue(data["views"])

    col1, col2 = st.columns([1, 3])

    with col1:
        st.image(data["thumbnail"])

    with col2:
        st.subheader(data["title"])

        st.metric(
            "구독자",
            f"{data['subscribers']:,}"
        )

        st.metric(
            "총 조회수",
            f"{data['views']:,}"
        )

        st.metric(
            "영상 수",
            f"{data['videos']:,}"
        )

    st.divider()

    st.subheader("💰 예상 월 광고 수익")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "보수적",
        f"${revenue['monthly_low']:,.0f}"
    )

    c2.metric(
        "평균",
        f"${revenue['monthly_avg']:,.0f}"
    )

    c3.metric(
        "낙관적",
        f"${revenue['monthly_high']:,.0f}"
    )

    st.info(
        """
실제 수익은 국가, 시청자층, CPM, RPM,
광고 유형, 멤버십, 슈퍼챗, 협찬 등에 따라 크게 달라질 수 있습니다.
"""
    )
