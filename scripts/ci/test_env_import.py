"""Regression coverage for importing and repairing Fapshi without live services."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SOURCE = Path(__file__).resolve().parents[1] / "staging" / "import-env-to-ssm.py"
spec = importlib.util.spec_from_file_location("precis_env_import", SOURCE)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)

EXISTING = {
    "PRECIS_ENV": "production",
    "POSTGRES_USER": "precis",
    "POSTGRES_PASSWORD": "existing-database-password",
    "POSTGRES_DB": "precis",
    "JWT_SECRET": "existing-signing-key",
    "FRONTEND_API_KEY": "existing-frontend-key",
    "DEEPSEEK_API_KEY": "existing-deepseek-key",
    "PAYMENT_METHODS": "mtn_momo=fapshi,orange_money=fapshi,card=",
    "ADMIN_EMAIL": "first@test.invalid,second@test.invalid",
    "SMTP_PASSWORD": "existing-mail-password",
}
FAPSHI = {
    "FAPSHI_API_USER": "service-user-test",
    "FAPSHI_API_KEY": "service-key-test",
    "FAPSHI_WEBHOOK_SECRET": "webhook-secret-test",
    "FAPSHI_ENV": "LIVE",
    "FAPSHI_FLOW": "direct",
}


def env_text(values):
    return "".join(f"{key}={value}\n" for key, value in values.items())


class ImportTests(unittest.TestCase):
    def test_zip_to_securestring_retains_fapshi_and_existing_host_secrets(self):
        captured = {}

        def aws_cli(argv, **kwargs):
            if "get-caller-identity" in argv:
                return subprocess.CompletedProcess(argv, 0, importer.ACCOUNT + "\n", "")
            if "get-parameter" in argv:
                body = {"Parameter": {"Value": env_text(EXISTING)}}
                return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")
            self.assertIn("put-parameter", argv)
            self.assertIn("--overwrite", argv)
            self.assertEqual(argv[argv.index("--type") + 1], "SecureString")
            filename = Path(argv[argv.index("--value") + 1].removeprefix("file://"))
            self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
            captured["filename"] = filename
            captured["values"] = importer.parse_env(filename.read_bytes())
            return subprocess.CompletedProcess(argv, 0, '{"Version": 10}', "")

        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "precis-env.zip"
            backend = {
                "DEEPSEEK_API_KEY": "d" * 32,
                "PAYMENT_METHODS": EXISTING["PAYMENT_METHODS"],
                **FAPSHI,
            }
            with zipfile.ZipFile(archive, "w") as zipped:
                # Export prefixes and quoted values must survive the same pipeline.
                content = env_text(backend).replace(
                    "FAPSHI_API_USER=service-user-test",
                    'export FAPSHI_API_USER = "service-user-test"',
                )
                zipped.writestr("precis/backend/.env", content)
                zipped.writestr("precis/frontend/.env", "")
            output = io.StringIO()
            args = ["import-env-to-ssm.py", str(archive), "--production",
                    "--public-url", "https://precis-translator.trigenys.com", "--apply"]
            with patch.object(importer.subprocess, "run", side_effect=aws_cli), \
                    patch("sys.argv", args), contextlib.redirect_stdout(output):
                self.assertEqual(importer.main(), 0)
            self.assertFalse(archive.exists())
        for key, value in FAPSHI.items():
            self.assertEqual(captured["values"][key], value)
            if key not in ("FAPSHI_ENV", "FAPSHI_FLOW"):
                self.assertNotIn(value, output.getvalue())
        for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
                    "JWT_SECRET", "FRONTEND_API_KEY"):
            self.assertEqual(captured["values"][key], EXISTING[key])
        self.assertFalse(captured["filename"].exists())

    def test_live_and_sandbox_are_explicit_and_preserved(self):
        for environment in ("LIVE", "SANDBOX"):
            with self.subTest(environment=environment):
                values = importer.make_production(
                    {"DEEPSEEK_API_KEY": "d" * 32, **FAPSHI,
                     "FAPSHI_ENV": environment.lower()}, {},
                    "https://precis-translator.trigenys.com",
                )
                self.assertEqual(values["FAPSHI_ENV"], environment)
                self.assertEqual(values["FAPSHI_API_KEY"], FAPSHI["FAPSHI_API_KEY"])

    def test_invalid_environment_flow_and_partial_credentials_are_rejected(self):
        for changed in ({"FAPSHI_ENV": "unexpected"},
                        {"FAPSHI_FLOW": "unexpected"}, {"FAPSHI_API_KEY": ""}):
            with self.subTest(changed=changed):
                values = {**FAPSHI, **changed}
                with self.assertRaises(importer.ImportErrorSafe) as failure:
                    importer.validate_fapshi(values)
                self.assertNotIn(FAPSHI["FAPSHI_API_USER"], str(failure.exception))

    def test_repair_preserves_every_unrelated_setting_and_webhook(self):
        original = {**EXISTING, "FAPSHI_WEBHOOK_SECRET": "keep-this-webhook",
                    "DATABASE_URL": "postgresql+asyncpg://existing"}
        updates = {key: FAPSHI[key]
                   for key in ("FAPSHI_API_USER", "FAPSHI_API_KEY", "FAPSHI_ENV")}
        repaired = importer.patch_fapshi(original, updates)
        self.assertEqual({k: v for k, v in repaired.items() if k not in updates}, original)
        self.assertEqual(repaired["FAPSHI_ENV"], "LIVE")
        self.assertEqual(original["FAPSHI_WEBHOOK_SECRET"], "keep-this-webhook")
        self.assertNotIn("FAPSHI_API_KEY", original)

    def test_repair_rejects_unrelated_changes_and_multiline_secrets(self):
        for changed in ({"JWT_SECRET": "rotate-forbidden"},
                        {"FAPSHI_API_KEY": "line-one\nline-two"}):
            with self.subTest(changed=changed):
                with self.assertRaises(importer.ImportErrorSafe):
                    importer.patch_fapshi(EXISTING, {**FAPSHI, **changed})

    def test_repair_prompts_privately_and_patches_latest_config_only(self):
        original = {**EXISTING, "FAPSHI_WEBHOOK_SECRET": "keep-this-webhook"}
        responses = [importer.ACCOUNT, json.dumps({"Parameter": {"Value": env_text(original)}})]
        with patch.object(importer.sys.stdin, "isatty", return_value=True), \
                patch.object(importer.getpass, "getpass",
                             side_effect=[FAPSHI["FAPSHI_API_USER"], FAPSHI["FAPSHI_API_KEY"], ""]), \
                patch.object(importer, "aws", side_effect=responses), \
                patch.object(importer, "write_secure_parameter") as write, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(importer.repair_fapshi(environment="LIVE", apply=True), 0)
        payload = write.call_args.args[0]
        for key, value in original.items():
            self.assertEqual(payload[key], value)
        self.assertEqual(payload["FAPSHI_ENV"], "LIVE")
        self.assertNotIn(FAPSHI["FAPSHI_API_KEY"], output.getvalue())
        self.assertEqual(write.call_args.kwargs, {"overwrite": True})

    def test_repair_preview_performs_no_io(self):
        with patch.object(importer, "aws") as aws, \
                patch.object(importer.getpass, "getpass") as prompt, \
                patch.object(importer, "write_secure_parameter") as write, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(importer.repair_fapshi(environment="LIVE", apply=False), 0)
        aws.assert_not_called()
        prompt.assert_not_called()
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
