"""
First Law ("No Evidence, No Claim") verification: Evidence + TrustResult.

Covers the core semantics plus TrustResult adoption across powers:
multiagent subagent dispatch, the cross-device relay, and the
model->PDF pipeline must all return evidence-backed TrustResults.
"""

import pytest

from jarvis.core.evidence import Evidence, TrustResult


# --------------------------------------------------------------------- #
#  Core semantics                                                        #
# --------------------------------------------------------------------- #

def test_evidence_serialization_roundtrip():
    ev = Evidence(source="unit.test", data={"answer": 42}, trust_level="verified")
    d = ev.to_dict()
    assert d["source"] == "unit.test"
    assert d["data"] == {"answer": 42}
    assert d["evidence_id"].startswith("ev_")
    assert d["trust_level"] == "verified"

    back = Evidence.from_dict(d)
    assert back.source == ev.source
    assert back.data == ev.data
    assert back.evidence_id == ev.evidence_id


def test_success_factory_wraps_evidence():
    ev = Evidence(source="unit.ok", data={"x": 1})
    trust = TrustResult.success(evidence=ev, description="did the thing")
    assert trust.verdict == "success"
    assert trust.description == "did the thing"
    trust.assert_evidence_present()  # must not raise
    d = trust.to_dict()
    assert d["verdict"] == "success"
    assert d["evidence"]["source"] == "unit.ok"


def test_fail_factory_keeps_evidence():
    ev = Evidence(source="unit.fail", data={"reason": "nope"})
    trust = TrustResult.fail(evidence=ev, description="broke")
    assert trust.verdict == "fail"
    trust.assert_evidence_present()
    assert trust.to_dict()["evidence"]["data"]["reason"] == "nope"


def test_first_law_rejects_success_without_evidence():
    trust = TrustResult(verdict="success", evidence=None, description="trust me")
    with pytest.raises(AssertionError, match="First Law"):
        trust.assert_evidence_present()


def test_first_law_rejects_empty_evidence_source():
    ev = Evidence(source="   ", data={})
    trust = TrustResult.success(evidence=ev, description="hollow")
    with pytest.raises(AssertionError, match="First Law"):
        trust.assert_evidence_present()


# --------------------------------------------------------------------- #
#  Adoption: multiagent powers (PWR-288..308)                            #
# --------------------------------------------------------------------- #

def test_multiagent_coding_subagent_returns_trustresult():
    from jarvis.powers.multiagent_powers import MultiAgentPowers

    powers = MultiAgentPowers()
    result = powers.invoke_subagent("coder", {"task": "write tests"})

    assert "trust_result" in result, "coding subagent must return TrustResult"
    assert result["trust_result"]["verdict"] == "success"
    assert result["trust_result"]["evidence"]["source"].startswith("multiagent.")
    assert "evidence" in result


def test_multiagent_generic_subagent_also_adopted():
    """Non-coding roles must be evidence-backed too (adoption completeness)."""
    from jarvis.powers.multiagent_powers import MultiAgentPowers

    powers = MultiAgentPowers()
    for role in ("researcher", "reviewer", "memory_manager", "tool_selector"):
        result = powers.invoke_subagent(role, {"topic": "x"})
        assert "trust_result" in result, f"role {role} missing TrustResult"
        assert result["trust_result"]["verdict"] == "success"
        assert result["trust_result"]["evidence"]["source"]


# --------------------------------------------------------------------- #
#  Adoption: cross-device relay                                          #
# --------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_relay_returns_trustresult_for_commands():
    from jarvis.core.relay import DeviceRelay

    class Orch:
        async def process_user_query(self, q):
            return {"task_id": "t1", "status": "COMPLETED",
                    "response": {"message": "ok"}}

    relay = DeviceRelay(orchestrator=Orch())
    token = relay.exchange_code(relay.create_pairing_code()["code"])["token"]

    trust = await relay.execute_command(token, "hello")
    assert isinstance(trust, TrustResult)
    trust.assert_evidence_present()

    rejected = await relay.execute_command("bad", "hello")
    assert isinstance(rejected, TrustResult)
    assert rejected.verdict == "fail"
    rejected.assert_evidence_present()


# --------------------------------------------------------------------- #
#  Adoption: model -> PDF pipeline (PWR-316)                             #
# --------------------------------------------------------------------- #

def test_doc_pipeline_returns_trustresult(tmp_path):
    from jarvis.core.doc_pipeline import DocPipeline

    pipeline = DocPipeline()
    ok = pipeline.model_to_pdf("# Title\n\nBody text.", output_dir=tmp_path)
    assert isinstance(ok, TrustResult)
    ok.assert_evidence_present()
    assert ok.verdict == "success"

    bad = pipeline.model_to_pdf("", output_dir=tmp_path)
    assert isinstance(bad, TrustResult)
    assert bad.verdict == "fail"
    bad.assert_evidence_present()
