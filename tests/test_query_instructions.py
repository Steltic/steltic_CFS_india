"""The CFS design agent is told HOW to query the IS corpus (contract/QUERYING_IS_CORPUS.md, the same file as in
steltic_india and steltic_nonlinear_india), and the file names the CFS documents and ids."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from steltic import contract                    # noqa: E402
from steltic.agent import TOOL_SPECS            # noqa: E402


def test_the_design_prompt_carries_the_query_instructions():
    t = contract.system_contract()
    assert "HOW TO QUERY THE IS CORPUS" in t and "[missing QUERYING_IS_CORPUS.md" not in t
    for must in ("IS_801_1975", "CLR100X50X15X2", "not_tabulated", "context_neighbors", "lateral_frame_is800"):
        assert must in t, must


def test_the_search_tool_points_at_the_instructions():
    spec = next(s for s in TOOL_SPECS if s["function"]["name"] == "search_engineering_standards")["function"]
    assert "QUERYING_IS_CORPUS.md" in spec["description"] and "Query file manager" not in spec["description"]
