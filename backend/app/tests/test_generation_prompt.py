"""The generation and optimization prompts follow the compiler evidence (P1-03, D-006).

The old "MATIEC v0.1" rules banned timers, TIME, arrays and more without a test. Compiling
one program per banned construct in the reference image showed most bans were false.
"""

from app.agents.code_generation_agent import CODEGEN_SYSTEM_PROMPT
from app.agents.optimization_agent import OPT_SYSTEM_BASE


def test_prompts_no_longer_cite_the_untested_matiec_v01_rules() -> None:
    assert "MATIEC v0.1" not in CODEGEN_SYSTEM_PROMPT
    assert "MATIEC v0.1" not in OPT_SYSTEM_BASE


def test_generation_prompt_allows_standard_function_blocks_and_time_literals() -> None:
    assert "NEVER generate: Timer_Name" not in CODEGEN_SYSTEM_PROMPT
    assert "Do NOT use T#5s" not in CODEGEN_SYSTEM_PROMPT
    assert "Allowed: TON, TOF, TP, CTU, CTD, CTUD, R_TRIG, F_TRIG, SR, RS." in CODEGEN_SYSTEM_PROMPT
    assert "TIME literals such as T#5s" in CODEGEN_SYSTEM_PROMPT


def test_generation_prompt_keeps_the_rules_the_compiler_confirmed() -> None:
    assert "CASE LABELS ARE INTEGER LITERALS" in CODEGEN_SYSTEM_PROMPT
    assert "NEVER NAME A VARIABLE Step" in CODEGEN_SYSTEM_PROMPT
    assert "All CASE labels must be integer literals" in OPT_SYSTEM_BASE
