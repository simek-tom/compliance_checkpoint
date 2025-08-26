import streamlit as st
import pandas as pd
import numpy as np
import base64
import os
import re
from pathlib import Path
import scipy.stats as stats
import datetime

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="USL Audit", layout="wide")

# ─── Font helpers & CSS injection ──────────────────────────────────────────────
def font_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bi = font_to_b64(Path("visuals/fonts/Montserrat-BoldItalic.ttf"))
b  = font_to_b64(Path("visuals/fonts/Montserrat-Bold.ttf"))
st.markdown(f"""
<style>
  @font-face {{ font-family:'Montserrat'; font-style:italic; font-weight:700;
    src:url(data:font/ttf;base64,{bi}) format('truetype'); }}
  @font-face {{ font-family:'Montserrat'; font-style:normal; font-weight:700;
    src:url(data:font/ttf;base64,{b})  format('truetype'); }}
  html, body, [class*="css"] {{ font-family:'Montserrat',sans-serif!important; }}
  .stButton > button {{ font-family:'Montserrat',sans-serif!important; }}
</style>
""", unsafe_allow_html=True)

# ─── Data loading ──────────────────────────────────────────────────────────────
QUESTIONS_PATH = Path("questions_data") / "questions.csv"
if not QUESTIONS_PATH.exists():
    st.error(f"CSV not found: {QUESTIONS_PATH}")
    st.stop()

@st.cache_data
def load_questions(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, sep=";")
    # normalize European commas
    for col in ["weight_fulfilled","weight_awareness"]:
        df[col] = df[col].astype(str).str.replace(",",".").astype(float)
    return df

questions_df = load_questions(QUESTIONS_PATH)

LOG_PATH = Path("audit_data") / "audit_scores_log.csv"
@st.cache_data
def load_log(p: Path) -> pd.DataFrame:
    return pd.read_csv(p) if p.exists() else pd.DataFrame(
        columns=["compliance_score","awareness_score","time_stamp"]
    )

audit_log = load_log(LOG_PATH)

INDICATOR_PATH = Path("visuals")/"b77b1e85-9817-49f9-b1ae-9be3e04ea552.png"
@st.cache_data
def load_indicator_b64(p: Path) -> str:
    with open(p,"rb") as f:
        return base64.b64encode(f.read()).decode()

indicator_b64 = load_indicator_b64(INDICATOR_PATH) if INDICATOR_PATH.exists() else None

# ─── Session init ──────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = 1
if "global_questions" not in st.session_state:
    st.session_state.global_questions = pd.DataFrame()
if "global_answers" not in st.session_state:
    st.session_state.global_answers = pd.DataFrame()

# ─── Helpers ───────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    return re.sub(r"\W+","_", text).lower()

def save_global_progress():
    df = st.session_state.global_questions.copy()
    # Add safety check for company name
    if hasattr(st.session_state, 'company') and st.session_state.company:
        df["company_name"] = st.session_state.company
    else:
        df["company_name"] = "Unknown Company"  # Fallback value
    df["answer_fulfilled"] = st.session_state.global_answers["fulfilled"]
    df["answer_awareness"]  = st.session_state.global_answers["awareness"]
    os.makedirs("cache",exist_ok=True)
    df.to_csv(st.session_state.cache_file,index=False)

def log_percentiles(company_name, compliance_score, awareness_score):
    """Log compliance and awareness scores to percentiles CSV"""
    log_path = Path("percentiles_log/percentiles.csv")
    os.makedirs("percentiles_log", exist_ok=True)
    
    # Create new row
    new_row = {
        "company_name": company_name,
        "compliance_score": round(compliance_score, 1),
        "awereness_score": round(awareness_score, 1)  # Note: keeping the typo "awereness" to match your CSV header
    }
    
    # Load existing data or create new
    if log_path.exists():
        df = pd.read_csv(log_path, sep=";")
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
    
    # Save back to CSV
    df.to_csv(log_path, sep=";", index=False)

# ─── Renderers ─────────────────────────────────────────────────────────────────

def render_title_page():
    # two 750px-high containers for images + splash
    col1, col2 = st.columns([3,1])
    with col1:
        with st.container(height=750, border=False):
            st.markdown(
                "<h1 style='font-size:110px;font-family:Montserrat;'>"
                "Pojďme se<br>podívat, jak jste na tom!</h1>",
                unsafe_allow_html=True
            )
            st.image("visuals/COMPLIANCE CHECKPOINT-2.png")
    with col2:
        with st.container(height=750, border=False):
            # blank lines
            for _ in range(12):
                st.text("")
            st.image(
                "visuals/progress_visual.svg",
                width=int(450*0.85)
            )
    if st.button("Začít audit"):
        st.session_state.page = 2
        st.rerun()

def render_audit_mode():
    st.header("Typ auditu")
    
    audit_type = st.radio(
        "Vyberte typ auditu:",
        ["Začít nový audit", "Pokračovat rozepsaný audit"],
        index=0
    )
    
    if audit_type == "Začít nový audit":
        company_name = st.text_input("Název společnosti:", key="company_input")  # Changed from "company" to "company_input"
        
        if st.button("Začít", disabled=not company_name):
            # Store company name in session state
            st.session_state.company = company_name  # Now this works because there's no widget conflict
            
            # Load questions and initialize answers
            st.session_state.global_questions = questions_df.copy()
            st.session_state.global_answers = pd.DataFrame({
                "fulfilled": [np.nan] * len(questions_df),
                "awareness": [np.nan] * len(questions_df)
            }).astype(float)
            
            # Create cache file with company name
            safe = slugify(st.session_state.company)
            now = datetime.datetime.now()
            st.session_state.cache_file = f"cache/{safe}_{now:%Y%m%d_%H%M%S}.csv"
            save_global_progress()
            
            # Move to area selection
            st.session_state.page = 3
            st.rerun()
    
    else:  # "Pokračovat rozepsaný audit"
        cache_files = list(Path("cache").glob("*.csv")) if Path("cache").exists() else []
        
        if cache_files:
            st.session_state.resume_file = st.selectbox(
                "Vyberte soubor k pokračování:",
                [f.name for f in cache_files]
            )
            
            if st.button("Pokračovat"):
                path = Path("cache") / st.session_state.resume_file
                loaded = pd.read_csv(path)
                
                # Extract company name from the cached file
                if "company_name" in loaded.columns:
                    st.session_state.company = loaded["company_name"].iloc[0]
                else:
                    # Fallback: extract from filename if no company_name column
                    filename_parts = st.session_state.resume_file.split("_")
                    if len(filename_parts) > 2:
                        st.session_state.company = "_".join(filename_parts[:-2])  # Remove timestamp parts
                    else:
                        st.session_state.company = "Unknown Company"
                
                # Split the loaded data back into questions and answers
                st.session_state.global_questions = loaded.drop(columns=["answer_fulfilled", "answer_awareness"] + 
                                                               (["company_name"] if "company_name" in loaded.columns else []))
                st.session_state.global_answers = pd.DataFrame({
                    "fulfilled": loaded["answer_fulfilled"],
                    "awareness": loaded["answer_awareness"]
                }).astype(float)
                
                st.session_state.cache_file = str(path)
                st.session_state.page = 3
                st.rerun()
        else:
            st.warning("Žádné cache soubory nebyly nalezeny.")

def render_area_menu():
    st.header("Vyberte oblast")
    
    # Hardcoded areas (placeholders)
    HARDCODED_AREAS = [
        "BOZP & PO",
        "ONBOARDING & OFFBOARDING",
        "PRACOVNÍ DOBA &ČERPÁNÍ VOLNA",
        "KANCELÁŘ",
        "WHISTLEBLOWING",
        "GDPR",
        "ODMĚŇOVÁNÍ",
        "KONTRAKTOŘI",
        "FINANCE A ÚČETNICTVÍ",
        "SLUŽEBNÍ CESTY A VÝDAJE"
    ]
    
    cols = st.columns(2)
    for i, area in enumerate(HARDCODED_AREAS):
        with cols[i%2]:
            # Calculate scores for this area if it exists in dataframe
            mask = st.session_state.global_questions.area == area
            q = st.session_state.global_questions[mask]
            a = st.session_state.global_answers[mask]
            
            if len(q) > 0:  # Area exists in dataframe
                f = pd.to_numeric(a.fulfilled, errors="coerce").fillna(0)
                wf = q.weight_fulfilled.sum() or 1
                comp = (f * q.weight_fulfilled).sum() / wf * 100
                av = pd.to_numeric(a.awareness, errors="coerce").fillna(0)
                wa = q.weight_awareness.sum() or 1
                aw = (av * q.weight_awareness).sum() / wa * 100
            else:  # Area doesn't exist in dataframe
                comp, aw = 0, 0

            with st.container(height=100, border=False):
                btn = st.button(f"**{area}**", use_container_width=True,
                                key=f"area_{slugify(area)}")
                st.markdown(
                    f"<div style='display:flex;align-items:center;"
                    f"justify-content:center;height:30px;'>"
                    f"<div style='font-weight:700;'>Compliance: {comp:.0f}%</div>"
                    f"<div style='width:20px;'></div>"
                    f"<div style='font-weight:700;'>Awareness: {aw:.0f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            if btn:
                # Filter questions dataframe by selected area
                filtered_questions = st.session_state.global_questions[
                    st.session_state.global_questions.area == area
                ].reset_index(drop=True)
                
                # Store filtered data in session state
                st.session_state.current_area = area
                st.session_state.filtered_questions = filtered_questions
                
                # Move to page 4
                st.session_state.page = 4
                st.rerun()

    st.markdown("---")
    if st.button("Souhrn výsledků", use_container_width=True):
        st.session_state.page = 5
        st.rerun()

def render_progress():
    if len(st.session_state.filtered_questions) == 0:
        return
        
    current_idx = st.session_state.current_question_idx
    total = len(st.session_state.filtered_questions)
    current = current_idx + 1  # 1-based

    # Window logic: show 20 questions at a time
    window_size = 20
    window_index = (current - 1) // window_size  # 0 for questions 1–20, 1 for 21–40, etc.
    start = window_index * window_size + 1
    end = min(start + window_size - 1, total)

    tracker_html = (
        '<div style="display:flex; justify-content:space-between; '
        'align-items:flex-end; width:100%;">'
    )

    for step in range(start, end + 1):
        idx = step - 1
        # Get the question from filtered_questions
        filtered_question = st.session_state.filtered_questions.iloc[idx]
        
        # Find corresponding answer in global_answers by matching question text
        try:
            global_idx = st.session_state.global_questions[
                st.session_state.global_questions['question'] == filtered_question['question']
            ].index[0]
            val = st.session_state.global_answers.at[global_idx, "fulfilled"]
            
            # Pick color based on answer
            if pd.isna(val):
                color = "black"
            elif val == 1:
                color = "green"
            elif val == 0.5:
                color = "orange"
            elif val == 0:
                color = "red"
            else:
                color = "black"
        except Exception:
            color = "black"

        # Indicator if this is the current step
        if step == current and indicator_b64:
            indicator_html = (
                f'<img src="data:image/png;base64,{indicator_b64}" '
                'width="24" style="margin-bottom:4px;" />'
            )
        else:
            indicator_html = '<div style="height:24px;"></div>'

        number_html = f"<div style='color:{color}; font-weight:bold;'>{step}</div>"

        tracker_html += (
            "<div style='flex:1; text-align:center;'>"
            f"{indicator_html}{number_html}"
            "</div>"
        )

    tracker_html += "</div>"
    st.markdown(tracker_html, unsafe_allow_html=True)

def render_questions():
    # Initialize question index if not exists
    if "current_question_idx" not in st.session_state:
        st.session_state.current_question_idx = 0
    
    # Display current question
    if len(st.session_state.filtered_questions) > 0:
        current_idx = st.session_state.current_question_idx
        total_questions = len(st.session_state.filtered_questions)
        question = st.session_state.filtered_questions.iloc[current_idx]
        
        # Small area title container
        with st.container():
            st.markdown(
                f"<div style='text-align:center;font-size:16px;color:#666;margin-bottom:20px;'>"
                f"{st.session_state.current_area}</div>",
                unsafe_allow_html=True
            )
        
        # Main question container - eye catcher
        with st.container():
            col1, col2, col3 = st.columns([1,3,1])
            with col2:
                with st.container(height=300, border=False):
                    # st.markdown(
                    #     f"<h3 style='text-align:center;margin-bottom:20px;color:#333;'>"
                    #     f"Otázka {current_idx + 1}/{total_questions}</h3>",
                    #     unsafe_allow_html=True
                    # )
                    st.markdown(
                        f"<h1 style='text-align:center;font-size:32px;font-weight:bold;margin-bottom:40px;line-height:1.3;'>"
                        f"{question['question']}</h1>",
                        unsafe_allow_html=True
                    )
        
        # Answer buttons container
        with st.container():
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                if st.button("Jsem si plně vědom/á a uplatňujeme", 
                           key=f"btn1_{current_idx}", use_container_width=True):
                    question_idx = st.session_state.global_questions[
                        st.session_state.global_questions['question'] == question['question']
                    ].index[0]
                    st.session_state.global_answers.at[question_idx, 'fulfilled'] = 1.0
                    st.session_state.global_answers.at[question_idx, 'awareness'] = 1.0
                    save_global_progress()
                    st.session_state.current_question_idx += 1
                    if st.session_state.current_question_idx >= total_questions:
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                    st.rerun()
                    
                if st.button("Jsem si vědom/á a částečně uplatňujeme", 
                           key=f"btn2_{current_idx}", use_container_width=True):
                    question_idx = st.session_state.global_questions[
                        st.session_state.global_questions['question'] == question['question']
                    ].index[0]
                    st.session_state.global_answers.at[question_idx, 'fulfilled'] = 0.5
                    st.session_state.global_answers.at[question_idx, 'awareness'] = 1.0
                    save_global_progress()
                    st.session_state.current_question_idx += 1
                    if st.session_state.current_question_idx >= total_questions:
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                    st.rerun()
                    
                if st.button("Jsem si vědom/á, ale neuplatňujeme", 
                           key=f"btn3_{current_idx}", use_container_width=True):
                    question_idx = st.session_state.global_questions[
                        st.session_state.global_questions['question'] == question['question']
                    ].index[0]
                    st.session_state.global_answers.at[question_idx, 'fulfilled'] = 0.0
                    st.session_state.global_answers.at[question_idx, 'awareness'] = 1.0
                    save_global_progress()
                    st.session_state.current_question_idx += 1
                    if st.session_state.current_question_idx >= total_questions:
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                    st.rerun()
                    
                if st.button("Nejsem si vědom/á a neuplatňujeme", 
                           key=f"btn4_{current_idx}", use_container_width=True):
                    question_idx = st.session_state.global_questions[
                        st.session_state.global_questions['question'] == question['question']
                    ].index[0]
                    st.session_state.global_answers.at[question_idx, 'fulfilled'] = 0.0
                    st.session_state.global_answers.at[question_idx, 'awareness'] = 0.0
                    save_global_progress()
                    st.session_state.current_question_idx += 1
                    if st.session_state.current_question_idx >= total_questions:
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                    st.rerun()
                    
                if st.button("Nejsem si jistý/á", 
                           key=f"btn5_{current_idx}", use_container_width=True):
                    question_idx = st.session_state.global_questions[
                        st.session_state.global_questions['question'] == question['question']
                    ].index[0]
                    st.session_state.global_answers.at[question_idx, 'fulfilled'] = np.nan
                    st.session_state.global_answers.at[question_idx, 'awareness'] = np.nan
                    save_global_progress()
                    st.session_state.current_question_idx += 1
                    if st.session_state.current_question_idx >= total_questions:
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                    st.rerun()
        
        # Progress tracker container
        with st.container():
            st.markdown("<div style='margin:40px 0;'></div>", unsafe_allow_html=True)
            render_progress()
            st.markdown("<div style='margin:40px 0;'></div>", unsafe_allow_html=True)
        
        # Navigation buttons container
        with st.container():
            nav_col1, nav_col2, nav_col3 = st.columns([2,2,2])
            
            with nav_col1:
                with st.container():
                    if current_idx > 0:
                        if st.button("← Zpět", key=f"nav_back_{current_idx}"):
                            st.session_state.current_question_idx -= 1
                            st.rerun()
                
            with nav_col2:
                with st.container(horizontal_alignment="center"):
                    if st.button("Vrátit se do menu", key=f"nav_menu_{current_idx}"):
                        st.session_state.page = 3
                        st.session_state.current_question_idx = 0
                        st.rerun()
            
            with nav_col3:
                with st.container(horizontal_alignment="right"):
                    if current_idx < total_questions - 1:
                        if st.button("Další →", key=f"nav_next_{current_idx}"):
                            st.session_state.current_question_idx += 1
                            st.rerun()
    else:
        st.warning("No questions found for this area")

def render_summary():
    df = st.session_state.global_questions
    a  = st.session_state.global_answers
    f = pd.to_numeric(a.fulfilled,errors="coerce").fillna(0)
    av= pd.to_numeric(a.awareness,errors="coerce").fillna(0)
    wf, wa = df.weight_fulfilled.sum() or 1, df.weight_awareness.sum() or 1
    comp = (f*df.weight_fulfilled).sum()/wf*100
    aw   = (av*df.weight_awareness).sum()/wa*100

    # Load percentiles data to calculate percentiles
    percentiles_path = Path("percentiles_log/percentiles.csv")
    if percentiles_path.exists():
        percentiles_df = pd.read_csv(percentiles_path, sep=";")
        
        # Calculate percentiles
        comp_percentile = stats.percentileofscore(percentiles_df['compliance_score'], comp, kind='rank')
        aw_percentile = stats.percentileofscore(percentiles_df['awereness_score'], aw, kind='rank')
    else:
        comp_percentile = None
        aw_percentile = None

    with st.container(height=95, border=False):
        st.markdown(
            "<div style='height:95px;overflow:hidden;display:flex;align-items:center;justify-content:center;'>"
            "<h1 style='font-size:70px;font-family:Montserrat;margin:0;text-align:center;'>Souhrn výsledků</h1>"
            "</div>",
            unsafe_allow_html=True
        )
    
    with st.container(height=80, border=False):
        c1,c2 = st.columns(2)
        with c1:
            st.markdown(
                f"<div style='text-align:center;font-family:Montserrat;'>"
                f"<div style='font-size:14px;color:#666;margin-bottom:5px;'>Compliance score</div>"
                f"<div style='font-size:36px;font-weight:bold;'>{comp:.0f}%</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f"<div style='text-align:center;font-family:Montserrat;'>"
                f"<div style='font-size:14px;color:#666;margin-bottom:5px;'>Awareness score</div>"
                f"<div style='font-size:36px;font-weight:bold;'>{aw:.0f}%</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    
    with st.container(height=80, border=False):
        c1,c2 = st.columns(2)
        with c1:
            st.markdown(
                f"<div style='text-align:center;font-family:Montserrat;'>"
                f"<div style='font-size:14px;color:#666;margin-bottom:5px;'>Percentil</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#000;'>"
                f"{str(int(comp_percentile)) + '. percentil' if comp_percentile is not None else 'Nedostatek dat'}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f"<div style='text-align:center;font-family:Montserrat;'>"
                f"<div style='font-size:14px;color:#666;margin-bottom:5px;'>Percentil</div>"
                f"<div style='font-size:24px;font-weight:bold;color:#000;'>"
                f"{str(int(aw_percentile)) + '. percentil' if aw_percentile is not None else 'Nedostatek dat'}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    
    

    # Area breakdown rendered as a 3-column table with transparent borders
    table_rows = []
    for area in df.area.unique():
        mask = df.area == area
        wf2 = df[mask].weight_fulfilled.sum() or 1
        wa2 = df[mask].weight_awareness.sum() or 1
        c2 = (f[mask] * df[mask].weight_fulfilled).sum() / wf2 * 100
        a2 = (av[mask] * df[mask].weight_awareness).sum() / wa2 * 100
        table_rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;font-weight:700;border:1px solid transparent;'>{area}</td>"
            f"<td style='padding:8px 12px;text-align:right;border:1px solid transparent;min-width:110px;'>{c2:.0f}%</td>"
            f"<td style='padding:8px 12px;text-align:right;border:1px solid transparent;min-width:110px;'>{a2:.0f}%</td>"
            f"</tr>"
        )

    table_html = (
        "<div style='max-width:900px;margin:0px auto;padding:12px;border-radius:8px;background:transparent;font-family:Montserrat,Arial,sans-serif;'>"
        "<table style='width:100%;border-collapse:separate;border-spacing:0;'>"
        "<thead>"
        "<tr>"
        "<th style='text-align:left;padding:8px 12px;border:1px solid transparent;'>Oblast</th>"
        "<th style='text-align:right;padding:8px 12px;border:1px solid transparent;'>Compliance</th>"
        "<th style='text-align:right;padding:8px 12px;border:1px solid transparent;'>Awareness</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        + "".join(table_rows)
        + "</tbody></table></div>"
    )

    st.markdown(table_html, unsafe_allow_html=True)
    if st.button("Exportovat CSV", key="export_csv"):
        safe = slugify(st.session_state.company)
        now  = datetime.datetime.now()
        fn   = f"{safe}_audit_{now:%Y%m%d_%H%M%S}.csv"
        os.makedirs("answers_logs",exist_ok=True)
        out = df.copy()
        out["answer_fulfilled"] = a.fulfilled
        out["answer_awareness"]  = a.awareness
        path = Path("answers_logs")/fn
        out.to_csv(path,index=False)
        st.success(f"Uloženo: {path}")
        
        # Log percentiles
        log_percentiles(st.session_state.company, comp, aw)
        
    with st.container(horizontal_alignment="center"):
        if st.button("Vrátit se do menu", key="nav_menu_summary"):
            st.session_state.page = 3
            st.session_state.current_question_idx = 0
            st.rerun()

# ─── Main routing ──────────────────────────────────────────────────────────────
if   st.session_state.page == 1: render_title_page()
elif st.session_state.page == 2: render_audit_mode()
elif st.session_state.page == 3: render_area_menu()
elif st.session_state.page == 4: render_questions()
elif st.session_state.page == 5: render_summary()
