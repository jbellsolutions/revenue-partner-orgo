from __future__ import annotations

from pathlib import Path
import os
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
SKILL_ROOT = FILES / "skills/go-to-market/revenue-partner"


def text(path: Path) -> str:
    return path.read_text()


class RevenuePartnerBehaviorContractTests(unittest.TestCase):
    def test_skill_is_triggerable_and_source_aligned(self):
        skill = text(SKILL_ROOT / "SKILL.md")
        self.assertIn("name: revenue-partner", skill)
        self.assertIn("Money Desk", skill)
        self.assertIn("FIT_ASSESSMENT", skill)
        self.assertIn("OPERATE_AND_OPTIMIZE", skill)
        for channel in ("Affiliates", "Direct outbound", "Reactivation", "Social and content"):
            self.assertIn(channel, skill)

    def test_fit_gate_rejects_unvalidated_offer(self):
        body = text(SKILL_ROOT / "references/operating-system.md")
        self.assertRegex(body, r"(?i)(paid offer|commercial validation)")
        self.assertIn("not_fit", body)
        self.assertRegex(body, r"(?i)(do not|must not).{0,80}(launch|execute)")

    def test_target_is_explicitly_not_a_guarantee(self):
        combined = text(SKILL_ROOT / "SKILL.md") + text(FILES / "SOUL.md")
        self.assertIn("2–4", combined)
        self.assertRegex(combined, r"(?i)2–4.{0,120}(target|expectation).{0,120}(not.{0,20}guarantee|never.{0,20}guarantee)")

    def test_campaign_contract_has_bounded_approval_and_stop_rules(self):
        body = text(SKILL_ROOT / "references/campaign-contract.md")
        for phrase in (
            "Audience and exclusions",
            "Approved claims",
            "Suppression",
            "Pause",
            "Stop",
            "Fresh approval",
        ):
            self.assertIn(phrase, body)
        self.assertRegex(body, r"(?i)approval.{0,160}(cannot|does not).{0,100}(activate|authority)")

    def test_riley_keeps_relationships_human_owned(self):
        combined = text(SKILL_ROOT / "SKILL.md") + text(SKILL_ROOT / "references/operating-system.md")
        self.assertIn("SpeakerAgent Riley", combined)
        self.assertRegex(combined, r"(?i)human.{0,100}(relationship|closing)")

    def test_super_browser_and_scale_contract_are_explicit(self):
        body = text(SKILL_ROOT / "SKILL.md")
        self.assertIn("five-round council", body)
        self.assertIn("5,000", body)
        for term in ("provenance", "deduplication", "coverage", "exact count"):
            self.assertIn(term, body.lower())

    def test_skill_routes_reads_to_the_boxes_and_writes_to_the_approval_lifecycle(self):
        body = text(SKILL_ROOT / "SKILL.md")
        self.assertIn("browser-box", body)
        self.assertIn("data-box", body)
        self.assertRegex(body, r"(?i)external write.{0,120}approval lifecycle")
        self.assertRegex(body, r"(?i)browser-box here has read tools only")

    def test_source_ledger_contains_all_supplied_sources(self):
        ledger = text(SKILL_ROOT / "references/source-ledger.md")
        for source in (
            "https://aiintegraterz.com/revenue-partner",
            "kdvm_kRZk8A",
            "fAhwYrjmQRk",
            "BI-MNjm1tTQ",
        ):
            self.assertIn(source, ledger)
        self.assertIn("self-reported", ledger.lower())
        self.assertIn("not a guarantee", ledger.lower())

    def test_soul_is_revenue_partner_not_workspace_brand(self):
        soul = text(FILES / "SOUL.md")
        self.assertIn("Revenue Partner", soul)
        self.assertNotIn("Buzz", soul)
        self.assertIn("one story", soul.lower())
        self.assertIn("one dashboard", soul.lower())

    def test_public_branding_and_claims_are_qualified(self):
        readme = text(ROOT / "README.md")
        self.assertNotIn("Nick's Stack", readme)
        self.assertNotIn("Buzz", readme)
        self.assertNotIn("is fully observable", readme)
        self.assertNotIn("live, working agent", readme)
        self.assertIn("when configured", readme)

    def test_canonical_fit_call_and_economics_are_explicit(self):
        skill = text(SKILL_ROOT / "SKILL.md")
        soul = text(FILES / "SOUL.md")
        ledger = text(SKILL_ROOT / "references/source-ledger.md")
        combined = "\n".join((skill, soul, ledger))
        self.assertIn("Book a Fit Call", combined)
        self.assertIn("30–45 minute", combined)
        self.assertIn("no-pitch", combined)
        self.assertIn("honest fit assessment", combined)
        self.assertIn("internal base plus commission", skill)
        self.assertIn("straight growth monthly", skill)
        self.assertIn("Exact numbers and percentages are not published", skill)

    def test_knowledge_vault_has_no_secret_values(self):
        for path in (FILES / "agent-knowledge").rglob("*.md"):
            body = path.read_text()
            self.assertNotRegex(body, r"sk_live_[A-Za-z0-9]+", str(path))
            self.assertNotRegex(body, r"(?i)(api[_ -]?key|token)\s*[:=]\s*[A-Za-z0-9_-]{20,}", str(path))

    def test_repo_files_do_not_contain_supplied_key(self):
        needle = os.environ.get("ORGO_API_KEY", "")
        excluded = {".git", ".artifacts", ".ai-worktrees", "__pycache__"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in excluded for part in path.parts):
                continue
            try:
                body = path.read_text(errors="ignore")
            except OSError:
                continue
            if needle:
                self.assertNotIn(needle, body, str(path))
            self.assertNotRegex(
                body,
                r"(?i)ORGO_API_KEY\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}",
                str(path),
            )


if __name__ == "__main__":
    unittest.main()
