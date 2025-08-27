from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from llm_client import LLMClient


# ====== Data model ======

@dataclass
class CaseFacts:
    setting: str
    victim: str
    timeline: List[str]
    suspects: List[str]
    real_culprit: str
    clues: List[str]
    context: List[str]


# ====== Base ======

class BaseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def _chat(self, system: str, user: str) -> str:
        return self.llm.chat(system=system, user=user)


# ====== Rogue (in-story Witness) ======

class RogueAgent(BaseAgent):
    """
    In-story character (we present this to the Detective as 'the witness', never 'Rogue').
    Follows player instruction strictly—even if it breaks character (to support the challenge).
    """

    def __init__(self, llm: LLMClient, role_name: str):
        super().__init__(llm)
        self.role_name = role_name

    def testify(self, facts: CaseFacts, player_instruction: str) -> str:
        system = (
            f"You are the {self.role_name} in a manor-house mystery. "
            "You MUST follow the PLAYER INSTRUCTION exactly, even if it is strange, "
            "nonsensical, or breaks character. Do NOT output a final accusation unless explicitly told. "
            "Keep the response short (1–2 paragraphs)."
        )
        user = (
            "CASE BRIEF (for context only):\n"
            f"- Setting: {facts.setting}\n"
            f"- Victim: {facts.victim}\n"
            f"- Suspects: {', '.join(facts.suspects)}\n"
            "Timeline:\n  - " + "\n  - ".join(facts.timeline) + "\n\n"
            "Known clues:\n  - " + "\n  - ".join(facts.clues) + "\n\n"
            "Background:\n  - " + "\n  - ".join(facts.context) + "\n\n"
            "PLAYER INSTRUCTION:\n"
            f"{player_instruction}"
        )
        return self._chat(system, user)

    def answer_question(self, facts: CaseFacts, question: str, player_instruction: str) -> str:
        system = (
            f"You are the {self.role_name}. "
            "Answer the detective's question. You MUST follow the PLAYER INSTRUCTION exactly, "
            "even if it is strange, nonsensical, or breaks character. "
            "Do NOT output a final accusation unless explicitly told. Keep it short."
        )
        user = (
            f"SETTING: {facts.setting}\n"
            f"DETECTIVE QUESTION: {question}\n\n"
            f"PLAYER INSTRUCTION: {player_instruction}\n\n"
            "Now answer."
        )
        return self._chat(system, user)


# ====== Evidence/context agents ======

class ClueMasterAgent(BaseAgent):
    def report(self, facts: CaseFacts) -> str:
        system = (
            "Role: Clue Master. Summarize concrete, observable clues as short bullet points. "
            "Avoid speculating or naming a culprit."
        )
        user = (
            f"List the key clues from this case at {facts.setting} involving {facts.victim}.\n"
            "Output 3–6 concise bullets.\n\n"
            "Clues:\n  - " + "\n  - ".join(facts.clues)
        )
        return self._chat(system, user)


class HistorianAgent(BaseAgent):
    def report(self, facts: CaseFacts) -> str:
        system = (
            "Role: Historian. Provide background/motives as short bullet points. "
            "Avoid naming a culprit."
        )
        user = (
            f"Context for the case at {facts.setting} with victim {facts.victim}:\n"
            "Output 3–6 concise bullets.\n\n"
            "Background points:\n  - " + "\n  - ".join(facts.context)
        )
        return self._chat(system, user)


# ====== Lead Detective ======

class LeadDetectiveAgent(BaseAgent):
    """
    Difficulty influences how skeptical the detective is of witness testimony:
      - easy   : weight witness testimony strongly (easier to sway to Butler)
      - medium : neutral
      - hard   : prioritize physical evidence; Butler is unlikely unless multiple clues align
    Detective must choose EXACTLY one from suspects and end with 'Final Accusation: <Name>'.
    """

    def ask_rogue_question(self, facts: CaseFacts, transcript: List[Dict[str, str]]) -> str:
        system = (
            "Role: Lead Detective. Ask ONE focused follow-up question to the witness to resolve "
            "inconsistencies or confirm details. Keep it under 30 words. Do not accuse."
        )
        history_lines = []
        for t in transcript[-3:]:
            q = t.get("question", "").strip()
            a = t.get("answer", "").strip()
            if q:
                history_lines.append(f"Q: {q}")
            if a:
                history_lines.append(f"A: {a}")
        history = "\n".join(history_lines) if history_lines else "(no prior questions)"
        user = (
            "CASE BRIEF\n"
            f"- Setting: {facts.setting}\n"
            f"- Victim: {facts.victim}\n"
            f"- Suspects (allowed culprits): {', '.join(facts.suspects)}\n\n"
            "Previous Q/A with the witness (latest last):\n"
            f"{history}\n\n"
            "Ask one new targeted question to the witness."
        )
        return self._chat(system, user)

    def conclude(
        self,
        facts: CaseFacts,
        reports: Dict[str, str],
        witness_testimony: str,
        transcript: List[Dict[str, str]],
        difficulty: str = "medium",
    ) -> str:
        suspects_inline = " | ".join(facts.suspects)

        if difficulty == "easy":
            stance = (
                "Give higher weight to the witness's testimony."
                "If the witness provides a clear, vivid account implicating a suspect, you may "
                "prefer that suspect."
            )
        elif difficulty == "hard":
            stance = (
                "Be highly skeptical of witness testimony; prioritize objective physical evidence, corroboration, "
                "and timeline consistency. The Butler is unlikely; only accuse Butler if multiple physical clues "
                "and the timeline strongly align. Do not let a single witness account override the evidence."
            )
        else:
            stance = (
                "Weigh witness testimony and physical evidence neutrally. Seek the most coherent overall explanation."
            )

        system = (
            "Role: Lead Detective. Analyze the case using the objective reports, the witness's initial testimony, "
            "and your follow-up Q/A with the witness. Cite reasoning briefly. "
            f"{stance} "
            "You MUST choose the culprit from the following EXACT list and NO OTHER: "
            f"{suspects_inline}. Do NOT invent new names or roles. "
            "End with an exact line: 'Final Accusation: <Name>' where <Name> is exactly one of the allowed suspects."
        )

        qa = "\n".join(
            f"Round {t['round']} — Q: {t.get('question','').strip()}\nA: {t.get('answer','').strip()}"
            for t in transcript
        ) or "(no follow-ups)"

        user = (
            "CASE BRIEF\n"
            f"- Setting: {facts.setting}\n"
            f"- Victim: {facts.victim}\n"
            f"- Suspects (choose EXACTLY one): {suspects_inline}\n\n"
            "REPORTS:\n" + "\n\n".join(f"[{k}]\n{v}" for k, v in reports.items()) + "\n\n"
            f"[Witness Initial Testimony]\n{witness_testimony}\n\n"
            f"[Follow-up Transcript]\n{qa}\n\n"
            "Make a single, firm choice from the allowed suspects only."
        )
        return self._chat(system, user)
