import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from collections import Counter
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

video_url = st.text_input(
    "유튜브 영상 링크 (선택사항)"
)

raw_comments = st.text_area(
    "댓글 붙여넣기",
    height=200,
    placeholder=(
        "유튜브 댓글을 복사해서 붙여넣으세요. 줄바꿈으로 구분합니다.\n\n"
        "예시:\n"
        "이 영상 진짜 유익해요!\n"
        "설명이 너무 어렵네요\n"
        "구독했습니다 최고예요"
    )
)

max_comments = st.slider(
    "분석할 댓글 수",
    20,
    1000,
    200,
    20
)

# =====================
# 댓글 파싱
# =====================

def parse_comments(text, limit):
    lines = [l.strip() for l in text.strip().splitlines()]
    lines = [l for l in lines if len(l) >= 2]
    lines = lines[:limit]
    return pd.DataFrame({"comment": lines})

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

    font_path = FONT_PATH if Path(FONT_PATH).exists() else None

    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=600,
        background_color="white"
    )

    return wc.generate_from_frequencies(counter)

# =====================
# 분석 시작
# =====================

if st.button("댓글 분석 시작"):

    if not raw_comments.strip():
        st.warning("댓글을 붙여넣어 주세요.")
        st.stop()

    df = parse_comments(raw_comments, max_comments)

    if df.empty:
        st.error("유효한 댓글이 없습니다.")
        st.stop()

    st.success(f"{len(df)}개 댓글 로드 완료")

    # =====================
    # 데이터
    # =====================

    st.subheader("📄 댓글 데이터")

    st.dataframe(df.head(20))

    # =====================
    # 댓글 길이 분포
    # =====================

    df["length"] = df["comment"].str.len()

    hourly = (
        df.groupby("length")
        .size()
        .reset_index(name="count")
    )

    st.subheader("📏 댓글 길이 분포")

    fig1, ax1 = plt.subplots(
        figsize=(10, 4)
    )

    sns.histplot(
        df["length"],
        bins=20,
        kde=True,
        ax=ax1
    )

    ax1.set_title("댓글 길이 분포")
    ax1.set_xlabel("글자 수")
    ax1.set_ylabel("댓글 수")

    st.pyplot(fig1)

    # =====================
    # 빈출 단어 TOP 댓글
    # =====================

    st.subheader("🔥 긴 댓글 TOP 10")

    top_comments = (
        df.sort_values(
            by="length",
            ascending=False
        )
        .head(10)
    )

    st.dataframe(
        top_comments[
            ["comment", "length"]
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

        fig2, ax2 = plt.subplots(
            figsize=(15, 7)
        )

        ax2.imshow(wc)

        ax2.axis("off")

        st.pyplot(fig2)

    else:

        st.warning(
            "워드클라우드 생성 실패"
        )

    # =====================
    # 빈출 단어 TOP 20
    # =====================

    st.subheader("🔤 빈출 단어 TOP 20")

    clean = re.sub(r"[^가-힣a-zA-Z\s]", " ", text)
    word_counts = Counter(
        w for w in clean.split() if len(w) >= 2
    )

    if word_counts:

        top_words = pd.DataFrame(
            word_counts.most_common(20),
            columns=["단어", "빈도"]
        )

        fig3, ax3 = plt.subplots(figsize=(10, 5))

        sns.barplot(
            data=top_words,
            x="빈도",
            y="단어",
            ax=ax3,
            palette="Blues_r"
        )

        ax3.set_title("빈출 단어 TOP 20")

        st.pyplot(fig3)
