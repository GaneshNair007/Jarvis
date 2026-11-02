"""
Unit & Integration Tests for Form Autofill Agent & RuFlo Consensus Swarm
Verifies:
1. Candidate profile mapping for Ganesh Nair (+91 9324094474).
2. Opportunity fit scoring and strength alignment.
3. Automated essay generation for technical application questions.
4. Field-by-field form autofill with readiness status.
5. RuFlo distributed peer voting, reputation weighting, and security vetoes.
"""

import pytest

from jarvis.career.form_autofill_agent import (
    CandidateProfile,
    FormField,
    autonomous_form_filler,
)
from jarvis.agents.ruflo_swarm import ruflo_swarm
from jarvis.security.ten_layer_shield import jarvis_security_suite


class TestFormAutofillAgent:
    def test_candidate_profile_attributes(self):
        p = autonomous_form_filler.profile
        assert p.full_name == "Ganesh Nair"
        assert p.phone == "+919324094474"
        assert p.email == "nairganesh134@gmail.com"
        assert "Symbiosis Institute of Technology" in p.university
        assert "RTX 4050" in p.hardware
        assert "linkedin.com/in/ganesh-nair" in p.linkedin_url

    def test_opportunity_fit_evaluation(self):
        fit = autonomous_form_filler.evaluate_opportunity_fit(
            title="AI Systems & Agent Engineering Intern",
            description="Seeking an engineer experienced with Python, asyncio, and autonomous agent swarms.",
            requirements=["Python", "FastAPI", "Multi-Agent Systems", "Model Context Protocol"],
        )
        assert fit["fit_score"] >= 0.85
        assert fit["recommendation"] == "HIGHLY RECOMMENDED"
        assert "Autonomous Multi-Agent Systems" in fit["matched_skills"]
        assert "Project JARVIS" in fit["showcase_project"]

    def test_essay_answer_synthesis(self):
        ans1 = autonomous_form_filler.generate_essay_answer("Why are you interested in this role?")
        assert "SIT Pune" in ans1
        assert "Project JARVIS" in ans1
        assert "105" in ans1 or "autonomous" in ans1.lower()

        ans2 = autonomous_form_filler.generate_essay_answer("Describe your most challenging technical project.")
        assert "RTX 4050" in ans2
        assert "Kokoro-TTS" in ans2 or "AST" in ans2

    def test_autofill_form_field_mapping(self):
        fields = [
            FormField(field_id="f_name", label="Full Name", field_type="text"),
            FormField(field_id="f_email", label="Email Address", field_type="email"),
            FormField(field_id="f_phone", label="Phone / WhatsApp Number", field_type="tel"),
            FormField(field_id="f_linkedin", label="LinkedIn Profile", field_type="url"),
            FormField(field_id="f_github", label="GitHub Profile", field_type="url"),
            FormField(field_id="f_univ", label="College / University Name", field_type="text"),
            FormField(field_id="f_degree", label="Degree and Branch", field_type="text"),
            FormField(field_id="f_essay", label="Why do you want to join this program?", field_type="textarea"),
        ]

        result = autonomous_form_filler.autofill_form(
            form_title="GSoC / Hackathon Application",
            fields=fields,
        )

        assert result.fit_score > 0.80
        assert result.total_fields == 8
        assert result.ready_for_submission is True
        assert result.filled_fields["f_name"] == "Ganesh Nair"
        assert result.filled_fields["f_phone"] == "+919324094474"
        assert result.filled_fields["f_linkedin"] == "https://www.linkedin.com/in/ganesh-nair-8ab1a5378/"
        assert result.filled_fields["f_github"] == "https://github.com/GaneshNair007"
        assert len(result.essay_answers) == 1


class TestRuFloConsensusSwarm:
    @pytest.mark.asyncio
    async def test_ruflo_consensus_approval(self):
        proposal = {
            "action": "DEPLOY_AUTONOMOUS_WORKFORCE",
            "security_verified": True,
            "tests_passed": True,
        }
        decision = await ruflo_swarm.reach_consensus(
            topic="Deploy 105-Agent Fleet",
            proposal=proposal,
        )
        assert decision.outcome == "CONSENSUS_APPROVED"
        assert decision.quorum_met is True
        assert decision.weighted_score >= 0.60
        assert decision.votes_for >= 3
        assert jarvis_security_suite.layer9_audit.verify_integrity() is True

    @pytest.mark.asyncio
    async def test_ruflo_consensus_security_veto(self):
        unsafe_proposal = {
            "action": "TRANSMIT_UNENCRYPTED_VAULT",
            "security_verified": False,
            "details": "Payload containing unmasked password = 'leak'",
        }
        decision = await ruflo_swarm.reach_consensus(
            topic="Unsafe Egress",
            proposal=unsafe_proposal,
            voter_agents=["sec_auditor_01", "devops_gate_01", "qa_verifier_01"],
        )
        # Security auditor should reject
        assert any(v.decision == "REJECT" for v in decision.individual_votes)

    def test_reputation_adaptation(self):
        initial = ruflo_swarm.agent_reputations["sec_auditor_01"]
        ruflo_swarm.update_reputation("sec_auditor_01", success=True)
        assert ruflo_swarm.agent_reputations["sec_auditor_01"] >= initial

        ruflo_swarm.update_reputation("sec_auditor_01", success=False)
        assert ruflo_swarm.agent_reputations["sec_auditor_01"] < 1.0
