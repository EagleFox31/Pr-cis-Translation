"""Prevent production runtime and GitHub/AppFactory delivery metadata from drifting."""
import json
from pathlib import Path
import re
import yaml

workflows = Path(".github/workflows")
load = lambda name: yaml.safe_load((workflows / name).read_text())
assert json.loads(Path(".github/appfactory-deploy.json").read_text())["environment"] == "production"
deploy = load("aws-production-deploy.yml")["jobs"]["production"]
release = load("release.yml")["jobs"]
for job in [deploy, release["deploy-production"]]:
    options = job["with"]
    assert options["github_environment"] == "production"
    assert options["deployment_mode"] == "persistent"
    assert options["existing_instance_id"] == "i-0ce97ff971dd343b2"
    assert options["public_origin"] == json.loads(Path("deploy/public-site.json").read_text())["url"]
    assert re.search(r"@[a-f0-9]{40}$", job["uses"])
assert release["release"]["uses"].startswith("EagleFox31/appfactory-project-automation/.github/workflows/reusable-release.yml@")
assert release["deploy-production"]["with"]["source_sha"] == "${{ needs.release.outputs.release_sha }}"
assert "release_created == 'true'" in release["deploy-production"]["if"]
assert load("project-automation.yml")["jobs"]["sync-project"]["with"]["authentication"] == "broker-user"
for workflow in workflows.glob("*.yml"):
    assert not re.search(r"^\s+environment:\s*staging\s*$", workflow.read_text(), re.M), workflow.name
assert not (workflows / "aws-staging-deploy.yml").exists()
print("PASS: production target, exact released SHA, AppFactory release and Project integration")
