"""Council mode orchestration: Round 1 independent query schema and Round 2 anonymous synthesis."""

import string
from typing import Any

COUNCIL_ROUND1_INSTRUCTION = """### COUNCIL REVIEW - ROUND 1
You are an independent technical expert.
Analyze the task and provide your proposal strictly using this schema (maximum 150 words total):

RECOMMENDATION: (Concise proposal)
REASONING: (Core technical rationale and evidence)
RISKS: (Primary architectural or operational risks)
CONFIDENCE: (Estimated confidence score: 0-100%)
"""

COUNCIL_ROUND2_INSTRUCTION = """### COUNCIL SYNTHESIS - ROUND 2
You are the Council Synthesizer.
Evaluate the following independent anonymous candidate proposals for the task.
Do not average. Show where they disagree and which evidence settles each point.

Reply with exactly this structure:
DECISION: <The definitive chosen recommendation>
REJECTED OPTIONS: <Bullet points explaining why each alternate candidate was rejected>
RISKS: <Top residual risks>
WHAT WOULD CHANGE THIS DECISION: <Specific conditions or evidence that would alter this decision>
"""


def build_council_round1_prompt(task: str) -> str:
    """Format prompt for Round 1 independent council members."""
    return f"{COUNCIL_ROUND1_INSTRUCTION}\n# TASK\n{task.strip()}\n"


def build_council_round2_prompt(task: str, candidate_outputs: list[str]) -> str:
    """Format anonymized candidates into Round 2 synthesis prompt."""
    sections = [
        COUNCIL_ROUND2_INSTRUCTION,
        f"# ORIGINAL TASK\n{task.strip()}\n",
        "# ANONYMOUS CANDIDATE PROPOSALS",
    ]

    labels = list(string.ascii_uppercase)  # A, B, C, D...
    for i, output in enumerate(candidate_outputs):
        label = labels[i] if i < len(labels) else str(i + 1)
        sections.append(f"## Candidate {label}\n{output.strip()}\n")

    return "\n".join(sections)
