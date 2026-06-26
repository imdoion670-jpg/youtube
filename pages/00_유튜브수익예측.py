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
st.markdown("채널명을 입력하면 구독자 수, 조회수, 예상 수익, 최근 영상 목록을 분석합니다.")

# -------------------------
# 입력
# -------------------------
channel_name = st.text_input("유튜브 채널명", placeholder="예: 침착맨  또는  @chimchakman")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)


# ====================================================
# STEP 1: 채널명 → 채널 URL + 채널 메타 확보
# ====================================================
def find_channel_url(name: str) -> tuple:
    """
    채널명으로 검색해서 (channel_url, channel_meta_dict) 반환.
    extract_flat 없이 검색 결과 3개만 가져와서 channel_url 추출.
    """
    search_opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        # extract_flat 사용하지 않음 — 영상 메타에서 channel_url 직접 접근
        "playlistend": 3,
        "skip_download": True,
    }

    queries = [
        f"ytsearch3:{name}",          # 일반 검색
        f"ytsearch3:{name} 유튜브",    # 검색어 보강
    ]

    for q in queries:
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                result = ydl.extract_info(q, download=False)
            for entry in (result.get("entries") or []):
                if not entry:
                    continue
                ch_url = entry.get("channel_url") or entry.get("uploader_url")
                if ch_url:
                    meta = {
                        "title": entry.get("channel") or entry.get("uploader", name),
                        "thumbnail": entry.get("thumbnail", ""),
                        "subscribers": entry.get("channel_follower_count", 0) or 0,
                    }
                    return ch_url, meta
        except Exception:
            continue

    return None, {}


# ====================================================
# STEP 2: 채널 URL → 영상 목록 (ID만 빠르게)
# ====================================================
def fetch_video_ids(channel_url: str, count: int) -> tuple:
    """
    채널의 /videos 탭에서 영상 ID 목록과 채널 메타 반환.
    extract_flat=True 로 빠르게 ID만 수집.
    """
    tabs = [
        channel_url.rstrip("/") + "/videos",
        channel_url.rstrip("/"),
    ]

    list_opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": True,
        "playlistend": count,
    }

    for tab_url in tabs:
        try:
            with yt_dlp.YoutubeDL(list_opts) as ydl:
                info = ydl.extract_info(tab_url, download=False)

            if not info:
                continue

            # entries 수집 — 중첩 구조 처리
            raw = info.get("entries") or []
            ids = []
            for e in raw:
                if not e:
                    continue
                # 중첩 playlist (Shorts/Live/Videos 탭 묶음)
                if e.get("_type") == "playlist":
                    for sub in (e.get("entries") or []):
                        if sub and sub.get("id"):
                            ids.append(sub["id"])
                else:
                    vid_id = e.get("id")
                    if vid_id:
                        ids.append(vid_id)

            if ids:
                channel_meta = {
                    "title": info.get("channel") or info.get("uploader", ""),
                    "thumbnail": (info.get("thumbnails") or [{}])[-1].get("url", ""),
                    "subscribers": info.get("channel_follower_count", 0) or 0,
                    "total_videos": info.get("playlist_count", 0) or 0,
                }
                return ids[:count], channel_meta

        except Exception:
            continue

    return [], {}


# ====================================================
# STEP 3: 영상 ID → 상세 정보 (조회수 등)
# ====================================================
def fetch_single_video(video_id: str) -> dict | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
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


def fetch_videos_parallel(video_ids: list, max_workers: int = 6) -> list:
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_single_video, vid): vid for vid in video_ids}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                videos.append(res)
    videos.sort(key=lambda x: x["업로드일"], reverse=True)
    return videos


# ====================================================
# 메인 파이프라인
# ====================================================
def get_channel_stats(channel_name: str, recent_count: int):
    # 1) 채널 URL 탐색
    channel_url, meta_from_search = find_channel_url(channel_name)
    if not channel_url:
        return None, None

    # 2) 영상 ID 목록 수집
    video_ids, meta_from_channel = fetch_video_ids(channel_url, recent_count)
    if not video_ids:
        return None, None

    # 3) 영상 상세 정보 병렬 수집
    videos = fetch_videos_parallel(video_ids)
    if not videos:
        return None, None

    # 메타 합치기 (채널 페이지 우선, 검색 결과 보완)
    total_views = sum(v["조회수"] for v in videos)
    channel_data = {
        "title": (
            meta_from_channel.get("title")
            or meta_from_search.get("title")
            or channel_name
        ),
        "thumbnail": (
            meta_from_channel.get("thumbnail")
            or meta_from_search.get("thumbnail")
            or ""
        ),
        "subscribers": (
            meta_from_channel.get("subscribers")
            or meta_from_search.get("subscribers")
            or 0
        ),
        "views": total_views,
        "videos": meta_from_channel.get("total_videos") or len(videos),
    }

    return channel_data, videos


# ====================================================
# 수익 추정
# ====================================================
def estimate_revenue(total_views: int, num_videos: int) -> dict:
    avg = total_views / max(num_videos, 1)
    monthly_views = avg * 4  # 월 4편 가정
    return {
        "low":  monthly_views / 1000 * 1,
        "avg":  monthly_views / 1000 * 3,
        "high": monthly_views / 1000 * 8,
    }


# ====================================================
# UI — 분석 실행
# ====================================================
if st.button("분석하기"):
    if not channel_name.strip():
        st.error("채널명을 입력하세요.")
        st.stop()

    progress = st.empty()

    with progress.container():
        with st.spinner("채널 URL 탐색 중..."):
            channel_url, meta = find_channel_url(channel_name.strip())

        if not channel_url:
            st.error(
                "채널을 찾지 못했습니다.\n\n"
                "**팁:** `@영문핸들` 형식(예: `@chimchakman`)으로 입력해 보세요."
            )
            st.stop()

        with st.spinner(f"영상 목록 수집 중..."):
            video_ids, ch_meta = fetch_video_ids(channel_url, recent_count)

        if not video_ids:
            st.error("영상 목록을 가져오지 못했습니다. 채널에 공개 영상이 없거나 접근이 제한되어 있습니다.")
            st.stop()

        with st.spinner(f"영상 {len(video_ids)}개 조회수 수집 중..."):
            videos = fetch_videos_parallel(video_ids)

    progress.empty()

    if not videos:
        st.error("영상 상세 정보를 가져오지 못했습니다.")
        st.stop()

    total_views = sum(v["조회수"] for v in videos)
    channel_data = {
        "title": ch_meta.get("title") or meta.get("title") or channel_name,
        "thumbnail": ch_meta.get("thumbnail") or meta.get("thumbnail") or "",
        "subscribers": ch_meta.get("subscribers") or meta.get("subscribers") or 0,
        "views": total_views,
        "videos": ch_meta.get("total_videos") or len(videos),
    }
    revenue = estimate_revenue(total_views, len(videos))

    # --- 채널 정보 ---
    col1, col2 = st.columns([1, 3])
    with col1:
        if channel_data["thumbnail"]:
            st.image(channel_data["thumbnail"], width=180)
    with col2:
        st.subheader(channel_data["title"])
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{channel_data['subscribers']:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{total_views:,}")
        m3.metric("영상 수", f"{channel_data['videos']:,}")

        if channel_data["subscribers"] > 0 and total_views > 0:
            avg_views = total_views // len(videos)
            engagement = avg_views / channel_data["subscribers"] * 100
            e1, e2 = st.columns(2)
            e1.metric("영상별 평균 조회수", f"{avg_views:,}")
            e2.metric("참여율", f"{engagement:.2f}%")

    st.divider()

    # --- 예상 수익 ---
    st.subheader("💰 예상 월 광고 수익")
    c1, c2, c3 = st.columns(3)
    c1.metric("보수적", f"${revenue['low']:,.0f}")
    c2.metric("평균",   f"${revenue['avg']:,.0f}")
    c3.metric("낙관적", f"${revenue['high']:,.0f}")
    st.info("추정 기준: 평균 조회수 × 월 4편 / CPM $1~$8 (국가·광고 유형에 따라 상이)")

    st.divider()

    # --- 영상 목록 ---
    st.subheader(f"🎬 최근 영상 {len(videos)}개")
    df = pd.DataFrame(videos)
    df["업로드일"] = pd.to_datetime(
        df["업로드일"], format="%Y%m%d", errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    st.dataframe(df[["제목", "조회수", "좋아요", "업로드일"]], use_container_width=True)

    # --- 차트 ---
    st.subheader("📊 영상별 조회수")
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
    titles = [t[:22] + "…" if len(t) > 22 else t for t in df["제목"]]
    ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
    ax.set_xlabel("조회수")
    ax.set_title("최근 영상 조회수 비교")
    plt.tight_layout()
    st.pyplot(fig)
