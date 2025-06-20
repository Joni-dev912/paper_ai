import streamlit as st
import io
import json
import zipfile
import os
import google.generativeai as genai

# ——————————————————————————————
# 1) API 설정
# ——————————————————————————————
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCFySjtGYoEYMuetoHZnfy-rZ83Tk5PZxo")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ——————————————————————————————
# 2) 유틸리티: dict 재귀 플래튼 함수
# ——————————————————————————————
def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items

# ——————————————————————————————
# 3) Streamlit UI
# ——————————————————————————————
st.set_page_config(page_title="📁 논문 AI 챗봇", layout="wide")
st.title("📁 ZIP 기반 논문 분석 AI 챗봇")

uploaded_zip = st.file_uploader("📥 논문 JSON 파일들이 담긴 ZIP 업로드", type=["zip"])
question     = st.text_input("💬 AI에게 물어볼 질문을 입력하세요:")
ask          = st.button("질문하기")

# ——————————————————————————————
# 4) 처리 로직
# ——————————————————————————————
if ask:
    if uploaded_zip is None:
        st.error("먼저 ZIP 파일을 업로드해 주세요.")
    elif not question.strip():
        st.error("질문을 입력해 주세요.")
    else:
        try:
            z = zipfile.ZipFile(io.BytesIO(uploaded_zip.read()))
            infos = [
                info for info in z.infolist()
                if (not info.is_dir()) and info.filename.lower().endswith(".json")
            ]
            st.write(f"🔍 ZIP 안에서 찾은 JSON 파일 수: {len(infos)}")

            if not infos:
                st.warning("ZIP 안에 .json 파일이 없습니다.")
            else:
                context_list = []

                for info in infos:
                    raw = z.read(info)
                    try:
                        text = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        text = raw.decode("utf-8", errors="ignore")

                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        st.warning(f"⚠️ '{info.filename}' 파싱 실패, 건너뜁니다.")
                        continue

                    # 1) 기본 섹션 경로 시도
                    sec      = data.get("packages", {}).get("gpt", {}).get("sections", {})
                    title    = sec.get("title", "").strip()
                    abstract = sec.get("abstract", "").strip()
                    method   = sec.get("methodology", "").strip()
                    results  = sec.get("results", "").strip()

                    # 2) 모두 비어있다면, 플래튼 후 키 이름으로 추출
                    if not any([title, abstract, method, results]):
                        flat = flatten_dict(data)
                        # 키에 단어 포함 여부로 필터링
                        title    = next((v for k, v in flat.items()
                                         if "title" in k.lower() and isinstance(v, str) and v.strip()), "")
                        abstract = next((v for k, v in flat.items()
                                         if any(x in k.lower() for x in ("abstract", "summary")) and isinstance(v, str) and v.strip()), "")
                        method   = next((v for k, v in flat.items()
                                         if "method" in k.lower() and isinstance(v, str) and v.strip()), "")
                        results  = next((v for k, v in flat.items()
                                         if "result" in k.lower() and isinstance(v, str) and v.strip()), "")

                    # 3) 여전히 비어있다면 경고
                    if not any([title, abstract, method, results]):
                        st.warning(f"⚠️ '{info.filename}' 에서 유의미한 섹션을 찾지 못했습니다.")
                        continue

                    # 4) 컨텍스트 조립
                    context_list.append(
                        f"📄 제목: {title}\n\n"
                        f"[초록]\n{abstract}\n\n"
                        f"[방법론]\n{method}\n\n"
                        f"[결과]\n{results}"
                    )

                if not context_list:
                    st.error("읽을 논문 내용이 하나도 남지 않았습니다.")
                else:
                    full_context = "\n\n---\n\n".join(context_list)
                    prompt = (
                        "다음은 여러 논문에서 추출한 핵심 내용입니다. 이 내용을 바탕으로 아래 질문에 답해주세요.\n\n"
                        f"{full_context}\n\n"
                        "[질문]\n"
                        f"{question}"
                    )
                    resp = model.generate_content(prompt)
                    st.subheader("🧠 AI의 응답")
                    st.write(resp.text or "(응답이 없습니다)")

        except zipfile.BadZipFile:
            st.error("올바른 ZIP 파일이 아닙니다. 다시 확인해 주세요.")
        except Exception as e:
            st.error(f"오류 발생: {e}")
