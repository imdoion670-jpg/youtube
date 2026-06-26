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

channel_name = st.text_input("유튜브 채널명", placeholder="예: 슛박스  또는  @shootboxofficial")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)


# -------------------------
# 핵심 함수
# -------------------------

def fetch_video_detail(video_id: str) -> dict | None:
    """영상 ID로 상세 정보(조회수 등) 가져오기"""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "제목": info.get("title", ""),
            "조회수": info.get("view_count", 0) or 0,
            "좋아요": info.get("like_count", 0) or 0,
            "업로드일": (info.get("upload_date", "") or "")[:8],
            "url": info.get("webpage_url", url),
            "_channel": info.get("channel", ""),
            "_channel_url": info.get("channel_url", ""),
            "_subscribers": info.get("channel_follower_count", 0) or 0,
            "_thumbnail": info.get("thumbnail", ""),
        }
    except Exception:
        return None


def get_channel_videos(channel_name: str, count: int):
    """
    전략:
    1) ytsearch로 영상 1개를 완전 파싱 → channel_url 확보
    2) channel_url/videos 를 extract_flat으로 영상 ID 목록 수집
    3) 각 영상 ID를 병렬로 상세 파싱
    """

    # --- STEP 1: 영상 1개 완전 파싱으로 channel_url 확보 ---
    search_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # extract_flat 없음 → 상세 파싱
    }
    channel_url = None
    channel_meta = {}

    with yt_dlp.YoutubeDL(search_opts) as ydl:
        result = ydl.extract_info(f"ytsearch5:{channel_name}", download=False)

    for entry in (result.get("entries") or []):
        if not entry:
            continue
        ch = entry.get("channel", "") or ""
        ch_url = entry.get("channel_url") or entry.get("uploader_url") or ""

        # 채널명이 검색어와 비슷한 entry 우선
        if ch_url:
            channel_url = ch_url
            channel_meta = {
                "title": ch,
                "thumbnail": entry.get("thumbnail", ""),
                "subscribers": entry.get("channel_follower_count", 0) or 0,
            }
            # 채널명이 검색어와 일치하면 바로 확정
            if channel_name.replace("@", "").lower() in ch.lower():
                break

    if not channel_url:
        return None, None

    # --- STEP 2: channel_url/videos 에서 영상 ID 목록 ---
    list_opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": True,
        "playlistend": count,
    }

    video_ids = []
    for tab_url in [channel_url + "/videos", channel_url]:
        try:
            with yt_dlp.YoutubeDL(list_opts) as ydl:
                info = ydl.extract_info(tab_url, download=False)

            if not info:
                continue

            entries = info.get("entries") or []

            # 채널 탭이 중첩된 경우 (Videos / Shorts / Live)
            if entries and entries[0] and entries[0].get("_type") == "playlist":
                # 첫 번째 탭(Videos)의 entries 사용
                entries = entries[0].get("entries") or []

            ids = [e["id"] for e in entries if e and e.get("id")]

            if ids:
                # 채널 메타 보강
                channel_meta.update({
                    "title": info.get("channel") or info.get("uploader") or channel_meta.get("title", ""),
                    "thumbnail": (info.get("thumbnails") or [{}])[-1].get("url", "") or channel_meta.get("thumbnail", ""),
                    "subscribers": info.get("channel_follower_count", 0) or channel_meta.get("subscribers", 0),
                    "total_videos": info.get("playlist_count", 0) or 0,
                })
                video_ids = ids[:count]
                break
        except Exception:
            continue

    if not video_ids:
        return None, None

    # --- STEP 3: 병렬로 각 영상 상세 파싱 ---
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_video_detail, vid): vid for vid in video_ids}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                # 첫 영상에서 채널 메타 보강
                if not channel_meta.get("subscribers") and res.get("_subscribers"):
                    channel_meta["subscribers"] = res["_subscribers"]
                if not channel_meta.get("title") and res.get("_channel"):
                    channel_meta["title"] = res["_channel"]
                videos.append(res)

    videos.sort(key=lambda x: x["업로드일"], reverse=True)

    total_views = sum(v["조회수"] for v in videos)
    channel_data = {
        "title":       channel_meta.get("title") or channel_name,
        "thumbnail":   channel_meta.get("thumbnail") or (videos[0]["_thumbnail"] if videos else ""),
        "subscribers": channel_meta.get("subscribers") or 0,
        "views":       total_views,
        "total_videos": channel_meta.get("total_videos") or len(videos),
    }

    return channel_data, videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views: int, num_videos: int) -> dict:
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

    with st.spinner("채널 및 영상 정보 수집 중... (최대 1~2분 소요)"):
        try:
            data, videos = get_channel_videos(name, recent_count)
        except Exception as e:
            st.error(f"오류 발생: {e}")
            st.stop()

    if not data or not videos:
        st.error(
            f"**'{name}' 채널을 찾지 못했습니다.**\n\n"
            "아래 방법을 시도해보세요:\n"
            "- `@영문핸들` 형식으로 입력 (예: `@shootboxofficial`)\n"
            "- 유튜브에서 채널 URL을 직접 복사해서 입력\n"
            "- 채널의 정확한 이름으로 입력"
        )
        st.stop()

    revenue = estimate_revenue(data["views"], len(videos))

    # --- 채널 정보 ---
    col1, col2 = st.columns([1, 3])
    with col1:
        if data["thumbnail"]:
            st.image(data["thumbnail"], width=180)
    with col2:
        st.subheader(data["title"])
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{data['subscribers']:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{data['views']:,}")
        m3.metric("영상 수", f"{data['total_videos']:,}")

        if data["subscribers"] > 0 and data["views"] > 0:
            avg_v = data["views"] // len(videos)
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
    df = df[["제목", "조회수", "좋아요", "업로드일"]].copy()
    df["업로드일"] = pd.to_datetime(df["업로드일"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    st.dataframe(df, use_container_width=True)

    # --- 차트 ---
    st.subheader("📊 영상별 조회수")
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
    titles = [t[:22] + "…" if len(t) > 22 else t for t in df["제목"]]
    ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
    ax.set_xlabel("조회수")
    ax.set_title("최근 영상 조회수 비교")
    plt.tight_layout()
    st.pyplot(fig)
