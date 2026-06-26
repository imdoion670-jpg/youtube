import streamlit as st
import yt_dlp

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
# 채널명 입력
# -------------------------
channel_name = st.text_input(
    "유튜브 채널명",
    placeholder="예: 침착맨"
)

# -------------------------
# 채널 정보 가져오기 (yt-dlp)
# -------------------------
def get_channel_stats(channel_name):

    search_url = f"ytsearch1:{channel_name}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_result = ydl.extract_info(
            search_url,
            download=False
        )

    if not search_result.get("entries"):
        return None

    channel_url = search_result["entries"][0].get("channel_url")

    if not channel_url:
        return None

    channel_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": 1,
    }

    with yt_dlp.YoutubeDL(channel_opts) as ydl:
        channel_info = ydl.extract_info(
            channel_url,
            download=False
        )

    return {
        "title": channel_info.get("channel") or channel_info.get("uploader", ""),
        "thumbnail": channel_info.get("thumbnails", [{}])[-1].get("url", ""),
        "subscribers": channel_info.get("channel_follower_count", 0) or 0,
        "views": channel_info.get("view_count", 0) or 0,
        "videos": channel_info.get("playlist_count", 0) or 0,
        "description": channel_info.get("description", ""),
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

    if not channel_name:
        st.error("채널명을 입력하세요.")
        st.stop()

    try:

        with st.spinner("분석 중..."):

            data = get_channel_stats(channel_name)

            if not data:
                st.error("채널을 찾을 수 없습니다.")
                st.stop()

            revenue = estimate_revenue(
                data["views"]
            )

        col1, col2 = st.columns([1, 3])

        with col1:
            if data["thumbnail"]:
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
