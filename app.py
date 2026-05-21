import re
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st
from matplotlib import pyplot as plt
from wordcloud import WordCloud

from youtube_comment_downloader import YoutubeCommentDownloader

# -----------------------------
# 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="YouTube 댓글 분석기",
    layout="wide"
)

st.title("🎬 YouTube 댓글 분석 웹앱")
st.markdown("유튜브 영상 댓글을 수집하고 사용자 반응을 분석합니다.")

# -----------------------------
# 유튜브 URL 입력
# -----------------------------
youtube_url = st.text_input(
    "유튜브 영상 링크 입력",
    placeholder="https://www.youtube.com/watch?v=xxxx"
)

comment_limit = st.slider(
    "수집할 댓글 수",
    min_value=20,
    max_value=10000,
    value=200,
    step=20
)

# -----------------------------
# 영상 ID 추출 함수
# -----------------------------
def extract_video_id(url):
    patterns = [
        r"v=([a-zA-Z0-9_-]+)",
        r"youtu\.be/([a-zA-Z0-9_-]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


# -----------------------------
# 댓글 수집 함수
# -----------------------------
@st.cache_data(show_spinner=False)
def fetch_comments(video_id, limit):

    downloader = YoutubeCommentDownloader()
    comments = downloader.get_comments_from_url(
        f"https://www.youtube.com/watch?v={video_id}",
        sort_by=0
    )

    data = []

    for idx, comment in enumerate(comments):

        if idx >= limit:
            break

        data.append({
            "comment": comment.get("text", ""),
            "likes": comment.get("votes", 0),
            "time": comment.get("time", ""),
            "author": comment.get("author", "")
        })

    return pd.DataFrame(data)


# -----------------------------
# 댓글 시간 전처리
# -----------------------------
def convert_time_to_hours(time_text):

    """
    예:
    '1 hour ago'
    '2 days ago'
    """

    if not isinstance(time_text, str):
        return None

    time_text = time_text.lower()

    if "minute" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num / 60

    elif "hour" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num

    elif "day" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num * 24

    elif "week" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num * 24 * 7

    elif "month" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num * 24 * 30

    elif "year" in time_text:
        num = int(re.findall(r"\d+", time_text)[0])
        return num * 24 * 365

    return None


# -----------------------------
# 분석 시작
# -----------------------------
if st.button("댓글 수집 및 분석 시작"):

    if not youtube_url:
        st.warning("유튜브 링크를 입력해주세요.")
        st.stop()

    video_id = extract_video_id(youtube_url)

    if not video_id:
        st.error("올바른 유튜브 링크가 아닙니다.")
        st.stop()

    with st.spinner("댓글 수집 중..."):

        df = fetch_comments(video_id, comment_limit)

    if df.empty:
        st.error("댓글을 가져오지 못했습니다.")
        st.stop()

    st.success(f"{len(df)}개의 댓글 수집 완료!")

    # -----------------------------
    # 기본 통계
    # -----------------------------
    st.subheader("📊 기본 통계")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("댓글 수", len(df))

    with col2:
        st.metric("총 좋아요 수", int(df["likes"].sum()))

    with col3:
        st.metric("평균 좋아요", round(df["likes"].mean(), 2))

    # -----------------------------
    # 시간대 분석
    # -----------------------------
    st.subheader("⏰ 댓글 시간 추이 분석")

    df["hours_ago"] = df["time"].apply(convert_time_to_hours)

    time_df = (
        df.dropna(subset=["hours_ago"])
        .groupby("hours_ago")
        .size()
        .reset_index(name="count")
        .sort_values("hours_ago")
    )

    fig_time = px.line(
        time_df,
        x="hours_ago",
        y="count",
        markers=True,
        title="시간 흐름에 따른 댓글 수"
    )

    fig_time.update_layout(
        xaxis_title="현재 기준 이전 시간(hours)",
        yaxis_title="댓글 수"
    )

    st.plotly_chart(fig_time, use_container_width=True)

    # -----------------------------
    # 좋아요 분석
    # -----------------------------
    st.subheader("👍 좋아요 분석")

    fig_like = px.histogram(
        df,
        x="likes",
        nbins=30,
        title="댓글 좋아요 분포"
    )

    st.plotly_chart(fig_like, use_container_width=True)

    top_like_df = df.sort_values("likes", ascending=False).head(10)

    st.markdown("### 🔥 좋아요 TOP 댓글")

    st.dataframe(
        top_like_df[["author", "likes", "comment"]],
        use_container_width=True
    )

    # -----------------------------
    # 워드클라우드
    # -----------------------------
    st.subheader("☁️ 워드클라우드")

    text = " ".join(df["comment"].astype(str).tolist())

    # 한글 폰트 경로 수정 필요 가능
    wordcloud = WordCloud(
        width=1200,
        height=600,
        background_color="white",
        collocations=False
    ).generate(text)

    fig_wc, ax = plt.subplots(figsize=(15, 7))

    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")

    st.pyplot(fig_wc)

    # -----------------------------
    # 자주 등장하는 단어
    # -----------------------------
    st.subheader("📌 자주 등장한 단어")

    words = re.findall(r'\b\w+\b', text.lower())

    stopwords = {
        "the", "is", "a", "an", "and",
        "to", "of", "it", "this", "that",
        "in", "on", "for", "with"
    }

    filtered_words = [
        word for word in words
        if len(word) > 1 and word not in stopwords
    ]

    counter = Counter(filtered_words)

    top_words = pd.DataFrame(
        counter.most_common(20),
        columns=["word", "count"]
    )

    fig_word = px.bar(
        top_words,
        x="word",
        y="count",
        title="자주 등장한 단어 TOP 20"
    )

    st.plotly_chart(fig_word, use_container_width=True)

    # -----------------------------
    # 댓글 원본 데이터
    # -----------------------------
    st.subheader("📝 댓글 데이터")

    st.dataframe(df, use_container_width=True)
