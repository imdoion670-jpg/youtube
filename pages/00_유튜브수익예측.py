import streamlit as st
import requests
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
st.set_page_config(page_title="YouTube 수익 분석기", page_icon="📺", layout="wide")
st.title("📺 유튜브 채널 수익 분석기")
st.markdown("채널명을 입력하면 구독자 수, 조회수, 예상 수익, 최근 영상 목록을 분석합니다.")

# -------------------------
# API 키 입력
# -------------------------
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input(
        "YouTube Data API v3 키",
        type="password",
        help="Google Cloud Console에서 발급받은 API 키를 입력하세요."
    )
    st.markdown("""
    **API 키 발급 방법:**
    1. [Google Cloud Console](https://console.cloud.google.com/) 접속
    2. 프로젝트 생성
    3. YouTube Data API v3 활성화
    4. 사용자 인증 정보 → API 키 생성
    """)

# -------------------------
# 입력
# -------------------------
channel_name = st.text_input("유튜브 채널명", placeholder="예: 슛박스  또는  @shootbox")
recent_count = st.slider("최근 영상 수", 5, 50, 10, 5)

BASE = "https://www.googleapis.com/youtube/v3"


# -------------------------
# STEP 1: 채널명 → channel_id
# -------------------------
def search_channel(name: str, key: str):
    # @핸들 형식이면 handle로 직접 조회
    if name.startswith("@"):
        url = f"{BASE}/channels"
        params = {"part": "snippet,statistics", "forHandle": name.lstrip("@"), "key": key}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
        if items:
            return items[0]

    # 일반 검색
    url = f"{BASE}/search"
    params = {"part": "snippet", "q": name, "type": "channel", "maxResults": 5, "key": key}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None

    # 첫 번째 채널의 channel_id로 통계 조회
    channel_id = items[0]["id"]["channelId"]
    url2 = f"{BASE}/channels"
    params2 = {"part": "snippet,statistics,brandingSettings", "id": channel_id, "key": key}
    r2 = requests.get(url2, params=params2, timeout=10)
    r2.raise_for_status()
    items2 = r2.json().get("items", [])
    return items2[0] if items2 else None


# -------------------------
# STEP 2: channel_id → 최근 영상 목록
# -------------------------
def get_recent_videos(channel_id: str, count: int, key: str):
    # uploads 플레이리스트 ID 가져오기
    url = f"{BASE}/channels"
    params = {"part": "contentDetails", "id": channel_id, "key": key}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return []

    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 플레이리스트에서 영상 ID 수집
    video_ids = []
    next_page = None
    while len(video_ids) < count:
        url2 = f"{BASE}/playlistItems"
        params2 = {
            "part": "contentDetails",
            "playlistId": uploads_id,
            "maxResults": min(count - len(video_ids), 50),
            "key": key,
        }
        if next_page:
            params2["pageToken"] = next_page
        r2 = requests.get(url2, params=params2, timeout=10)
        r2.raise_for_status()
        data = r2.json()
        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        next_page = data.get("nextPageToken")
        if not next_page:
            break

    if not video_ids:
        return []

    # 영상 통계 일괄 조회 (최대 50개)
    url3 = f"{BASE}/videos"
    params3 = {
        "part": "snippet,statistics",
        "id": ",".join(video_ids[:50]),
        "key": key,
    }
    r3 = requests.get(url3, params=params3, timeout=10)
    r3.raise_for_status()

    videos = []
    for item in r3.json().get("items", []):
        snip = item["snippet"]
        stat = item.get("statistics", {})
        videos.append({
            "제목": snip.get("title", ""),
            "조회수": int(stat.get("viewCount", 0) or 0),
            "좋아요": int(stat.get("likeCount", 0) or 0),
            "댓글수": int(stat.get("commentCount", 0) or 0),
            "업로드일": snip.get("publishedAt", "")[:10],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
        })

    return videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views: int, num_videos: int):
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
    if not api_key:
        st.error("왼쪽 사이드바에 YouTube API 키를 입력해주세요.")
        st.stop()
    if not channel_name.strip():
        st.error("채널명을 입력하세요.")
        st.stop()

    name = channel_name.strip()

    with st.spinner("① 채널 검색 중..."):
        try:
            channel = search_channel(name, api_key)
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                st.error("API 키 오류 또는 할당량 초과입니다. API 키를 확인하세요.")
            else:
                st.error(f"API 오류: {e}")
            st.stop()
        except Exception as e:
            st.error(f"오류: {e}")
            st.stop()

    if not channel:
        st.error(f"'{name}' 채널을 찾지 못했습니다. 채널명을 정확히 입력하거나 @핸들을 사용해보세요.")
        st.stop()

    channel_id = channel["id"]
    snip = channel["snippet"]
    stat = channel.get("statistics", {})

    subscribers = int(stat.get("subscriberCount", 0) or 0)
    total_vid_count = int(stat.get("videoCount", 0) or 0)
    thumbnail = snip.get("thumbnails", {}).get("high", {}).get("url", "")
    title = snip.get("title", name)

    with st.spinner(f"② 최근 영상 {recent_count}개 수집 중..."):
        try:
            videos = get_recent_videos(channel_id, recent_count, api_key)
        except Exception as e:
            st.error(f"영상 목록 수집 오류: {e}")
            st.stop()

    if not videos:
        st.error("영상 목록을 가져오지 못했습니다.")
        st.stop()

    total_views = sum(v["조회수"] for v in videos)
    revenue = estimate_revenue(total_views, len(videos))

    # --- 채널 정보 ---
    col1, col2 = st.columns([1, 3])
    with col1:
        if thumbnail:
            st.image(thumbnail, width=180)
    with col2:
        st.subheader(title)
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{subscribers:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{total_views:,}")
        m3.metric("전체 영상 수", f"{total_vid_count:,}")

        if subscribers > 0 and total_views > 0:
            avg_v = total_views // len(videos)
            eng = avg_v / subscribers * 100
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
    st.dataframe(df[["제목", "조회수", "좋아요", "댓글수", "업로드일"]], use_container_width=True)

    # --- 차트 ---
    st.subheader("📊 영상별 조회수")
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
    titles = [t[:22] + "…" if len(t) > 22 else t for t in df["제목"]]
    ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
    ax.set_xlabel("조회수")
    ax.set_title("최근 영상 조회수 비교")
    plt.tight_layout()
    st.pyplot(fig)
