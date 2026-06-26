import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
import urllib.request
import requests

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
# 사이드바: API 키 입력
# -------------------------
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input(
        "YouTube Data API v3 키",
        type="password",
        help="https://console.cloud.google.com 에서 발급"
    )
    st.markdown("""
    **API 키 발급 방법:**
    1. [Google Cloud Console](https://console.cloud.google.com) 접속
    2. 프로젝트 생성
    3. YouTube Data API v3 활성화
    4. 사용자 인증 정보 → API 키 생성
    """)

# -------------------------
# 입력
# -------------------------
channel_name = st.text_input("유튜브 채널명", placeholder="예: 슛박스  또는  @shootboxofficial")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)

BASE = "https://www.googleapis.com/youtube/v3"


# -------------------------
# STEP 1: 채널 검색
# -------------------------
def search_channel(name: str, key: str) -> dict | None:
    """채널명으로 검색해서 채널 ID 반환"""
    # @핸들 형식이면 핸들로 직접 조회
    if name.startswith("@"):
        r = requests.get(f"{BASE}/channels", params={
            "part": "snippet,statistics",
            "forHandle": name.lstrip("@"),
            "key": key,
        })
        data = r.json()
        items = data.get("items", [])
        if items:
            return items[0]

    # 일반 검색
    r = requests.get(f"{BASE}/search", params={
        "part": "snippet",
        "q": name,
        "type": "channel",
        "maxResults": 5,
        "key": key,
    })
    data = r.json()

    if "error" in data:
        raise Exception(data["error"]["message"])

    items = data.get("items", [])
    if not items:
        return None

    # 첫 번째 채널 ID로 상세 정보 조회
    channel_id = items[0]["snippet"]["channelId"]
    return get_channel_by_id(channel_id, key)


def get_channel_by_id(channel_id: str, key: str) -> dict | None:
    r = requests.get(f"{BASE}/channels", params={
        "part": "snippet,statistics,contentDetails",
        "id": channel_id,
        "key": key,
    })
    data = r.json()
    items = data.get("items", [])
    return items[0] if items else None


# -------------------------
# STEP 2: 최근 영상 목록
# -------------------------
def get_recent_videos(channel: dict, count: int, key: str) -> list:
    """업로드 플레이리스트에서 최근 영상 ID 가져오기"""
    uploads_id = (
        channel.get("contentDetails", {})
               .get("relatedPlaylists", {})
               .get("uploads", "")
    )
    if not uploads_id:
        return []

    r = requests.get(f"{BASE}/playlistItems", params={
        "part": "contentDetails",
        "playlistId": uploads_id,
        "maxResults": count,
        "key": key,
    })
    data = r.json()

    if "error" in data:
        raise Exception(data["error"]["message"])

    video_ids = [
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
    ]
    if not video_ids:
        return []

    # 영상 상세 정보 (조회수, 좋아요 등)
    r2 = requests.get(f"{BASE}/videos", params={
        "part": "snippet,statistics",
        "id": ",".join(video_ids),
        "key": key,
    })
    data2 = r2.json()

    videos = []
    for item in data2.get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        videos.append({
            "제목": snippet.get("title", ""),
            "조회수": int(stats.get("viewCount", 0) or 0),
            "좋아요": int(stats.get("likeCount", 0) or 0),
            "업로드일": snippet.get("publishedAt", "")[:10],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
        })

    return videos


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

    if not api_key:
        st.error("왼쪽 사이드바에 YouTube API 키를 입력해주세요.")
        st.stop()

    name = channel_name.strip()

    try:
        with st.spinner("① 채널 검색 중..."):
            channel = search_channel(name, api_key)

        if not channel:
            st.error(f"**'{name}' 채널을 찾지 못했습니다.**\n\n"
                     "`@영문핸들` 형식(예: `@shootboxofficial`)으로 입력해보세요.")
            st.stop()

        with st.spinner("② 최근 영상 수집 중..."):
            videos = get_recent_videos(channel, recent_count, api_key)

        if not videos:
            st.error("영상 목록을 가져오지 못했습니다.")
            st.stop()

    except Exception as e:
        st.error(f"API 오류: {e}")
        st.stop()

    # 데이터 정리
    snippet = channel.get("snippet", {})
    stats   = channel.get("statistics", {})
    subs    = int(stats.get("subscriberCount", 0) or 0)
    total_vids = int(stats.get("videoCount", 0) or 0)
    total_views = sum(v["조회수"] for v in videos)
    revenue = estimate_revenue(total_views, len(videos))

    thumb = ""
    thumbs = snippet.get("thumbnails", {})
    for q in ["high", "medium", "default"]:
        if q in thumbs:
            thumb = thumbs[q].get("url", "")
            break

    # --- 채널 정보 ---
    col1, col2 = st.columns([1, 3])
    with col1:
        if thumb:
            st.image(thumb, width=180)
    with col2:
        st.subheader(snippet.get("title", name))
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{subs:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{total_views:,}")
        m3.metric("영상 수", f"{total_vids:,}")

        if subs > 0 and total_views > 0:
            avg_v = total_views // len(videos)
            eng   = avg_v / subs * 100
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
