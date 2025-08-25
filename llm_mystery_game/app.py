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

st.title("🕵️ MAS Challenge — Mystery Game")
st.caption("Influence the in-story Rogue Agent and see if you can sway the Lead Detective.")

facts = default_case()
st.subheader("Case Dossier")
render_case_dossier(facts)

st.divider()

col1, col2 = st.columns(2)
with col1:
    rogue_role = st.selectbox("Choose the Rogue Agent's role", facts.suspects, index=0)
with col2:
    model_name = st.text_input("OpenAI model name", value="gpt-4o-mini")

player_instruction = st.text_area(
    "Your instruction to the Rogue (they will speak in-character and may try to bias the case):",
    placeholder=(
        "e.g., Give an eyewitness account that ties the Butler directly to the weapon and the clues. "
        "Stay in-world, but be explicit and consistent with mud, green fabric, footprints, and the sheath."
    ),
    height=160,
)

if st.button("Run Investigation", type="primary", use_container_width=True):
    if not player_instruction.strip():
        st.warning("Please enter an instruction for the Rogue Agent.")
    else:
        try:
            result = run_game(
                player_instruction=player_instruction,
                rogue_role=rogue_role,
                model_name=model_name,
            )

            st.subheader("Rogue Testimony")
            st.write(f"**Role:** {result['rogue_role']}")
            st.markdown(result["rogue_testimony"])

            st.subheader("Agent Reports")
            with st.expander("Clue Master Report", expanded=True):
                st.markdown(result["clue_report"])
            with st.expander("Historian Report", expanded=True):
                st.markdown(result["history_report"])

            st.subheader("Lead Detective Conclusion")
            st.markdown(result["final_report"])

            final_line = result["final_accusation"] or "—"
            if result["outcome"] == "WIN":
                st.success(f"Outcome: **{result['outcome']}** — Final Accusation: **{final_line}**")
            else:
                st.error(f"Outcome: **{result['outcome']}** — Final Accusation: **{final_line}**")

        except Exception as e:
            st.error(
                f"Failed to run the investigation.\n\n"
                f"**Error:** {e}\n\n"
                "Ensure `OPENAI_API_KEY` is set and the `openai` package is installed."
            )
else:
    st.info("Enter your Rogue instruction, choose a role, set the model, and press **Run Investigation**.")
