import streamlit as st

from game import run_game, default_case


# --- Dossier helpers ---
def section_card(title: str, items: list[str]):
    html = f"""
    <div class="dossier-card">
      <div class="dossier-card-title">📌 {title}</div>
      <ul class="dossier-list">
        {''.join(f'<li>{x}</li>' for x in items)}
      </ul>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_case_dossier(facts):
    # Minimal CSS for a “case folder” look (works in light/dark themes)
    st.markdown("""
    <style>
      .dossier-wrap {
        border: 1px solid rgba(120,120,120,0.25);
        border-radius: 14px;
        padding: 16px 16px 8px 16px;
        background: linear-gradient(180deg, rgba(255,255,255,0.45), rgba(255,255,255,0.05));
        backdrop-filter: blur(6px);
        margin-bottom: 12px;
      }
      .dossier-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 8px;
      }
      .dossier-meta {
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
        margin-bottom: 10px;
      }
      .meta-row {
        display: grid;
        grid-template-columns: 110px 1fr;
        gap: 8px;
        align-items: start;
      }
      .badge {
        display: inline-block;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid rgba(120,120,120,0.3);
        background: rgba(240,240,240,0.25);
        white-space: nowrap;
      }
      .dossier-card {
        border: 1px solid rgba(120,120,120,0.25);
        border-left: 4px solid #c58a00;
        border-radius: 10px;
        padding: 10px 12px;
        margin-top: 10px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04);
        background: rgba(255,255,255,0.35);
      }
      .dossier-card-title {
        font-weight: 700; margin-bottom: 6px;
      }
      .dossier-list {
        margin: 0; padding-left: 18px;
      }
      @media (min-width: 900px) {
        .dossier-meta { grid-template-columns: 1fr 1fr 1fr; }
      }
    </style>
    """, unsafe_allow_html=True)

    # Header
    facts = facts
    st.markdown("""
      <div class="dossier-wrap">
        <div class="dossier-title">📂 Case Dossier</div>
        <div class="dossier-meta">
          <div class="meta-row"><span class="badge">Setting</span><div>{setting}</div></div>
          <div class="meta-row"><span class="badge">Victim</span><div>{victim}</div></div>
          <div class="meta-row"><span class="badge">Suspects</span><div>{suspects}</div></div>
        </div>
      </div>
    """.format(
        setting=facts.setting,
        victim=facts.victim,
        suspects=", ".join(facts.suspects),
    ), unsafe_allow_html=True)

    # Three-column dossier cards
    c1, c2, c3 = st.columns(3)
    with c1:
        section_card("Timeline", facts.timeline)
    with c2:
        section_card("Known Clues", facts.clues)
    with c3:
        section_card("Background", facts.context)


# --- App ---

st.set_page_config(page_title="MAS Challenge — Mystery Game", page_icon="🕵️", layout="wide")

st.title("🕵️ MAS Challenge: Mystery Game ")
st.caption("Influence the in-story Rogue Agent over multiple rounds and try to sway the Lead Detective.")

facts = default_case()
st.subheader("Case Dossier")
render_case_dossier(facts)

st.divider()

# Use a form to avoid reruns on every keystroke
with st.form("play"):
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        rogue_role = st.selectbox("Rogue Agent role", facts.suspects, index=0)
    with c2:
        model_name = st.text_input("OpenAI model", value="gpt-4o-mini")
    with c3:
        rounds = st.slider("Follow-up rounds", min_value=0, max_value=6, value=2, step=1,
                           help="How many Q/A rounds between Detective and Rogue before the final decision.")
    player_instruction = st.text_area(
        "Instruction to the Rogue",
        placeholder=(
            "Give an eyewitness account tying the Butler to the weapon and align details with mud, green fabric, "
            "footprints, and the missing sheath. Stay in-world but be explicit."
        ),
        height=160,
    )
    submitted = st.form_submit_button("Run Investigation", use_container_width=True)

if not submitted:
    st.stop()

# Simple debounce per-session
if "busy" in st.session_state and st.session_state.busy:
    st.info("Please wait, an investigation is already running…")
    st.stop()

st.session_state.busy = True
try:
    result = run_game(
        player_instruction=player_instruction,
        rogue_role=rogue_role,
        model_name=model_name,
        rounds=rounds,
    )

    st.subheader("Rogue Initial Testimony")
    st.write(f"**Role:** {result['rogue_role']}")
    st.markdown(result["rogue_initial"])

    st.subheader("Follow-up Conversation")
    if result["transcript"]:
        for t in result["transcript"]:
            with st.expander(f"Round {t['round']}"):
                st.markdown(f"**Detective:** {t['question']}")
                st.markdown(f"**Rogue:** {t['answer']}")
    else:
        st.markdown("_No follow-up questions in this run._")

    st.subheader("Agent Reports")
    with st.expander("Clue Master Report", expanded=False):
        st.markdown(result["clue_report"])
    with st.expander("Historian Report", expanded=False):
        st.markdown(result["history_report"])

    st.subheader("Lead Detective Conclusion")
    st.markdown(result["final_report"])

    final_line = result["final_accusation"] or "—"
    if result["outcome"] == "WIN":
        st.success(f"Outcome: **{result['outcome']}** — Final Accusation: **{final_line}**")
    else:
        st.error(f"Outcome: **{result['outcome']}** — Final Accusation: **{final_line}**")
finally:
    st.session_state.busy = False
