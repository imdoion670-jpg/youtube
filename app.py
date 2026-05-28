import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from collections import Counter
from konlpy.tag import Okt
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import re

# -----------------------------
# Streamlit 기본 설정
# -----------------------------
st.set_page_config(
    page_title="YouTube 댓글 분석기",
    layout="wide"
)

st.title("📺 YouTube 댓글 분석 및 시각화")

# -----------------------------
# YouTube API Key 입력
# -----------------------------
API_KEY = st.text_input(
    "YouTube Data API Key 입력",
    type="password"
)

# -----------------------------
# 유튜브 URL 입력
# -----------------------------
video_url = st.text_input(
    "YouTube 영상 링크 입력"
)

# -----------------------------
# 댓글 수 슬라이더
# -----------------------------
max_comments = st.slider(
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
    if "youtube.com" in url:
        query = urlparse(url)
        return parse_qs(query.query)["v"][0]

    elif "youtu.be" in url:
        return url.split("/")[-1]

    return None

# -----------------------------
# 댓글 수집 함수
# -----------------------------
def get_comments(video_id, api_key, max_results):

    youtube = build(
        "youtube",
        "v3",
        developerKey=api_key
    )

    comments = []

    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=100,
        textFormat="plainText"
    )

    while request and len(comments) < max_results:

        response = request.execute()

        for item in response["items"]:

            comment = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "comment": comment["textDisplay"],
                "likeCount": comment["likeCount"],
                "publishedAt": comment["publishedAt"]
            })

            if len(comments) >= max_results:
                break

        request = youtube.commentThreads().list_next(
            request,
            response
        )

    return pd.DataFrame(comments)

# -----------------------------
# 워드클라우드 생성 함수
# -----------------------------
def generate_wordcloud(text):

    okt = Okt()

    # 한글만 추출
    text = re.sub(r"[^가-힣\s]", "", text)

    nouns = okt.nouns(text)

    # 2글자 이상만 사용
    nouns = [word for word in nouns if len(word) > 1]

    counter = Counter(nouns)

    # Windows 기준 한글 폰트
    font_path = "malgun.ttf"

    wc = WordCloud(
        font_path=font_path,
        background_color="white",
        width=1000,
        height=500
    )

    wordcloud = wc.generate_from_frequencies(counter)

    return wordcloud

# -----------------------------
# 분석 실행 버튼
# -----------------------------
if st.button("댓글 분석 시작"):

    if not API_KEY:
        st.warning("API Key를 입력해주세요.")
        st.stop()

    if not video_url:
        st.warning("유튜브 링크를 입력해주세요.")
        st.stop()

    with st.spinner("댓글 수집 중..."):

        video_id = extract_video_id(video_url)

        df = get_comments(
            video_id,
            API_KEY,
            max_comments
        )

    st.success(f"{len(df)}개의 댓글 수집 완료!")

    # -----------------------------
    # 데이터 전처리
    # -----------------------------
    df["publishedAt"] = pd.to_datetime(df["publishedAt"])

    df["date"] = df["publishedAt"].dt.date
    df["hour"] = df["publishedAt"].dt.hour

    # -----------------------------
    # 데이터 미리보기
    # -----------------------------
    st.subheader("📄 댓글 데이터")

    st.dataframe(df.head())

    # -----------------------------
    # 시간대별 댓글 수
    # -----------------------------
    st.subheader("⏰ 시간대별 댓글 추이")

    hourly_comments = (
        df.groupby("hour")
        .size()
        .reset_index(name="count")
    )

    fig1, ax1 = plt.subplots(figsize=(10, 4))

    sns.lineplot(
        data=hourly_comments,
        x="hour",
        y="count",
        marker="o",
        ax=ax1
    )

    ax1.set_xlabel("시간")
    ax1.set_ylabel("댓글 수")
    ax1.set_title("시간대별 댓글 수")

    st.pyplot(fig1)

    # -----------------------------
    # 좋아요 분석
    # -----------------------------
    st.subheader("👍 좋아요 수 분석")

    fig2, ax2 = plt.subplots(figsize=(10, 4))

    sns.histplot(
        df["likeCount"],
        bins=30,
        kde=True,
        ax=ax2
    )

    ax2.set_title("댓글 좋아요 분포")
    ax2.set_xlabel("좋아요 수")

    st.pyplot(fig2)

    # 상위 댓글
    st.subheader("🔥 좋아요 TOP 댓글")

    top_comments = df.sort_values(
        by="likeCount",
        ascending=False
    ).head(10)

    st.dataframe(
        top_comments[[
            "comment",
            "likeCount"
        ]]
    )

    # -----------------------------
    # 워드클라우드
    # -----------------------------
    st.subheader("☁️ 자주 등장하는 단어")

    full_text = " ".join(df["comment"].astype(str))

    wordcloud = generate_wordcloud(full_text)

    fig3, ax3 = plt.subplots(figsize=(15, 7))

    ax3.imshow(wordcloud)
    ax3.axis("off")

    st.pyplot(fig3)

```
