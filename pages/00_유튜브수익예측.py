import streamlit as st
from googleapiclient.discovery import build

# -------------------------
# 페이지 설정
# -------------------------
st.set_page_config(
    page_title="YouTube 수익 분석기",
    page_icon="📺",
    layout="wide"
)

# -------------------------
# 제목
# -------------------------
st.title("📺 유튜브 채널 수익 분석기")

st.markdown("""
채널명을 입력하면

- 구독자 수
- 총 조회수
- 영상 수
- 예상 월 광고 수익

을 분석합니다.
""")

# -------------------------
# API KEY 입력
# -------------------------
API_KEY = st.text_input(
    "YouTube Data API Key",
    type="password"
)

# -------------------------
# 채널명 입력
# -------------------------
channel_name = st.text_input(
    "유튜브 채널명",
    placeholder="예: 침착맨"
)

# -------------------------
# 채널 검색
# -------------------------
def search_channel(youtube, channel_name):

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
# 채널 정보 가져오기
# -------------------------
def get_channel_stats(youtube, channel_id):

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
        "subscribers": int(
            item["statistics"].get(
                "subscriberCount",
                0
            )
        ),
        "views": int(
            item["statistics"].get(
                "viewCount",
                0
            )
        ),
        "videos": int(
            item["statistics"].get(
                "videoCount",
                0
            )
        )
    }


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views):

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
# 분석 버튼
# -------------------------
if st.button("분석하기"):

    if not API_KEY:
        st.error("YouTube API Key를 입력하세요.")
        st.stop()

    if not channel_name:
        st.error("채널명을 입력하세요.")
        st.stop()

    try:

        youtube = build(
            "youtube",
            "v3",
            developerKey=API_KEY
        )

        with st.spinner("분석 중..."):

            channel_id = search_channel(
                youtube,
                channel_name
            )

            if not channel_id:
                st.error("채널을 찾을 수 없습니다.")
                st.stop()

            data = get_channel_stats(
                youtube,
                channel_id
            )

            revenue = estimate_revenue(
                data["views"]
            )

        col1, col2 = st.columns([1, 3])

        with col1:
            st.image(
                data["thumbnail"],
                width=180
            )

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
            "실제 수익은 국가, CPM, RPM, 광고 유형, 멤버십, 협찬 등에 따라 달라질 수 있습니다."
        )

    except Exception as e:
        st.error(f"오류 발생: {e}")
