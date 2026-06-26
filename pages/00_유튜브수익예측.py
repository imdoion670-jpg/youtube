import streamlit as st
import yt_dlp
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
import urllib.request
import concurrent.futures
import tempfile
import os

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

# -------------------------
# 쿠키 안내 & 입력
# -------------------------
with st.sidebar:
    st.header("⚙️ 설정")
    st.markdown("""
### 🍪 쿠키 설정 (필수)
YouTube 봇 차단을 우회하려면 브라우저 쿠키가 필요합니다.

**쿠키 파일 내보내기:**
1. Chrome/Edge에서 **[EditThisCookie](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)** 또는 **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** 확장 설치
2. [youtube.com](https://youtube.com) 접속 후 로그인
3. 확장 아이콘 클릭 → **Export as cookies.txt**
4. 아래에 파일 업로드
""")
    cookie_file = st.file_uploader("cookies.txt 업로드", type=["txt"], label_visibility="collapsed")
    
    if cookie_file:
        st.success("✅ 쿠키 로드됨")
    else:
        st.warning("⚠️ 쿠키 없으면 봇 차단될 수 있음")

st.markdown("채널명을 입력하면 구독자 수, 조회수, 예상 수익, 최근 영상 목록을 분석합니다.")

channel_name = st.text_input("유튜브 채널명", placeholder="예: 너덜트  또는  @neodult")
recent_count = st.slider("최근 영상 수", 5, 20, 10, 5)


# -------------------------
# 쿠키 파일 임시 저장
# -------------------------
def get_cookie_path(cookie_file) -> str | None:
    if not cookie_file:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
    tmp.write(cookie_file.read())
    tmp.close()
    return tmp.name


# -------------------------
# yt-dlp 기본 옵션 (쿠키 포함)
# -------------------------
def base_opts(cookie_path: str | None, extra: dict = {}) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "skip_download": True,
        # 봇 우회 옵션
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        },
    }
    if cookie_path:
        opts["cookiefile"] = cookie_path
    opts.update(extra)
    return opts


# -------------------------
# STEP 1: 채널 URL 확보
# -------------------------
def find_channel_url(name: str, cookie_path: str | None):
    opts = base_opts(cookie_path)  # extract_flat 없음 → 완전 파싱

    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(f"ytsearch5:{name}", download=False)

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
    return None, {}


# -------------------------
# STEP 2: 영상 ID 목록
# -------------------------
def get_video_ids(channel_url: str, count: int, cookie_path: str | None):
    opts = base_opts(cookie_path, {
        "extract_flat": True,
        "playlistend": count,
    })

    for tab in [channel_url.rstrip("/") + "/videos", channel_url.rstrip("/")]:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(tab, download=False)
            if not info:
                continue

            entries = info.get("entries") or []
            # 중첩 탭 구조 처리
            if entries and entries[0] and entries[0].get("_type") == "playlist":
                entries = entries[0].get("entries") or []

            ids = [e["id"] for e in entries if e and e.get("id")]
            if ids:
                meta = {
                    "title": info.get("channel") or info.get("uploader", ""),
                    "thumbnail": (info.get("thumbnails") or [{}])[-1].get("url", ""),
                    "subscribers": info.get("channel_follower_count", 0) or 0,
                    "total_videos": info.get("playlist_count", 0) or 0,
                }
                return ids[:count], meta
        except Exception:
            continue
    return [], {}


# -------------------------
# STEP 3: 영상 상세 정보
# -------------------------
def fetch_video(video_id: str, cookie_path: str | None) -> dict | None:
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = base_opts(cookie_path)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "제목": info.get("title", ""),
            "조회수": info.get("view_count", 0) or 0,
            "좋아요": info.get("like_count", 0) or 0,
            "업로드일": (info.get("upload_date", "") or "")[:8],
            "_subscribers": info.get("channel_follower_count", 0) or 0,
            "_thumbnail": info.get("thumbnail", ""),
            "_channel": info.get("channel", ""),
        }
    except Exception:
        return None


def fetch_all(video_ids: list, cookie_path: str | None) -> list:
    videos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_video, vid, cookie_path): vid for vid in video_ids}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                videos.append(res)
    videos.sort(key=lambda x: x["업로드일"], reverse=True)
    return videos


# -------------------------
# 수익 추정
# -------------------------
def estimate_revenue(total_views: int, num_videos: int) -> dict:
    avg = total_views / max(num_videos, 1)
    monthly = avg * 4
    return {"low": monthly/1000*1, "avg": monthly/1000*3, "high": monthly/1000*8}


# -------------------------
# 분석 실행
# -------------------------
if st.button("분석하기"):
    if not channel_name.strip():
        st.error("채널명을 입력하세요.")
        st.stop()

    name = channel_name.strip()
    cookie_path = get_cookie_path(cookie_file)

    try:
        with st.spinner("① 채널 검색 중..."):
            ch_url, search_meta = find_channel_url(name, cookie_path)

        if not ch_url:
            st.error("채널을 찾지 못했습니다. `@영문핸들` 형식으로 입력해보세요.")
            st.stop()

        with st.spinner("② 영상 목록 수집 중..."):
            video_ids, ch_meta = get_video_ids(ch_url, recent_count, cookie_path)

        if not video_ids:
            st.error("영상 목록을 가져오지 못했습니다.")
            st.stop()

        with st.spinner(f"③ 영상 {len(video_ids)}개 조회수 수집 중..."):
            videos = fetch_all(video_ids, cookie_path)

    except Exception as e:
        st.error(f"오류: {e}")
        st.stop()
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.unlink(cookie_path)

    if not videos:
        st.error("영상 정보를 가져오지 못했습니다.")
        st.stop()

    total_views = sum(v["조회수"] for v in videos)
    data = {
        "title":        ch_meta.get("title") or search_meta.get("title") or name,
        "thumbnail":    ch_meta.get("thumbnail") or search_meta.get("thumbnail") or videos[0].get("_thumbnail", ""),
        "subscribers":  ch_meta.get("subscribers") or search_meta.get("subscribers") or videos[0].get("_subscribers", 0),
        "views":        total_views,
        "total_videos": ch_meta.get("total_videos") or len(videos),
    }
    revenue = estimate_revenue(total_views, len(videos))

    # 채널 정보
    col1, col2 = st.columns([1, 3])
    with col1:
        if data["thumbnail"]:
            st.image(data["thumbnail"], width=180)
    with col2:
        st.subheader(data["title"])
        m1, m2, m3 = st.columns(3)
        m1.metric("구독자", f"{data['subscribers']:,}")
        m2.metric(f"총 조회수 (최근 {len(videos)}개)", f"{total_views:,}")
        m3.metric("영상 수", f"{data['total_videos']:,}")
        if data["subscribers"] > 0 and total_views > 0:
            avg_v = total_views // len(videos)
            eng = avg_v / data["subscribers"] * 100
            e1, e2 = st.columns(2)
            e1.metric("영상별 평균 조회수", f"{avg_v:,}")
            e2.metric("참여율", f"{eng:.2f}%")

    st.divider()

    st.subheader("💰 예상 월 광고 수익")
    c1, c2, c3 = st.columns(3)
    c1.metric("보수적", f"${revenue['low']:,.0f}")
    c2.metric("평균",   f"${revenue['avg']:,.0f}")
    c3.metric("낙관적", f"${revenue['high']:,.0f}")
    st.info("추정 기준: 평균 조회수 × 월 4편 / CPM $1~$8")

    st.divider()

    st.subheader(f"🎬 최근 영상 {len(videos)}개")
    df = pd.DataFrame(videos)[["제목", "조회수", "좋아요", "업로드일"]].copy()
    df["업로드일"] = pd.to_datetime(df["업로드일"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    st.dataframe(df, use_container_width=True)

    st.subheader("📊 영상별 조회수")
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))
    titles = [t[:22] + "…" if len(t) > 22 else t for t in df["제목"]]
    ax.barh(titles[::-1], df["조회수"][::-1], color="#4f86c6")
    ax.set_xlabel("조회수")
    ax.set_title("최근 영상 조회수 비교")
    plt.tight_layout()
    st.pyplot(fig)
