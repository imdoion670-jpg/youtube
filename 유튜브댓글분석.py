import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from collections import Counter
from pathlib import Path
import anthropic
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

st.info(
    "유튜브 영상의 댓글을 복사해서 아래에 붙여넣으세요. "
    "줄바꿈으로 댓글을 구분합니다.",
    icon="ℹ️"
)

# =====================
# 입력
# =====================

video_url = st.text_input(
    "유튜브 영상 링크 (선택사항 — 참고용)"
)

raw_text = st.text_area(
    "댓글 붙여넣기",
    height=200,
    placeholder=(
        "댓글을 줄바꿈으로 구분해서 붙여넣으세요.\n\n"
        "예시:\n"
        "이 영상 진짜 유익해요!\n"
        "설명이 너무 어렵네요\n"
        "구독했습니다 최고예요"
    )
)

analysis_mode = st.selectbox(
    "AI 분석 방향",
    [
        "전반적인 반응 분석",
        "감성 분석 (긍정/부정/중립)",
        "주요 주제 및 키워드 추출",
        "시청자 요청/피드백 정리",
    ]
)

# =====================
# 댓글 파싱
# =====================

def parse_comments(text):
    lines = [l.strip() for l in text.strip().splitlines()]
    lines = [l for l in lines if len(l) >= 2]
    return pd.DataFrame({"comment": lines})

# =====================
# 워드클라우드
# =====================

def create_wordcloud(text):
    text = re.sub(r"[^가-힣a-zA-Z\s]", " ", text)
    words = [w for w in text.split() if len(w) >= 2]
    counter = Counter(words)

    if not counter:
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
# Claude AI 분석
# =====================

def analyze_with_claude(comments, mode, url=""):
    client = anthropic.Anthropic()

    video_info = f"유튜브 영상 URL: {url}\n" if url else ""
    comment_list = "\n".join(
        f"{i+1}. {c}" for i, c in enumerate(comments)
    )

    prompts = {
        "전반적인 반응 분석": (
            f"다음은 유튜브 영상의 댓글들입니다. "
            f"전반적인 시청자 반응을 한국어로 분석해주세요. "
            f"전체적인 분위기, 주요 반응 패턴, 눈에 띄는 의견들을 정리해주세요.\n\n"
            f"{video_info}댓글 수: {len(comments)}개\n\n"
            f"댓글 목록:\n{comment_list}"
        ),
        "감성 분석 (긍정/부정/중립)": (
            f"다음 유튜브 댓글들을 감성 분석해주세요. "
            f"긍정/부정/중립 비율을 추정하고, 각 카테고리의 대표 댓글 예시와 함께 "
            f"한국어로 설명해주세요.\n\n"
            f"{video_info}댓글 수: {len(comments)}개\n\n"
            f"댓글 목록:\n{comment_list}"
        ),
        "주요 주제 및 키워드 추출": (
            f"다음 유튜브 댓글들에서 주요 주제와 키워드를 추출해주세요. "
            f"많이 언급된 토픽, 핵심 키워드, 시청자들이 가장 관심 갖는 내용을 "
            f"한국어로 정리해주세요.\n\n"
            f"{video_info}댓글 수: {len(comments)}개\n\n"
            f"댓글 목록:\n{comment_list}"
        ),
        "시청자 요청/피드백 정리": (
            f"다음 유튜브 댓글들에서 시청자들의 요청사항, 건설적인 피드백, "
            f"개선 제안을 정리해주세요. 크리에이터가 참고할 수 있도록 "
            f"한국어로 구체적으로 요약해주세요.\n\n"
            f"{video_info}댓글 수: {len(comments)}개\n\n"
            f"댓글 목록:\n{comment_list}"
        ),
    }

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompts[mode]}
        ]
    )

    return message.content[0].text

# =====================
# 분석 시작
# =====================

if st.button("댓글 분석 시작"):

    if not raw_text.strip():
        st.warning("댓글을 입력해주세요.")
        st.stop()

    df = parse_comments(raw_text)

    if df.empty:
        st.error("유효한 댓글이 없습니다. 줄바꿈으로 구분된 댓글을 입력해주세요.")
        st.stop()

    st.success(f"{len(df)}개 댓글 로드 완료")

    # =====================
    # 데이터
    # =====================

    st.subheader("📄 댓글 데이터")
    st.dataframe(df.head(20), use_container_width=True)

    # =====================
    # 댓글 길이 분포
    # =====================

    df["length"] = df["comment"].str.len()

    st.subheader("📏 댓글 길이 분포")

    fig1, ax1 = plt.subplots(figsize=(10, 4))

    sns.histplot(
        df["length"],
        bins=20,
        kde=True,
        ax=ax1,
        color="#4f86c6"
    )

    ax1.set_title("댓글 길이 분포")
    ax1.set_xlabel("글자 수")
    ax1.set_ylabel("댓글 개수")

    st.pyplot(fig1)

    # =====================
    # 워드클라우드
    # =====================

    st.subheader("☁️ 워드클라우드")

    text = " ".join(df["comment"].astype(str))
    wc = create_wordcloud(text)

    if wc:
        fig2, ax2 = plt.subplots(figsize=(15, 7))
        ax2.imshow(wc)
        ax2.axis("off")
        st.pyplot(fig2)
    else:
        st.warning("워드클라우드를 생성할 수 없습니다.")

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

    # =====================
    # AI 분석
    # =====================

    st.subheader(f"🤖 AI 분석 — {analysis_mode}")

    with st.spinner("Claude가 분석 중입니다..."):
        try:
            result = analyze_with_claude(
                df["comment"].tolist(),
                analysis_mode,
                video_url
            )
            st.markdown(result)
        except Exception as e:
            st.error(f"AI 분석 중 오류가 발생했습니다: {e}")
