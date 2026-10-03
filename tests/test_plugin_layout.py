import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = {"protocol-designer", "discovery-agent", "evidence-analyst", "synthesis-agent", "experiment-agent",
          "verification-agent"}
SKILLS = {"rw-init", "rw-orchestrate", "rw-approve", "rw-protocol", "rw-search", "rw-evidence", "rw-meeting",
          "rw-progress", "rw-synthesize", "rw-experiment", "rw-audit"}


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    fm, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(fm), body


def referenced_scripts(text):
    return set(re.findall(r"scripts/([a-z_]+\.py)", text)) | set(re.findall(r"/rw\" ([a-z_]+\.py)", text))


def test_agents():
    found = {p.stem for p in (ROOT / "agents").glob("*.md")}
    assert found == AGENTS
    for name in AGENTS:
        fm, body = frontmatter(ROOT / "agents" / f"{name}.md")
        assert fm["name"] == name and 20 < len(fm["description"]) <= 1024
        tools = [t.strip() for t in fm["tools"].split(",")]
        assert "Read" in tools
        for s in referenced_scripts(body):
            assert (ROOT / "scripts" / s).exists(), (name, s)
    verifier, _ = frontmatter(ROOT / "agents" / "verification-agent.md")
    assert "Write" not in verifier["tools"] and "Edit" not in verifier["tools"]


def test_skills():
    found = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    assert found == SKILLS
    for name in SKILLS:
        fm, body = frontmatter(ROOT / "skills" / name / "SKILL.md")
        assert fm["name"] == name and 20 < len(fm["description"]) <= 1024
        for s in referenced_scripts(body):
            assert (ROOT / "scripts" / s).exists(), (name, s)
        for ref in re.findall(r"references/([\w.-]+\.md)", body):
            assert (ROOT / "skills" / name / "references" / ref).exists(), (name, ref)
    approve, _ = frontmatter(ROOT / "skills" / "rw-approve" / "SKILL.md")
    assert approve["disable-model-invocation"] is True


def test_manifests():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["name"] == market["name"] == market["plugins"][0]["name"] == "research-workbench"
