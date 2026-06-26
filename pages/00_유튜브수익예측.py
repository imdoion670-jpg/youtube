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

channel_name = st.text_input("유튜브 채널명", placeholder="예: 침착맨  또는  @chimchakman")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)


# -------------------------
# 핵심: 영상 한 개에서 channel_url 뽑기
# -------------------------
def get_channel_url_from_search(name: str):
    """
    ytsearch로 영상 1개를 완전히 파싱해서 channel_url 반환.
    extract_flat 사용 안 함 — flat 모드에선 channel_url이 없을 수 있음.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "skip_download": True,
        # extract_flat 없음 → 영상 메타 전체 파싱
    }
    queries = [name, f"{name} channel"]
    for q in queries:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.extract_info(f"ytsearch5:{q}", download=False)
            for entry in (result.get("entries") or []):
                if not entry:
                    continue
                ch_url = entry.get("channel_url") or entry.get("uploader_url")
                if ch_url:
                    return ch_url, {
                        "title": entry.get("channel") or entry.get("uploader", name),
                        "thumbnail": entry.get("thumbnail", ""),
                        "subscribers": entry.get("channel_follower_count", 0) or 0,
                    }
        except Exception:
            continue
    return None, {}


# -------------------------
# 채널 URL → 영상 ID 목록
# -------------------------
def get_video_ids_from_channel(channel_url: str, count: int):
    """
    채널 URL의 /videos 탭에서 영상 ID를 추출.
    extract_flat=True로 빠르게, 중첩 구조 처리.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": True,
        "playlistend": count * 3,  # 중첩/shorts 포함될 수 있어 여유있게
    }

    urls_to_try = [
        channel_url.rstrip("/") + "/videos",
        channel_url.rstrip("/"),
    ]

    for url in urls_to_try:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                continue

            ids = []
            raw_entries = info.get("entries") or []

            for e in raw_entries:
                if not e:
                    continue
                # 중첩 playlist (Shorts/Live 탭 등)
                if e.get("_type") == "playlist":
                    for sub in (e.get("entries") or []):
                        if sub and sub.get("id"):
                            ids.append(sub["id"])
                elif e.get("id"):
                    ids.append(e["id"])

            # 중복 제거 후 count개
            seen = set()
            unique_ids = []
            for i in ids:
                if i not in seen:
                    seen.add(i)
                    unique_ids.append(i)
                if len(unique_ids) >= count:
                    break

            if unique_ids:
                ch_meta = {
                    "title": info.get("channel") or info.get("uploader", ""),
                    "thumbnail": (info.get("thumbnails") or [{}])[-1].get("url", ""),
                    "subscribers": info.get("channel_follower_count", 0) or 0,
                    "total_videos": info.get("playlist_count", 0) or 0,
                }
                return unique_ids, ch_meta

        except Exception:
            continue

    return [], {}


# -------------------------
# 영상 ID → 상세 정보
# -------------------------
def fetch_single_video(video_id: str):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
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


def fetch_all_videos(video_ids: list):
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_single_video, vid): vid for vid in video_ids}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                videos.append(res)
    videos.sort(key=lambda x: x["업로드일"], reverse=True)
    return videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views, num_videos):
    avg = total_views / max(num_videos, 1)
    monthly = avg * 4
    return {
        "low":  monthly / 1000 * 1,
        "avg":  monthly / 1000 * 3,
        "high": monthly / 1000 * 8,
    }


# -------------------------
# 분석 실행
# -------------------------
if st.button("분석하기"):
    if not channel_name.strip():
        st.error("채널명을 입력하세요.")
        st.stop()

    name = channel_name.strip()

    # STEP 1
    with st.spinner("① 채널 검색 중..."):
        channel_url, search_meta = get_channel_url_from_search(name)

    if not channel_url:
        st.error(f"**'{name}' 채널을 찾지 못했습니다.**\n\n"
                 "아래 방법을 시도해보세요:\n"
                 "- `@영문핸들` 형식으로 입력 (예: `@chimchakman`)\n"
                 "- 채널의 정확한 이름으로 입력\n"
                 "- 유튜브에서 채널 URL을 직접 복사해서 입력")
        st.stop()

    # STEP 2
    with st.spinner("② 영상 목록 수집 중..."):
        video_ids, ch_meta = get_video_ids_from_channel(channel_url, recent_count)

    if not video_ids:
        st.error("영상 목록을 가져오지 못했습니다.\n채널에 공개 영상이 없거나 yt-dlp가 해당 채널 구조를 지원하지 않을 수 있습니다.")
        st.stop()

    # STEP 3
    with st.spinner(f"③ 영상 {len(video_ids)}개 조회수 수집 중 (시간이 걸릴 수 있습니다)..."):
        videos = fetch_all_videos(video_ids)

    if not videos:
        st.error("영상 상세 정보 수집에 실패했습니다.")
        st.stop()

    # 최종 채널 데이터 조합
    total_views = sum(v["조회수"] for v in videos)
    data = {
        "title":       ch_meta.get("title") or search_meta.get("title") or name,
        "thumbnail":   ch_meta.get("thumbnail") or search_meta.get("thumbnail") or "",
        "subscribers": ch_meta.get("subscribers") or search_meta.get("subscribers") or 0,
        "views":       total_views,
        "videos":      ch_meta.get("total_videos") or len(videos),
    }
    revenue = estimate_revenue(total_views, len(videos))

    # --- 채널 정보 ---
    col1, col2 = st.columns([1, 3])
    with col1:
        if data["thumbnail"]:
            st.image(data["thumbnail"], width=180)
    with col2:
        st.subheader(data["title"])
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{data['subscribers']:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{total_views:,}")
        m3.metric("영상 수", f"{data['videos']:,}")
        if data["subscribers"] > 0 and total_views > 0:
            avg_v = total_views // len(videos)
            eng = avg_v / data["subscribers"] * 100
            e1, e2 = st.columns(2)
            e1.metric("영상별 평균 조회수", f"{avg_v:,}")
            e2.metric("참여율", f"{eng:.2f}%")

    st.divider()

    # --- 수익 ---
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
