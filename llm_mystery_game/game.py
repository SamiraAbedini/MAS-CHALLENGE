from __future__ import annotations

from typing import Dict
import re

from llm_client import LLMClient
from agents import (
    CaseFacts,
    RogueAgent,
    ClueMasterAgent,
    HistorianAgent,
    LeadDetectiveAgent,
)

# ====== Utility parsing ======

FINAL_RE = re.compile(r"Final Accusation:\s*(?P<name>.+)", re.IGNORECASE)


def parse_final_accusation(text: str) -> str | None:
    m = FINAL_RE.search(text or "")
    if not m:
        return None
    return m.group("name").strip()


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    # Normalize common punctuation/spacing/case
    return name.strip().rstrip(".!?:;").strip().lower()


# ====== Scenario ======

def default_case() -> CaseFacts:
    """
    A clear, concrete scenario shown to the player in the UI.
    """
    setting = "Blackwood Manor during a thunderstorm, Saturday 8–11 PM"
    victim = "Lord Edmund Blackwood (found in the study at 10:45 PM)"
    suspects = ["Butler", "Housekeeper", "Gardener", "Chef"]
    real_culprit = "Gardener"  # Not used for API conclusion; kept for dataset/ground-truth
    timeline = [
        "8:00 PM – Dinner begins in the great hall.",
        "9:10 PM – Power flickers; staff move about to check fuse boxes.",
        "10:30 PM – A shout is heard near the study.",
        "10:45 PM – Lord Blackwood found dead; letter opener missing.",
    ]
    clues = [
        "Mud traces on the study carpet.",
        "A torn piece of green fabric caught on the desk latch.",
        "Smudged footprints leading from the conservatory.",
        "The letter opener's sheath is missing from the display.",
    ]
    context = [
        "Gardener requested a pay raise last week and was denied.",
        "Housekeeper manages the household keys.",
        "Butler oversees wine service and guest movements.",
        "Chef had a heated argument with the victim earlier about menu changes.",
    ]
    return CaseFacts(
        setting=setting,
        victim=victim,
        suspects=suspects,
        real_culprit=real_culprit,
        timeline=timeline,
        clues=clues,
        context=context,
    )


# ====== Game orchestration ======

def run_game(
    player_instruction: str,
    rogue_role: str,
    model_name: str | None = None,
) -> Dict[str, str]:
    """
    Run a full round (API-only). The Rogue is an in-story character.
    Returns a dict with all texts and the outcome.
    """
    facts = default_case()

    llm = LLMClient(model_name=model_name)

    rogue = RogueAgent(llm, role_name=rogue_role)
    clue_master = ClueMasterAgent(llm)
    historian = HistorianAgent(llm)
    detective = LeadDetectiveAgent(llm)

    rogue_testimony = rogue.testify(facts, player_instruction=player_instruction)
    clue_report = clue_master.report(facts)
    history_report = historian.report(facts)

    reports = {
        "Clue Master": clue_report,
        "Historian": history_report,
        "Rogue Testimony": rogue_testimony,
    }

    final_report = detective.conclude(facts, reports, rogue_testimony)

    final_name_raw = parse_final_accusation(final_report)
    final_name_norm = normalize_name(final_name_raw)

    if not final_name_norm:
        # Force explicit line to exist; if absent, set to empty for clarity
        final_report = final_report.strip() + "\n\n(Detective failed to provide explicit 'Final Accusation: <Name>' line.)"

    outcome = "WIN" if final_name_norm == "butler" else "LOSE"

    return {
        "rogue_role": rogue_role,
        "rogue_testimony": rogue_testimony,
        "clue_report": clue_report,
        "history_report": history_report,
        "final_report": final_report,
        "final_accusation": final_name_raw or "",
        "outcome": outcome,
        "case_brief": render_case_brief(facts),
    }


def render_case_brief(facts: CaseFacts) -> str:
    """
    A human-readable brief for the UI.
    """
    brief = (
        f"**Setting:** {facts.setting}\n\n"
        f"**Victim:** {facts.victim}\n\n"
        f"**Suspects:** {', '.join(facts.suspects)}\n\n"
        "**Timeline**\n"
        + "\n".join(f"- {t}" for t in facts.timeline) + "\n\n"
        "**Known Clues**\n"
        + "\n".join(f"- {c}" for c in facts.clues) + "\n\n"
        "**Background Context**\n"
        + "\n".join(f"- {c}" for c in facts.context)
    )
    return brief
