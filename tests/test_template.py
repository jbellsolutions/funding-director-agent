from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    def test_required_funding_and_runtime_files_exist(self) -> None:
        required = [
            "README.md",
            "START-HERE.md",
            "AGENTS.md",
            "setup.sh",
            "new-agent.sh",
            "compose.yml",
            "hermes-image/Dockerfile",
            "hermes/config.template.yaml",
            "orgo/deployment.json",
            "orgo/setup.sh",
            "orgo/verify.sh",
            "orgo/emergency-stop.sh",
            "orgo/resume-external-writes.sh",
            "orgo/FundingDirector.desktop",
            "policies/permissions.json",
            "org/registry.json",
            "files/SOUL.md",
            "files/AGENTS.md",
            "files/agent-knowledge/07.Funding Department Charter.md",
            "files/agent-knowledge/08.Funding Machine Operating Map.md",
            "files/local-packages/funding-director/config/products.json",
            "files/local-packages/funding-director/config/destinations.json",
            "files/local-packages/funding-director/config/training-sources.json",
            "files/local-packages/funding-director/src/funding_director/engine.py",
            "files/local-packages/funding-director/src/funding_director/ghl.py",
            "files/local-packages/funding-director/src/funding_director/mcp_server.py",
            "files/skills/funding/file-underwriting/SKILL.md",
            "files/skills/funding/product-routing/SKILL.md",
            "files/skills/funding/submission-operator/SKILL.md",
            "files/skills/funding/offer-comparison/SKILL.md",
            "files/skills/funding/training-ingestion/SKILL.md",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_runtime_is_exactly_pinned_everywhere(self) -> None:
        dockerfile = (ROOT / "hermes-image/Dockerfile").read_text()
        deployment = json.loads((ROOT / "orgo/deployment.json").read_text())
        setup = (ROOT / "orgo/setup.sh").read_text()
        self.assertIn(
            "v2026.8.31@sha256:64923faeae267792bf9bf87fe3b4c4869e35004e360c7df01730ad801b74d524",
            dockerfile,
        )
        runtime = deployment["runtime"]
        self.assertEqual("v2026.8.31", runtime["hermes_release"])
        self.assertEqual("29112bef099274229cadff79cdff7bf7b99c4b77", runtime["hermes_commit"])
        self.assertEqual("0.21.0", runtime["hermes_version"])
        for value in (
            runtime["hermes_release"],
            runtime["hermes_commit"],
            runtime["install_script_sha256"],
        ):
            self.assertIn(value, setup)
        self.assertNotIn(":latest", dockerfile)

    def test_super_browser_source_and_runtime_lock_are_unchanged(self) -> None:
        source_root = ROOT / "files/local-packages/super-browser/src"
        source_files = sorted(source_root.rglob("*.py"))
        digest = hashlib.sha256()
        for path in source_files:
            digest.update(path.relative_to(source_root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        self.assertEqual(21, len(source_files))
        self.assertEqual("7fad2facb6ba04f6f33c533aa3c5c36cd35afe27af50ef76e64587d292e12522", digest.hexdigest())
        lock = (ROOT / "files/local-packages/super-browser/requirements-runtime.lock").read_text()
        self.assertIn("playwright==1.60.0", lock)
        self.assertIn("--hash=sha256:", lock)
        self.assertIn("uv pip install --no-config", (ROOT / "hermes-image/Dockerfile").read_text())

    def _render(self, extra: dict[str, str]) -> str:
        env = {**os.environ, "HERMES_MODEL": "openai/gpt-5.6-luna", "AGENT_PERSONA": "concise", **extra}
        for name in (
            "FIREWORKS_API_KEY", "DEEPSEEK_API_KEY", "TOGETHER_API_KEY", "COMPOSIO_API_KEY",
            "FUNDING_MACHINE_API_KEY", "TELEGRAM_HOME_CHANNEL", "SLACK_HOME_CHANNEL",
            "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN",
            "BLUEBUBBLES_SERVER_URL", "BLUEBUBBLES_PASSWORD",
        ):
            if name not in extra:
                env.pop(name, None)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "config.yaml"
            subprocess.run(
                ["python3", str(ROOT / "scripts/render_config.py"), str(ROOT / "hermes/config.template.yaml"), str(output)],
                env=env,
                check=True,
            )
            return output.read_text()

    def test_minimal_config_is_funding_first_and_fail_closed(self) -> None:
        text = self._render({"TELEGRAM_BOT_TOKEN": "placeholder"})
        for required in (
            "funding-director-core:",
            "funding-director-approvals:",
            "mcp-funding-director-core",
            "mcp-funding-director-approvals",
            "verify_on_stop: true",
            "mode: manual",
            "hard_stop_enabled: true",
            "tirith_fail_open: false",
            "redact_pii: true",
            "redact_secrets: true",
            "fallback_providers: []",
        ):
            self.assertIn(required, text)
        self.assertNotIn("funding-machine:", text)
        self.assertNotIn("pandadoc:", text)
        self.assertNotIn("higgsfield:", text)
        self.assertNotIn("__", text)
        self.assertIn("exclude: [funding_submission_approve, ghl_action_approve]", text)
        self.assertIn("include: [funding_submission_approve, ghl_action_approve]", text)
        self.assertIn("trust: full", text)

    def test_full_config_adds_read_only_funding_machine_without_leaking_key(self) -> None:
        text = self._render({
            "SLACK_BOT_TOKEN": "placeholder",
            "SLACK_APP_TOKEN": "placeholder",
            "COMPOSIO_API_KEY": "ck_example",
            "FUNDING_MACHINE_API_KEY": "fmk_example",
            "FIREWORKS_API_KEY": "placeholder",
        })
        self.assertIn("funding-machine:", text)
        self.assertIn('Authorization: "Bearer fmk_example"', text)
        self.assertIn("trust: untrusted", text)
        self.assertIn("composio:", text)
        self.assertIn("api.fireworks.ai", text)

    def test_public_catalog_is_discovery_only(self) -> None:
        products = json.loads((ROOT / "files/local-packages/funding-director/config/products.json").read_text())
        self.assertGreaterEqual(len(products["products"]), 11)
        self.assertFalse(any(product["status"] == "active" for product in products["products"]))
        blocked = {product["product_id"]: product["status"] for product in products["products"]}
        self.assertEqual("blocked", blocked["credit-repair-referral"])
        destinations = json.loads((ROOT / "files/local-packages/funding-director/config/destinations.json").read_text())
        self.assertEqual([], destinations["destinations"])
        subprocess.run(
            ["python3", str(ROOT / "scripts/validate_funding_config.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_permissions_encode_the_founder_boundary(self) -> None:
        policy = json.loads((ROOT / "policies/permissions.json").read_text())
        actions = policy["actions"]
        self.assertEqual("human-only", actions["credit.pull_new"]["decision"])
        self.assertEqual("human-only", actions["offer.accept_or_sign"]["decision"])
        self.assertEqual("deny", actions["identity_or_credit_partner_rental"]["decision"])
        self.assertEqual("deny", actions["permission.self_expand"]["decision"])
        self.assertIn("one-time-approval", actions["submission.transmit"]["decision"])
        self.assertFalse(policy["standing_playbooks_enabled"])

    def test_slack_does_not_offer_approval_bypass_commands(self) -> None:
        manifest = (ROOT / "slack-manifest.yml").read_text()
        self.assertIn("name: Funding Director", manifest)
        self.assertIn("command: /approve", manifest)
        self.assertNotIn("command: /yolo", manifest)
        self.assertNotIn("command: /approvals", manifest)
        self.assertLessEqual(manifest.count("  - command:"), 50)

    def test_orgo_profile_has_funding_core_and_stop_controls(self) -> None:
        deployment = json.loads((ROOT / "orgo/deployment.json").read_text())
        self.assertEqual("system/hermes-agent@1.0.0", deployment["orgo_template_ref"])
        self.assertEqual("ai-guy-funding-director", deployment["computer_name"])
        setup = (ROOT / "orgo/setup.sh").read_text()
        for required in (
            "mcp-funding-director-core",
            "mcp-funding-director-approvals",
            "approvals.mode=manual",
            "tool_loop_guardrails.hard_stop_enabled=true",
            "security.tirith_fail_open=false",
            "FUNDING_DIRECTOR_STATE_DIR",
        ):
            self.assertIn(required, setup)
        self.assertIn("funding-director-core.trust full", setup)
        self.assertIn("funding-director-approvals.trust untrusted", setup)
        self.assertIn("EXTERNAL_WRITES_STOPPED", (ROOT / "orgo/emergency-stop.sh").read_text())

    def test_skill_frontmatter_is_valid(self) -> None:
        skill_paths = sorted((ROOT / "files/skills").rglob("SKILL.md"))
        self.assertGreaterEqual(len(skill_paths), 10)
        for path in skill_paths:
            text = path.read_text()
            self.assertTrue(text.startswith("---\n"), path)
            self.assertRegex(text, r"(?m)^name: [a-z0-9-]+$")
            self.assertRegex(text, r"(?m)^description: .+$")

    def test_no_secret_or_private_training_material_is_packaged(self) -> None:
        forbidden_literals = [
            "104.236.11.200", "100.117.225.14", "1itGOY-3Kv1H1g5y62VJ2K_K6u2u36QYDurzVyk_s970",
            "Mca set up", "identityiq.com/sc-securepreferred",
        ]
        secret_patterns = [
            re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{12,}"),
            re.compile(r"fmk_[A-Za-z0-9_-]{20,}"),
            re.compile(r"pit-[A-Za-z0-9_-]{20,}"),
            re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
            re.compile(r"sk-(?:live|test)?[_-]?[A-Za-z0-9]{20,}"),
        ]
        violations: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for literal in forbidden_literals:
                if literal in text and path != Path(__file__).resolve():
                    violations.append(f"{path.relative_to(ROOT)} contains private source material")
            for pattern in secret_patterns:
                if pattern.search(text) and path != Path(__file__).resolve():
                    violations.append(f"{path.relative_to(ROOT)} matches a secret pattern")
        self.assertEqual([], violations)

    def test_brand_and_handoff_are_funding_specific(self) -> None:
        readme = (ROOT / "README.md").read_text()
        handoff = (ROOT / "AGENTS.md").read_text()
        for required in (
            "backend business-funding co-founder",
            "deterministic core",
            "GoHighLevel",
            "Funding Machine",
        ):
            self.assertIn(required, readme + handoff)
        self.assertIn("Definition of done", handoff)
        self.assertNotIn("general business-and-life operator", readme + handoff)


if __name__ == "__main__":
    unittest.main()
