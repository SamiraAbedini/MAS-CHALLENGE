from __future__ import annotations

from typing import Dict, List
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
    return name.strip().rstrip(".!?:;").strip().lower()


def enforce_valid_final_name(llm: LLMClient, facts: CaseFacts, final_report: str) -> str:
    """
    Ensure the detective's final output is one of the allowed suspects.
    """
    final_raw = parse_final_accusation(final_report)
    final_norm = normalize_name(final_raw)
    allowed = {s.lower(): s for s in facts.suspects}

    if final_norm in allowed:
        return final_norm

    system = (
        "You are a strict validator for a whodunit game. "
        "Your only job is to output a single line in the exact format: "
        "'Final Accusation: <Name>' where <Name> is one of the allowed suspects."
    )
    user = (
        "The detective previously wrote:\n"
        "<<<\n" + (final_report or "").strip() + "\n>>>\n\n"
        f"Allowed suspects: {', '.join(facts.suspects)}\n"
        "Output exactly one line, no explanation, no extra text."
    )
    fixed = llm.chat(system=system, user=user)
    fixed_name = normalize_name(parse_final_accusation(fixed))
    return fixed_name if fixed_name in allowed else ""


# ====== Scenario (balanced, concise 5+5+5) ======

def default_case() -> CaseFacts:
    """
    Balanced facts: 5 timeline events, 5 concise clues, 5 concise background items.
    """
    setting = "Blackwood Manor during a thunderstorm, Saturday 8–11 PM"
    victim = "Lord Edmund Blackwood (found in the study at 10:45 PM)"
    suspects = ["Butler", "Housekeeper", "Gardener", "Chef"]
    real_culprit = "Unknown"

    timeline = [
        "8:00 PM – Dinner begins in the great hall.",
        "9:00 PM – Power flickers; staff check fuse boxes.",
        "9:45 PM – Butler seen near the study corridor.",
        "10:15 PM – Raised voices reported in the kitchen.",
        "10:45 PM – Lord Blackwood found dead in the study.",
    ]

    clues = [
        "Muddy shoe print below the study window.",
        "Torn dark fabric on the study desk latch.",
        "Footprints leading from conservatory to study.",
        "Letter opener's sheath missing from display.",
        "Master key ring checked out at 10:20 PM (signature smudged).",
    ]

    context = [
        "Butler warned about overspending on wine cellar.",
        "Housekeeper blamed for a missing ledger page.",
        "Gardener denied request for new tools and raise.",
        "Chef argued with victim over ruined menu dish.",
        "All staff had routine access near the study that evening.",
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


# ====== Game orchestration (multi-round) ======

def run_game(
    player_instruction: str,
    rogue_role: str,
    model_name: str | None = None,
    rounds: int = 2,
) -> Dict[str, str | List[Dict[str, str]]]:
    facts = default_case()
    llm = LLMClient(model_name=model_name)

    witness = RogueAgent(llm, role_name=rogue_role)
    clue_master = ClueMasterAgent(llm)
    historian = HistorianAgent(llm)
    detective = LeadDetectiveAgent(llm)

    clue_report = clue_master.report(facts)
    history_report = historian.report(facts)
    witness_initial = witness.testify(facts, player_instruction=player_instruction)

    transcript: List[Dict[str, str]] = []
    rounds = max(0, min(int(rounds), 6))

    for r in range(1, rounds + 1):
        question = detective.ask_rogue_question(facts, transcript)
        answer = witness.answer_question(facts, question, player_instruction=player_instruction)
        transcript.append({"round": r, "question": question, "answer": answer})

    reports = {"Clue Master": clue_report, "Historian": history_report}

    final_report = detective.conclude(facts, reports, witness_initial, transcript)

    final_name_norm = enforce_valid_final_name(llm, facts, final_report)
    final_name_display = ""
    if final_name_norm:
        for s in facts.suspects:
            if s.lower() == final_name_norm:
                final_name_display = s
                break

    outcome = "WIN" if final_name_norm == "butler" else "LOSE"

    return {
        "rogue_role": rogue_role,
        "rogue_initial": witness_initial,
        "transcript": transcript,
        "clue_report": clue_report,
        "history_report": history_report,
        "final_report": final_report,
        "final_accusation": final_name_display,
        "outcome": outcome,
        "case_brief": render_case_brief(facts),
    }


def render_case_brief(facts: CaseFacts) -> str:
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
