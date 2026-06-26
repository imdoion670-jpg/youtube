import streamlit as st
import yt_dlp
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
import urllib.request

# -------------------------
# 한글 폰트 설정
# -------------------------

FONT_PATH = "/tmp/NanumGothic.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

if not Path(FONT_PATH).exists():
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    except Exception:
        FONT_PATH = None

if FONT_PATH and Path(FONT_PATH).exists():
    font_manager.fontManager.addfont(FONT_PATH)
    prop = font_manager.FontProperties(fname=FONT_PATH)
    plt.rcParams["font.family"] = prop.get_name()

plt.rcParams["axes.unicode_minus"] = False

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
- 최근 영상 목록 & 조회수
- 영상별 평균 조회수
- 구독자 대비 조회수 비율 (참여율)

을 분석합니다.
""")

# -------------------------
# 채널명 입력
# -------------------------
channel_name = st.text_input(
    "유튜브 채널명",
    placeholder="예: 침착맨"
)

recent_count = st.slider(
    "최근 영상 수",
    5, 30, 10, 5
)

# -------------------------
# 채널 정보 가져오기
# -------------------------
def get_channel_stats(channel_name, recent_count):

    # 채널 URL 검색
    search_url = f"ytsearch1:{channel_name}"

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
        search_result = ydl.extract_info(search_url, download=False)

    if not search_result.get("entries"):
        return None, None

    channel_url = search_result["entries"][0].get("channel_url")

    if not channel_url:
        return None, None

    # 채널 기본 정보 + 최근 영상
    channel_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": recent_count,
    }

    with yt_dlp.YoutubeDL(channel_opts) as ydl:
        channel_info = ydl.extract_info(channel_url, download=False)

    entries = channel_info.get("entries") or []

    # 각 영상 조회수 가져오기
    videos = []
    video_opts = {"quiet": True, "no_warnings": True}

    for entry in entries[:recent_count]:
        video_url = entry.get("url") or entry.get("webpage_url")
        if not video_url:
            continue
        try:
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                videos.append({
                    "제목": info.get("title", ""),
                    "조회수": info.get("view_count", 0) or 0,
                    "좋아요": info.get("like_count", 0) or 0,
                    "업로드일": info.get("upload_date", ""),
                    "url": info.get("webpage_url", ""),
                })
        except Exception:
            continue

    channel_data = {
        "title": channel_info.get("channel") or channel_info.get("uploader", ""),
        "thumbnail": (channel_info.get("thumbnails") or [{}])[-1].get("url", ""),
        "subscribers": channel_info.get("channel_follower_count", 0) or 0,
        "views": sum(v["조회수"] for v in videos) if videos else 0,
        "videos": channel_info.get("playlist_count", 0) or len(videos),
    }

    return channel_data, videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views):

    monthly_views = total_views * 0.03

    return {
        "monthly_low":  monthly_views / 1000 * 1,
        "monthly_avg":  monthly_views / 1000 * 3,
        "monthly_high": monthly_views / 1000 * 8,
    }


# -------------------------
# 분석 버튼
# -------------------------
if st.button("분석하기"):

    if not channel_name:
        st.error("채널명을 입력하세요.")
        st.stop()

    try:

        with st.spinner("채널 정보 수집 중..."):
            data, videos = get_channel_stats(channel_name, recent_count)

        if not data:
            st.error("채널을 찾을 수 없습니다.")
            st.stop()

        revenue = estimate_revenue(data["views"])

        # -------------------------
        # 채널 기본 정보
        # -------------------------
        col1, col2 = st.columns([1, 3])

        with col1:
            if data["thumbnail"]:
                st.image(data["thumbnail"], width=180)

        with col2:
            st.subheader(data["title"])

            m1, m2, m3 = st.columns(3)

            m1.metric("구독자", f"{data['subscribers']:,}")
            m2.metric("총 조회수 (최근)", f"{data['views']:,}")
            m3.metric("영상 수", f"{data['videos']:,}")

            # 참여율
            if data["subscribers"] > 0 and data["views"] > 0:
                engagement = (data["views"] / data["videos"] / data["subscribers"] * 100) if data["videos"] > 0 else 0
                avg_views = data["views"] // data["videos"] if data["videos"] > 0 else 0
                e1, e2 = st.columns(2)
                e1.metric("영상별 평균 조회수", f"{avg_views:,}")
                e2.metric("참여율 (평균조회수/구독자)", f"{engagement:.2f}%")

        st.divider()

        # -------------------------
        # 예상 수익
        # -------------------------
        st.subheader("💰 예상 월 광고 수익")

        c1, c2, c3 = st.columns(3)
        c1.metric("보수적", f"${revenue['monthly_low']:,.0f}")
        c2.metric("평균",   f"${revenue['monthly_avg']:,.0f}")
        c3.metric("낙관적", f"${revenue['monthly_high']:,.0f}")

        st.info("실제 수익은 국가, CPM, RPM, 광고 유형, 멤버십, 협찬 등에 따라 달라질 수 있습니다.")

        st.divider()

        # -------------------------
        # 최근 영상 목록
        # -------------------------
        if videos:

            st.subheader(f"🎬 최근 영상 {len(videos)}개")

            df = pd.DataFrame(videos)
            df["업로드일"] = pd.to_datetime(df["업로드일"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
            df["링크"] = df["url"].apply(lambda x: f"[보기]({x})")

            st.dataframe(
                df[["제목", "조회수", "좋아요", "업로드일"]],
                use_container_width=True
            )

            # 조회수 차트
            st.subheader("📊 영상별 조회수")

            fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))

            titles = [t[:20] + "..." if len(t) > 20 else t for t in df["제목"]]

            ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
            ax.set_xlabel("조회수")
            ax.set_title("최근 영상 조회수 비교")

            st.pyplot(fig)

    except Exception as e:
        st.error(f"오류 발생: {e}")
