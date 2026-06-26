import streamlit as st
import pandas as pd
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# -----------------------------
# 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="채널 평균 영상 분석기",
    page_icon="📊",
    layout="wide"
)

st.title("📊 YouTube 채널 평균 영상 분석기")

# -----------------------------
# API KEY
# -----------------------------
API_KEY = st.text_input(
    "YouTube API Key",
    type="password"
)

if API_KEY:
    youtube = build("youtube", "v3", developerKey=API_KEY)

# -----------------------------
# 채널명 입력
# -----------------------------
channel_name = st.text_input(
    "채널명 입력",
    placeholder="예: 침착맨"
)

# -----------------------------
# ISO8601 영상 길이 → 초
# -----------------------------
def duration_to_seconds(duration):

    h = re.search(r'(\d+)H', duration)
    m = re.search(r'(\d+)M', duration)
    s = re.search(r'(\d+)S', duration)

    hours = int(h.group(1)) if h else 0
    minutes = int(m.group(1)) if m else 0
    seconds = int(s.group(1)) if s else 0

    return hours * 3600 + minutes * 60 + seconds

# -----------------------------
# 채널 검색
# -----------------------------
def search_channel(name):

    response = youtube.search().list(
        q=name,
        part="snippet",
        type="channel",
        maxResults=1
    ).execute()

    if not response["items"]:
        return None

    return response["items"][0]["snippet"]["channelId"]

# -----------------------------
# 채널 정보
# -----------------------------
def get_channel_info(channel_id):

    response = youtube.channels().list(
        part="contentDetails,snippet,statistics",
        id=channel_id
    ).execute()

    item = response["items"][0]

    return {
        "title": item["snippet"]["title"],
        "subs": int(item["statistics"].get("subscriberCount", 0)),
        "videos": int(item["statistics"].get("videoCount", 0)),
        "playlist": item["contentDetails"]["relatedPlaylists"]["uploads"]
    }

# -----------------------------
# 영상 ID 가져오기
# -----------------------------
def get_video_ids(playlist_id):

    ids = []

    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=50
    )

    while request:

        response = request.execute()

        for item in response["items"]:
            ids.append(item["contentDetails"]["videoId"])

        request = youtube.playlistItems().list_next(
            request,
            response
        )

    return ids

# -----------------------------
# 영상 정보
# -----------------------------
def get_video_info(video_ids):

    videos = []

    for i in range(0, len(video_ids), 50):

        ids = ",".join(video_ids[i:i+50])

        response = youtube.videos().list(
            part="contentDetails,statistics,snippet",
            id=ids
        ).execute()

        for item in response["items"]:

            duration = duration_to_seconds(
                item["contentDetails"]["duration"]
            )

            views = int(
                item["statistics"].get("viewCount", 0)
            )

            videos.append({
                "제목": item["snippet"]["title"],
                "조회수": views,
                "길이(초)": duration
            })

    return pd.DataFrame(videos)

# -----------------------------
# 분석
# -----------------------------
if st.button("분석 시작"):

    if not API_KEY:
        st.warning("API Key를 입력하세요.")
        st.stop()

    if not channel_name:
        st.warning("채널명을 입력하세요.")
        st.stop()

    try:

        with st.spinner("분석 중..."):

            channel_id = search_channel(channel_name)

            if channel_id is None:
                st.error("채널을 찾을 수 없습니다.")
                st.stop()

            info = get_channel_info(channel_id)

            ids = get_video_ids(info["playlist"])

            df = get_video_info(ids)

    except HttpError as e:

        st.error(f"API 오류\n\n{e}")
        st.stop()

    if df.empty:
        st.error("영상 정보를 가져오지 못했습니다.")
        st.stop()

    avg_duration = int(df["길이(초)"].mean())
    avg_views = int(df["조회수"].mean())

    h = avg_duration // 3600
    m = (avg_duration % 3600) // 60
    s = avg_duration % 60

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "구독자",
        f"{info['subs']:,}"
    )

    col2.metric(
        "영상 수",
        f"{info['videos']:,}"
    )

    col3.metric(
        "평균 조회수",
        f"{avg_views:,}"
    )

    if h > 0:
        st.success(
            f"🎥 평균 영상 길이 : {h}시간 {m}분 {s}초"
        )
    else:
        st.success(
            f"🎥 평균 영상 길이 : {m}분 {s}초"
        )

    st.subheader("최근 영상 목록")

    st.dataframe(df)
