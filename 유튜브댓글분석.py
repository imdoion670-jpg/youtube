import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from collections import Counter
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import re

# =====================
# 한글 폰트 설정
# =====================

FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

if Path(FONT_PATH).exists():
    plt.rcParams["font.family"] = "NanumGothic"

plt.rcParams["axes.unicode_minus"] = False

# =====================
# 페이지 설정
# =====================

st.set_page_config(
    page_title="YouTube 댓글 분석기",
    page_icon="📺",
    layout="wide"
)

st.title("📺 YouTube 댓글 분석기")

# =====================
# 입력
# =====================

api_key = st.text_input(
    "YouTube API Key",
    type="password"
)

video_url = st.text_input(
    "유튜브 영상 링크"
)

max_comments = st.slider(
    "수집할 댓글 수",
    20,
    1000,
    200,
    20
)

# =====================
# 비디오 ID 추출
# =====================

def extract_video_id(url):

    try:

        if "youtu.be" in url:
            return url.split("/")[-1].split("?")[0]

        if "youtube.com" in url:

            return parse_qs(
                urlparse(url).query
            ).get("v", [None])[0]

    except:
        return None

    return None

# =====================
# 댓글 수집
# =====================

def get_comments(video_id, api_key, limit):

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

    while request and len(comments) < limit:

        response = request.execute()

        for item in response["items"]:

            snippet = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "comment": snippet["textDisplay"],
                "likes": snippet["likeCount"],
                "publishedAt": snippet["publishedAt"]
            })

            if len(comments) >= limit:
                break

        request = youtube.commentThreads().list_next(
            request,
            response
        )

    return pd.DataFrame(comments)

# =====================
# 워드클라우드
# =====================

def create_wordcloud(text):

    text = re.sub(
        r"[^가-힣a-zA-Z\s]",
        " ",
        text
    )

    words = text.split()

    words = [
        word
        for word in words
        if len(word) >= 2
    ]

    counter = Counter(words)

    if len(counter) == 0:
        return None

    wc = WordCloud(
        font_path=FONT_PATH if Path(FONT_PATH).exists() else None,
        width=1200,
        height=600,
        background_color="white"
    )

    return wc.generate_from_frequencies(counter)

# =====================
# 분석 시작
# =====================

if st.button("댓글 분석 시작"):

    if not api_key:
        st.warning("API Key를 입력하세요.")
        st.stop()

    if not video_url:
        st.warning("유튜브 링크를 입력하세요.")
        st.stop()

    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("올바른 유튜브 링크가 아닙니다.")
        st.stop()

    try:

        with st.spinner("댓글 수집 중..."):

            df = get_comments(
                video_id,
                api_key,
                max_comments
            )

    except HttpError as e:

        st.error(f"YouTube API 오류\n\n{e}")
        st.stop()

    if df.empty:

        st.error("댓글이 없습니다.")
        st.stop()

    st.success(f"{len(df)}개 댓글 수집 완료")

    # =====================
    # 데이터
    # =====================

    st.subheader("📄 댓글 데이터")

    st.dataframe(df.head(20))

    # =====================
    # 시간대 분석
    # =====================

    df["publishedAt"] = pd.to_datetime(
        df["publishedAt"]
    )

    df["hour"] = (
        df["publishedAt"]
        .dt.hour
    )

    hourly = (
        df.groupby("hour")
        .size()
        .reset_index(name="count")
    )

    st.subheader("⏰ 시간대별 댓글 추이")

    fig1, ax1 = plt.subplots(
        figsize=(10, 4)
    )

    sns.lineplot(
        data=hourly,
        x="hour",
        y="count",
        marker="o",
        ax=ax1
    )

    ax1.set_title("시간대별 댓글 추이")
    ax1.set_xlabel("시간")
    ax1.set_ylabel("댓글 수")

    st.pyplot(fig1)

    # =====================
    # 좋아요 분포
    # =====================

    st.subheader("👍 좋아요 분포")

    fig2, ax2 = plt.subplots(
        figsize=(10, 4)
    )

    sns.histplot(
        df["likes"],
        bins=20,
        kde=True,
        ax=ax2
    )

    ax2.set_title("좋아요 분포")
    ax2.set_xlabel("좋아요 수")
    ax2.set_ylabel("댓글 개수")

    st.pyplot(fig2)

    # =====================
    # TOP 댓글
    # =====================

    st.subheader("🔥 좋아요 TOP 댓글")

    top_comments = (
        df.sort_values(
            by="likes",
            ascending=False
        )
        .head(10)
    )

    st.dataframe(
        top_comments[
            ["comment", "likes"]
        ]
    )

    # =====================
    # 워드클라우드
    # =====================

    st.subheader("☁️ 워드클라우드")

    text = " ".join(
        df["comment"].astype(str)
    )

    wc = create_wordcloud(text)

    if wc:

        fig3, ax3 = plt.subplots(
            figsize=(15, 7)
        )

        ax3.imshow(wc)

        ax3.axis("off")

        st.pyplot(fig3)

    else:

        st.warning(
            "워드클라우드 생성 실패"
        )
