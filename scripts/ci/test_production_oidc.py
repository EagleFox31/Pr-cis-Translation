import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("production_oidc", Path(__file__).parents[1] / "ops/production_oidc.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def trust(subject):
    return {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Principal": {"Federated": f"arn:aws:iam::{module.ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"},
        "Condition": {"StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                       "token.actions.githubusercontent.com:sub": subject}}}]}


class ProductionTrustTests(unittest.TestCase):
    def test_subject_migrates_without_changing_original_or_permissions(self):
        for prefix in module.PREFIXES:
            original = trust(prefix + "staging")
            result = module.production_trust(original)
            self.assertEqual(result, trust(prefix + "production"))
            self.assertEqual(original, trust(prefix + "staging"))
            self.assertEqual(module.production_trust(result), result)

    def test_unrelated_or_broader_trust_is_refused(self):
        for subject in ["repo:other/repo:environment:staging", "*", module.PREFIXES[0] + "development"]:
            with self.assertRaises(ValueError): module.production_trust(trust(subject))
        document = trust(module.PREFIXES[0] + "staging")
        document["Statement"][0]["Principal"] = {"AWS": "*"}
        with self.assertRaises(ValueError): module.production_trust(document)


if __name__ == "__main__":
    unittest.main()
