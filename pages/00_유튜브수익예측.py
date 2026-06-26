import streamlit as st
import yt_dlp
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
import urllib.request
import concurrent.futures

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
# 입력
# -------------------------
channel_name = st.text_input(
    "유튜브 채널명",
    placeholder="예: 침착맨"
)

recent_count = st.slider(
    "최근 영상 수",
    5, 20, 10, 5
)

# -------------------------
# 단일 영상 정보 가져오기 (video_id or url 기반)
# -------------------------
def fetch_video(entry):
    """entry dict에서 video id 또는 url을 꺼내 상세 정보를 가져옴."""
    try:
        video_id = entry.get("id") or entry.get("url", "")
        # id가 URL 전체인 경우도 처리
        if video_id.startswith("http"):
            url = video_id
        else:
            url = f"https://www.youtube.com/watch?v={video_id}"

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "제목": info.get("title", ""),
                "조회수": info.get("view_count", 0) or 0,
                "좋아요": info.get("like_count", 0) or 0,
                "업로드일": info.get("upload_date", "") or "",
                "url": info.get("webpage_url", url),
            }
    except Exception as e:
        st.warning(f"영상 정보 수집 실패: {e}")
        return None


# -------------------------
# 채널 검색 → 채널 URL 확보
# -------------------------
def resolve_channel_url(channel_name: str) -> tuple[str | None, dict]:
    """
    채널명으로 검색해 채널 URL을 반환한다.
    ytsearch로 나온 영상의 channel_url을 활용하거나,
    ytsearchx: 채널 전용 검색을 시도한다.
    """
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}

    # 1차 시도: 영상 검색 결과에서 channel_url 추출
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch3:{channel_name}", download=False)

    for entry in result.get("entries") or []:
        ch_url = entry.get("channel_url")
        if ch_url:
            return ch_url, entry

    # 2차 시도: 채널 검색 URL 직접 구성
    search_url = f"https://www.youtube.com/@{channel_name}/videos"
    return search_url, {}


# -------------------------
# 채널 정보 + 영상 목록 수집
# -------------------------
def get_channel_stats(channel_name: str, recent_count: int):

    # 채널 URL 탐색
    channel_url, _ = resolve_channel_url(channel_name)
    if not channel_url:
        return None, None

    # extract_flat으로 영상 목록만 빠르게 가져오기
    list_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",   # ← 핵심: 플랫 모드지만 url/id는 포함됨
        "playlistend": recent_count,
        "ignoreerrors": True,
    }

    with yt_dlp.YoutubeDL(list_opts) as ydl:
        channel_info = ydl.extract_info(channel_url, download=False)

    if not channel_info:
        return None, None

    # entries 정규화: 중첩 플레이리스트 펼치기
    raw_entries = channel_info.get("entries") or []
    entries = []
    for e in raw_entries:
        if not e:
            continue
        # 일부 채널은 entries > entries 구조로 중첩됨
        if e.get("_type") == "playlist":
            entries.extend(e.get("entries") or [])
        else:
            entries.append(e)
    entries = [e for e in entries if e and (e.get("id") or e.get("url"))][:recent_count]

    if not entries:
        return None, None

    # 병렬로 각 영상 상세 조회수 수집
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_video, e): e for e in entries}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                videos.append(result)

    # 업로드일 기준 최신순 정렬
    videos.sort(key=lambda x: x["업로드일"], reverse=True)

    total_views = sum(v["조회수"] for v in videos)

    channel_data = {
        "title": (
            channel_info.get("channel")
            or channel_info.get("uploader")
            or channel_name
        ),
        "thumbnail": (channel_info.get("thumbnails") or [{}])[-1].get("url", ""),
        "subscribers": channel_info.get("channel_follower_count", 0) or 0,
        "views": total_views,
        "videos": channel_info.get("playlist_count", 0) or len(videos),
    }

    return channel_data, videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views: int, num_videos: int) -> dict:
    """
    최근 N개 영상의 합산 조회수를 월간으로 환산하여 수익 추정.
    월간 조회수 = 합산 조회수 (최근 영상들의 평균을 월 기준으로 볼 때)
    CPM 기준: 보수 $1, 평균 $3, 낙관 $8 / 1000뷰
    """
    # 영상 수가 있으면 영상당 평균 조회수 × 월 업로드 횟수(4회 가정)로 월간 추정
    if num_videos > 0:
        avg_views_per_video = total_views / num_videos
        monthly_views = avg_views_per_video * 4  # 월 4편 가정
    else:
        monthly_views = total_views * 0.03  # 기존 방식 fallback

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
        with st.spinner(f"채널 정보 및 최근 영상 {recent_count}개 수집 중..."):
            data, videos = get_channel_stats(channel_name, recent_count)

        if not data:
            st.error("채널을 찾을 수 없습니다. 채널명을 다시 확인해주세요.")
            st.stop()

        if not videos:
            st.warning("영상 정보를 가져오지 못했습니다. 채널에 공개 영상이 없거나 접근이 제한될 수 있습니다.")
            st.stop()

        revenue = estimate_revenue(data["views"], len(videos))

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
            m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{data['views']:,}")
            m3.metric("영상 수", f"{data['videos']:,}")

            if data["subscribers"] > 0 and len(videos) > 0 and data["views"] > 0:
                avg_views = data["views"] // len(videos)
                engagement = avg_views / data["subscribers"] * 100
                e1, e2 = st.columns(2)
                e1.metric("영상별 평균 조회수", f"{avg_views:,}")
                e2.metric("참여율", f"{engagement:.2f}%")

        st.divider()

        # -------------------------
        # 예상 수익
        # -------------------------
        st.subheader("💰 예상 월 광고 수익")

        c1, c2, c3 = st.columns(3)
        c1.metric("보수적", f"${revenue['monthly_low']:,.0f}")
        c2.metric("평균",   f"${revenue['monthly_avg']:,.0f}")
        c3.metric("낙관적", f"${revenue['monthly_high']:,.0f}")

        st.info("실제 수익은 국가, CPM, RPM, 광고 유형, 멤버십, 협찬 등에 따라 달라질 수 있습니다.\n수익 추정은 최근 영상 평균 조회수 × 월 4편 업로드 기준입니다.")

        st.divider()

        # -------------------------
        # 최근 영상 목록
        # -------------------------
        st.subheader(f"🎬 최근 영상 {len(videos)}개")

        df = pd.DataFrame(videos)
        df["업로드일"] = pd.to_datetime(
            df["업로드일"], format="%Y%m%d", errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        st.dataframe(
            df[["제목", "조회수", "좋아요", "업로드일"]],
            use_container_width=True
        )

        st.subheader("📊 영상별 조회수")

        fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
        titles = [t[:20] + "..." if len(t) > 20 else t for t in df["제목"]]
        ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
        ax.set_xlabel("조회수")
        ax.set_title("최근 영상 조회수 비교")
        plt.tight_layout()
        st.pyplot(fig)

    except Exception as e:
        st.error(f"오류 발생: {e}")
        st.exception(e)  # 개발 중 디버깅용 — 배포 시 제거 가능
