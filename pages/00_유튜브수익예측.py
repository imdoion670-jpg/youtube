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
st.set_page_config(page_title="YouTube 수익 분석기", page_icon="📺", layout="wide")

st.title("📺 유튜브 채널 수익 분석기")
st.markdown("""
채널명을 입력하면 구독자 수, 총 조회수, 예상 월 광고 수익, 최근 영상 목록 등을 분석합니다.
""")

# -------------------------
# 입력
# -------------------------
channel_name = st.text_input("유튜브 채널명", placeholder="예: 침착맨")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)


# -------------------------
# 유틸: 모든 video entry 평탄화
# -------------------------
def flatten_entries(entries):
    """중첩 playlist 구조를 재귀적으로 펼쳐서 video entry 목록 반환"""
    result = []
    for e in entries or []:
        if not e:
            continue
        if e.get("_type") == "playlist":
            result.extend(flatten_entries(e.get("entries") or []))
        else:
            vid_id = e.get("id") or e.get("url") or ""
            if vid_id:
                result.append(e)
    return result


# -------------------------
# 단일 영상 상세 정보
# -------------------------
def fetch_video(entry):
    try:
        vid_id = entry.get("id") or entry.get("url", "")
        if vid_id.startswith("http"):
            url = vid_id
        else:
            url = f"https://www.youtube.com/watch?v={vid_id}"

        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "제목": info.get("title", ""),
            "조회수": info.get("view_count", 0) or 0,
            "좋아요": info.get("like_count", 0) or 0,
            "업로드일": info.get("upload_date", "") or "",
            "url": info.get("webpage_url", url),
        }
    except Exception:
        return None


# -------------------------
# 채널 탐색 전략 목록
# -------------------------
def build_channel_urls(name: str) -> list:
    """여러 URL 전략을 순서대로 시도할 리스트 반환"""
    encoded = name.strip()
    return [
        f"https://www.youtube.com/@{encoded}/videos",
        f"https://www.youtube.com/c/{encoded}/videos",
        f"https://www.youtube.com/user/{encoded}/videos",
        f"ytsearch15:{encoded}",
    ]


# -------------------------
# 채널 정보 수집 메인
# -------------------------
def get_channel_stats(channel_name: str, recent_count: int):
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": True,
        "playlistend": recent_count,
    }

    channel_info = None
    entries = []

    for url in build_channel_urls(channel_name):
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                continue

            # ytsearch 결과: channel_url 추출 후 채널 재탐색
            if url.startswith("ytsearch"):
                found_url = None
                for e in (info.get("entries") or []):
                    ch_url = (e or {}).get("channel_url")
                    if ch_url:
                        found_url = ch_url + "/videos"
                        break
                if not found_url:
                    continue
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    info = ydl.extract_info(found_url, download=False)
                if not info:
                    continue

            flat = flatten_entries(info.get("entries") or [])
            if flat:
                channel_info = info
                entries = flat[:recent_count]
                break

        except Exception:
            continue

    if not channel_info or not entries:
        return None, None

    # 병렬 영상 상세 수집
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_video, e): e for e in entries}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                videos.append(res)

    if not videos:
        return None, None

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
    avg = total_views / max(num_videos, 1)
    monthly_views = avg * 4  # 월 4편 업로드 가정
    return {
        "monthly_low":  monthly_views / 1000 * 1,
        "monthly_avg":  monthly_views / 1000 * 3,
        "monthly_high": monthly_views / 1000 * 8,
    }


# -------------------------
# 분석 실행
# -------------------------
if st.button("분석하기"):
    if not channel_name.strip():
        st.error("채널명을 입력하세요.")
        st.stop()

    with st.spinner(f"채널 정보 및 최근 영상 {recent_count}개 수집 중..."):
        data, videos = get_channel_stats(channel_name.strip(), recent_count)

    if not data or not videos:
        st.error(
            "채널을 찾을 수 없거나 영상 정보를 가져오지 못했습니다.\n\n"
            "**팁:** `@채널핸들` 형식(예: @chimchakman) 또는 영문 채널명으로 시도해보세요."
        )
        st.stop()

    revenue = estimate_revenue(data["views"], len(videos))

    # 채널 기본 정보
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

        if data["subscribers"] > 0 and data["views"] > 0:
            avg_views = data["views"] // len(videos)
            engagement = avg_views / data["subscribers"] * 100
            e1, e2 = st.columns(2)
            e1.metric("영상별 평균 조회수", f"{avg_views:,}")
            e2.metric("참여율", f"{engagement:.2f}%")

    st.divider()

    # 예상 수익
    st.subheader("💰 예상 월 광고 수익")
    c1, c2, c3 = st.columns(3)
    c1.metric("보수적", f"${revenue['monthly_low']:,.0f}")
    c2.metric("평균",   f"${revenue['monthly_avg']:,.0f}")
    c3.metric("낙관적", f"${revenue['monthly_high']:,.0f}")
    st.info(
        "수익 추정: 최근 영상 평균 조회수 × 월 4편 기준 / CPM $1~$8\n"
        "실제 수익은 국가, 광고 유형, 멤버십, 협찬 등에 따라 다를 수 있습니다."
    )

    st.divider()

    # 최근 영상 목록
    st.subheader(f"🎬 최근 영상 {len(videos)}개")
    df = pd.DataFrame(videos)
    df["업로드일"] = pd.to_datetime(
        df["업로드일"], format="%Y%m%d", errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    st.dataframe(df[["제목", "조회수", "좋아요", "업로드일"]], use_container_width=True)

    # 차트
    st.subheader("📊 영상별 조회수")
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
    titles = [t[:20] + "..." if len(t) > 20 else t for t in df["제목"]]
    ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
    ax.set_xlabel("조회수")
    ax.set_title("최근 영상 조회수 비교")
    plt.tight_layout()
    st.pyplot(fig)
