import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from isodate import parse_duration

API_KEY = st.text_input("YouTube API Key", type="password")

if API_KEY:
    youtube = build("youtube", "v3", developerKey=API_KEY)

st.title("📊 채널 평균 영상 분석")

channel_name = st.text_input("채널명 입력")

# 채널 검색
def search_channel(name):
    res = youtube.search().list(
        q=name,
        part="snippet",
        type="channel",
        maxResults=1
    ).execute()

    if not res["items"]:
        return None

    return res["items"][0]["snippet"]["channelId"]

# 업로드 재생목록 ID
def get_upload_playlist(channel_id):
    res = youtube.channels().list(
        part="contentDetails,snippet,statistics",
        id=channel_id
    ).execute()

    item = res["items"][0]

    return (
        item["contentDetails"]["relatedPlaylists"]["uploads"],
        item["snippet"]["title"],
        int(item["statistics"]["subscriberCount"])
    )

# 영상 목록
def get_video_ids(playlist_id):

    ids=[]

    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=50
    )

    while request:

        response=request.execute()

        for item in response["items"]:
            ids.append(item["contentDetails"]["videoId"])

        request=youtube.playlistItems().list_next(
            request,
            response
        )

    return ids

# 영상 정보
def get_video_info(video_ids):

    videos=[]

    for i in range(0,len(video_ids),50):

        ids=",".join(video_ids[i:i+50])

        res=youtube.videos().list(
            part="contentDetails,statistics",
            id=ids
        ).execute()

        for item in res["items"]:

            duration=parse_duration(
                item["contentDetails"]["duration"]
            ).total_seconds()

            views=int(
                item["statistics"].get("viewCount",0)
            )

            videos.append({
                "duration":duration,
                "views":views
            })

    return pd.DataFrame(videos)

if st.button("분석"):

    channel_id=search_channel(channel_name)

    if channel_id is None:
        st.error("채널을 찾을 수 없습니다.")
        st.stop()

    playlist,title,subs=get_upload_playlist(channel_id)

    ids=get_video_ids(playlist)

    df=get_video_info(ids)

    avg_seconds=df["duration"].mean()

    avg_minutes=int(avg_seconds//60)
    avg_sec=int(avg_seconds%60)

    avg_views=int(df["views"].mean())

    col1,col2,col3=st.columns(3)

    col1.metric("구독자",f"{subs:,}")

    col2.metric("평균 조회수",f"{avg_views:,}")

    col3.metric("영상 개수",len(df))

    st.success(f"평균 영상 길이 : {avg_minutes}분 {avg_sec}초")

    st.dataframe(df.head())
