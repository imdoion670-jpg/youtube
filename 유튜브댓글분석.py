import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from wordcloud import WordCloud
from collections import Counter
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urlparse, parse_qs
import re

# -----------------------------
# 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="YouTube 댓글 분석기",
    layout="wide"
)

# -----------------------------
# 한글 폰트 자동 탐색
# -----------------------------
def find_korean_font():
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "/Library/Fonts/AppleGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for f in fm.findSystemFonts():
        name = os.path.basename(f).lower()
        if any(k in name for k in ["nanum", "malgun", "gothic", "noto"]):
            return f
    return None

KOREAN_FONT = find_korean_font()

# -----------------------------
# 한글 깨짐 방지
# -----------------------------
if KOREAN_FONT:
    font_name = fm.FontProperties(fname=KOREAN_FONT).get_name()
    plt.rcParams["font.family"] = font_name
else:
    plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"] = False

st.title("📺 YouTube 댓글 분석 대시보드")

# -----------------------------
# API KEY
# -----------------------------
API_KEY = st.text_input(
    "YouTube Data API Key",
    type="password"
)

# -----------------------------
# 링크 입력
# -----------------------------
video_url = st.text_input(
    "YouTube 영상 링크 입력"
)

# -----------------------------
# 댓글 수
# -----------------------------
max_comments = st.slider(
    "수집할 댓글 수",
    min_value=20,
    max_value=1000,
    value=200,
    step=20
)

# -----------------------------
# 영상 ID 추출
# -----------------------------
def extract_video_id(url):

    try:

        if "youtu.be/" in url:
            return url.split("/")[-1].split("?")[0]

        if "youtube.com" in url:
            return parse_qs(
                urlparse(url).query
            ).get("v", [None])[0]

    except:
        pass

    return None


# -----------------------------
# 댓글 수집
# -----------------------------
def get_comments(video_id, api_key, max_results):

    try:

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

                comment = item["snippet"][
                    "topLevelComment"
                ]["snippet"]

                comments.append({
                    "comment": comment["textDisplay"],
                    "likes": comment["likeCount"],
                    "publishedAt": comment["publishedAt"]
                })

                if len(comments) >= max_results:
                    break

            request = youtube.commentThreads().list_next(
                request,
                response
            )

        return pd.DataFrame(comments)

    except HttpError as e:

        st.error(
            f"YouTube API 오류\n\n{e}"
        )

        return pd.DataFrame()

    except Exception as e:

        st.error(
            f"오류 발생\n\n{e}"
        )

        return pd.DataFrame()


# -----------------------------
# 워드클라우드
# -----------------------------
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

    if KOREAN_FONT is None:
        st.warning("한글 폰트를 찾을 수 없습니다. `sudo apt-get install fonts-nanum` 으로 설치해주세요.")

    return WordCloud(
        font_path=KOREAN_FONT,
        width=1200,
        height=600,
        background_color="white"
    ).generate_from_frequencies(counter)


# -----------------------------
# 분석 시작
# -----------------------------
if st.button("댓글 분석 시작"):

    if not API_KEY:
        st.warning("API Key 입력")
        st.stop()

    if not video_url:
        st.warning("영상 링크 입력")
        st.stop()

    video_id = extract_video_id(
        video_url
    )

    if not video_id:
        st.error(
            "올바른 유튜브 링크가 아닙니다."
        )
        st.stop()

    with st.spinner("댓글 수집 중..."):

        df = get_comments(
            video_id,
            API_KEY,
            max_comments
        )

    if df.empty:
        st.stop()

    st.success(
        f"{len(df)}개 댓글 수집 완료"
    )

    # -----------------------------
    # 데이터
    # -----------------------------
    st.subheader("📄 댓글 데이터")

    st.dataframe(df.head(20))

    # -----------------------------
    # 시간대
    # -----------------------------
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

    st.subheader(
        "⏰ 시간대별 댓글 추이"
    )

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

    st.pyplot(fig1)

    # -----------------------------
    # 좋아요
    # -----------------------------
    st.subheader(
        "👍 좋아요 분포"
    )

    fig2, ax2 = plt.subplots(
        figsize=(10, 4)
    )

    sns.histplot(
        df["likes"],
        bins=20,
        kde=True,
        ax=ax2
    )

    st.pyplot(fig2)

    # -----------------------------
    # TOP 댓글
    # -----------------------------
    st.subheader(
        "🔥 좋아요 TOP 댓글"
    )

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

    # -----------------------------
    # 워드클라우드
    # -----------------------------
    st.subheader(
        "☁️ 워드클라우드"
    )

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
