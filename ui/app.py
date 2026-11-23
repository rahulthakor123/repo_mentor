import html
import re

import streamlit as st
import streamlit.components.v1 as components
from repo_mentor.service import architecture, index_repo, learning_path, qa, quiz, setup_guide
from repo_mentor.service import architecture, index_repo, learning_path, qa, setup_guide

st.set_page_config(page_title="Repo Mentor", page_icon="🧭")
st.title("🧭 Repo Mentor")
st.caption("Paste a GitHub repo and learn it step by step.")

with st.sidebar:
    url = st.text_input("GitHub repo URL", placeholder="https://github.com/user/repo")
    level = st.radio("Explain level", ["beginner", "advanced"])
    if st.button("Index repo", type="primary") and url:
        bar = st.progress(0, text="Cloning and reading files...")
        try:
            repo_id = index_repo(
                url, lambda done, total: bar.progress(done / total, text=f"Embedding {done}/{total}")
            )
        except Exception as e:
            bar.empty()
            st.error(f"Could not index this repo: {e}\n\nCheck that the URL is a public GitHub repo and that Ollama is running.")
            st.stop()
        clean_url = url.strip().rstrip("/")
        if clean_url.endswith(".git"):
            clean_url = clean_url[:-4]
        st.session_state.update(repo_id=repo_id, url=clean_url, messages=[])
        bar.empty()
        st.success(f"Ready: {repo_id}")
    st.divider()
    mode = st.radio("What do you want?",
                    ["Ask a question", "Learning path", "Setup guide", "Architecture map", "Quiz"])

if "repo_id" not in st.session_state:
    st.info("👈 Index a repo first.")
    st.stop()

MERMAID = re.compile(r"```mermaid\n(.*?)\n```", re.S)


def render_mermaid(code: str):
    page = f"""
<div class="mermaid">{html.escape(code)}</div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true }});
</script>"""
    components.html(page, height=520, scrolling=True)
    with st.expander("Mermaid source"):
        st.code(code, language="text")


def render_message(text: str):
    pos = 0
    for m in MERMAID.finditer(text):
        if text[pos:m.start()].strip():
            st.markdown(text[pos:m.start()])
        render_mermaid(m.group(1))
        pos = m.end()
    if text[pos:].strip():
        st.markdown(text[pos:])


def show_sources(sources):
    with st.expander("📂 Sources"):
        seen = set()
        for s in sources:
            key = (s["file_path"], s["start_line"])
            if key in seen:
                continue
            seen.add(key)
            link = f"{st.session_state.url}/blob/HEAD/{s['file_path']}#L{s['start_line']}-L{s['end_line']}"
            label = f"{s['file_path']} (lines {s['start_line']}-{s['end_line']})"
            st.markdown(f"- [{label}]({link})")


def answer_and_save(stream, sources):
    with st.chat_message("assistant"):
        answer = st.write_stream(stream)
        if sources:
            show_sources(sources)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


def ask_feature(text, run_stream, arg):
    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    try:
        stream, sources = run_stream(st.session_state.repo_id, arg, level)
        answer_and_save(stream, sources)
    except Exception as e:
        st.exception(e)


def ask_diagram(text, run_stream):
    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    try:
        with st.spinner("Reading the code..."):
            stream, _ = run_stream(st.session_state.repo_id, "", level)
            answer = "".join(stream)
        with st.chat_message("assistant"):
            render_message(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer, "sources": []})
    except Exception as e:
        st.exception(e)


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        render_message(m["content"])
        if m.get("sources"):
            show_sources(m["sources"])

if mode == "Learning path":
    st.info("Get a step-by-step reading order for this repo.")
    if st.button("🗺️ Generate learning path", type="primary"):
        ask_feature("Show me a learning path for this repo.", learning_path.run_stream, "")
elif mode == "Setup guide":
    st.info("Get exact steps to install and run this repo on Windows.")
    if st.button("🛠️ Generate setup guide", type="primary"):
        ask_feature("How do I set up and run this project?", setup_guide.run_stream, st.session_state.url)
elif mode == "Architecture map":
    st.info("See how the files connect, the API endpoints, and one line about each file.")
    if st.button("🏗️ Generate architecture map", type="primary"):
        ask_diagram("Show me the architecture of this repo.", architecture.run_stream)
elif mode == "Quiz":
    st.info("Five questions made from the real code. The answers are checked against the repo, not guessed by the model.")
    qs = st.session_state.get("quiz")
    new = st.button("🎯 New quiz", type="primary")
    if new or qs is None or qs["repo"] != st.session_state.repo_id:
        rnd = (qs["round"] + 1) if qs else 1
        qs = {"repo": st.session_state.repo_id, "round": rnd, "checked": False,
              "questions": quiz.generate(st.session_state.repo_id, f"{st.session_state.repo_id}-{rnd}")}
        st.session_state["quiz"] = qs
    if not qs["questions"]:
        st.warning("This repo doesn't have enough Python files (at least 4) to build a quiz.")
    else:
        picked = [st.radio(f"{i}. {q['q']}", q["options"], index=None, key=f"quiz-{qs['round']}-{i}")
                  for i, q in enumerate(qs["questions"], 1)]
        if st.button("✅ Check answers"):
            qs["checked"] = True
        if qs["checked"]:
            score = 0
            for i, (q, a) in enumerate(zip(qs["questions"], picked), 1):
                if a == q["answer"]:
                    score += 1
                    st.success(f"{i}. Correct. {q['why']}")
                else:
                    st.error(f"{i}. {'No answer' if a is None else 'Not quite'}. {q['why']}")
            st.subheader(f"Score: {score} / {len(qs['questions'])}")           
else:
    question = st.chat_input("Ask about the repo... (e.g. How do I run this project?)")
    if question:
        ask_feature(question, qa.run_stream, question)