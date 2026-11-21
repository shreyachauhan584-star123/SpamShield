
"""Learn & Protect: scam lessons (EN/HI) and a gentle quiz."""
from __future__ import annotations

import streamlit as st

from src.content.awareness import CATEGORIES
from src.content.quiz import QUIZ
from src.ui.state import T, current_lang
from src.ui.styles import quote_html
from src.utils.helpers import pick


def _answer(said_scam: bool) -> None:
    st.session_state["quiz_answer"] = said_scam

    if said_scam == QUIZ[st.session_state["quiz_i"]]["scam"]:
        st.session_state["quiz_score"] += 1


def _next() -> None:
    st.session_state["quiz_i"] += 1
    st.session_state["quiz_answer"] = None


def _restart() -> None:
    st.session_state.update(quiz_i=0, quiz_score=0, quiz_answer=None)


def render_page() -> None:
    lang = current_lang()

    st.title("📚 " + T("nav_awareness"))
    st.write(T("aw_intro"))

    # Scam awareness lessons
    for c in CATEGORIES:
        with st.expander(f"{c['icon']} {pick(c['title'], lang)}"):
            st.markdown(f"**{T('aw_example')}**")
            st.markdown(
                quote_html(pick(c["example"], lang)),
                unsafe_allow_html=True
            )

            st.markdown(f"**{T('aw_why')}**")
            st.write(pick(c["why"], lang))

            st.markdown(f"**{T('aw_how')}**")
            st.write(pick(c["how"], lang))

            st.success(
                f"**{T('aw_do')}:** {pick(c['do'], lang)}"
            )
            st.error(
                f"**{T('aw_never')}:** {pick(c['never'], lang)}"
            )

    st.divider()

    # Quiz section
    st.header("🧠 " + T("quiz_title"))
    st.write(T("quiz_intro"))

    st.session_state.setdefault("quiz_i", 0)
    st.session_state.setdefault("quiz_score", 0)
    st.session_state.setdefault("quiz_answer", None)

    i = st.session_state["quiz_i"]

    if i >= len(QUIZ):
        st.subheader(T("quiz_done_title"))

        st.success(
            T(
                "quiz_score",
                score=st.session_state["quiz_score"],
                total=len(QUIZ)
            )
        )

        st.button(
            T("quiz_restart"),
            on_click=_restart,
            use_container_width=True
        )
        return

    item = QUIZ[i]
    ans = st.session_state["quiz_answer"]

    st.caption(T("quiz_question_n", n=i + 1, total=len(QUIZ)))

    st.markdown(
        quote_html(item["message"]),
        unsafe_allow_html=True
    )

    if ans is None:
        a, b = st.columns(2)

        a.button(
            "✅ " + T("quiz_legit"),
            key=f"q{i}a",
            on_click=_answer,
            args=(False,),
            use_container_width=True
        )

        b.button(
            "⚠️ " + T("quiz_susp"),
            key=f"q{i}b",
            on_click=_answer,
            args=(True,),
            use_container_width=True
        )

    else:
        correct = ans == item["scam"]

        if correct:
            st.success("🎉 " + T("quiz_good"))
        else:
            st.info("💡 " + T("quiz_notquite"))

        st.write(pick(item["explanation"], lang))

        st.button(
            T("quiz_next"),
            on_click=_next,
            type="primary",
            use_container_width=True
        )
