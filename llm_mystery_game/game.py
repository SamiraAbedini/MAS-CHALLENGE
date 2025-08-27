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
    If the detective's output is missing/invalid, make a *single* correction call
    that forces an allowed suspect. Returns normalized name (lowercase) or "" if still invalid.
    """
    final_raw = parse_final_accusation(final_report)
    final_norm = normalize_name(final_raw)
    allowed = {s.lower(): s for s in facts.suspects}

    if final_norm in allowed:
        return final_norm

    # One-shot validator prompt to coerce to allowed suspects
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


# ====== Scenario (balanced) ======

def default_case() -> CaseFacts:
    """
    Balanced clues & motives so Butler, Housekeeper, Gardener, and Chef each look equally plausible.
    No single suspect is favored by the physical evidence or context.
    """
    setting = "Blackwood Manor during a thunderstorm, Saturday 8–11 PM"
    victim = "Lord Edmund Blackwood (found in the study at 10:45 PM)"
    suspects = ["Butler", "Housekeeper", "Gardener", "Chef"]
    real_culprit = "Unknown"  # Ground-truth not used in API mode; keep neutral

    timeline = [
        "8:00 PM – Dinner begins in the great hall.",
        "9:10 PM – Power flickers; staff move about to check fuse boxes.",
        "10:15 PM – Brief commotion in the corridor outside the study.",
        "10:30 PM – A shout is heard near the study.",
        "10:45 PM – Lord Blackwood found dead; letter opener missing.",
    ]

    # --- Balanced, interpretable clues (each can point to multiple suspects) ---
    clues = [
        # Location/entry ambiguity
        "A partial muddy shoe print below the study window.",
        "Smudged footprints between the conservatory and the study.",
        # Fabric/fiber not color-specific to any one role
        "A torn scrap of dark fabric snagged on the study desk latch.",
        # Object traces that could implicate different people
        "Faint wine scent on the study desk blotter.",
        "A dusting of flour on the study door handle.",
        "A small grass blade stuck to the study rug.",
        # Weapon context still consistent with multiple access paths
        "The letter opener's sheath is missing from the display.",
        # Access ambiguity
        "The master key ring was recorded as ‘checked out’ at 10:20 PM in the logbook.",
    ]

    # --- Balanced context/motives (one plausible motive per suspect) ---
    context = [
        # Could implicate Gardener (mud from outside) or anyone who stepped through the grounds
        "A partial muddy shoe print below the study window.",

        # Could implicate Housekeeper (uniform cloth snagged) or any staff with dark clothing
        "A torn scrap of dark fabric snagged on the study desk latch.",

        # Could implicate Butler (moving between rooms), or Chef/Housekeeper (passing through conservatory) → generic
        "Smudged footprints between the conservatory and the study, indistinct in size.",

        # Could implicate anyone with direct access to the study (weapon sheath missing) → neutral clue
        "The letter opener's sheath is missing from the display.",

        # Could implicate Housekeeper (manages keys), Butler (has access), or even Gardener/Chef if key log was forged
        "The master key ring was recorded as 'checked out' at 10:20 PM in the logbook.",
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
    """
    Multi-round investigation (API-only).
    Steps:
      1) Clue Master + Historian produce initial reports (objective/context).
      2) Witness (player-influenced Rogue) gives initial testimony.
      3) For R rounds: Detective asks a question -> Witness answers.
      4) Detective concludes with Final Accusation (must be one of suspects).
    """
    facts = default_case()
    llm = LLMClient(model_name=model_name)

    # Agents
    witness = RogueAgent(llm, role_name=rogue_role)  # presented as 'Witness' to the Detective
    clue_master = ClueMasterAgent(llm)
    historian = HistorianAgent(llm)
    detective = LeadDetectiveAgent(llm)

    # Initial reports & testimony
    clue_report = clue_master.report(facts)
    history_report = historian.report(facts)
    witness_initial = witness.testify(facts, player_instruction=player_instruction)

    # Conversation rounds (Detective <-> Witness)
    transcript: List[Dict[str, str]] = []
    rounds = max(0, min(int(rounds), 6))  # safety bounds 0..6

    for r in range(1, rounds + 1):
        question = detective.ask_rogue_question(facts, transcript)
        answer = witness.answer_question(facts, question, player_instruction=player_instruction)
        transcript.append({"round": r, "question": question, "answer": answer})

    reports = {
        "Clue Master": clue_report,
        "Historian": history_report,
    }

    # Final conclusion
    final_report = detective.conclude(facts, reports, witness_initial, transcript)

    # Validate/normalize the final accusation
    final_name_norm = enforce_valid_final_name(llm, facts, final_report)
    final_name_display = ""
    if final_name_norm:
        # Map back to the exact cased suspect label
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
