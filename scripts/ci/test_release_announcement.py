"""Non-régression de l'annonce WhatsApp de release, sans réseau ni secret réel."""
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_announcement as ra  # noqa: E402
import waha_notify  # noqa: E402

PAYLOAD = {
    "version": "1.9.0",
    "date_version": "2026-11-18",
    "elements": [
        {"id": "a", "date": "2026-11-18", "importance": 2, "titre": "Glossaires *partagés*",
         "resume": "Une   équipe,\nun glossaire."},
        {"id": "b", "date": "2026-11-18", "importance": 1, "titre": "Export Word", "resume": "Fidèle."},
        {"id": "c", "date": "2026-11-15", "importance": 1, "titre": "Plus ancien", "resume": "Avant."},
        {"id": "d", "date": "2026-11-09", "importance": 1, "titre": "Version précédente", "resume": "x"},
    ],
}
ENV = {"NOTIFY_SESSION": "trigenys-test", "NOTIFY_CHAT_ID": "123@g.us", "NOTIFY_API_KEY": "s3cr3t-key"}


class FakeMarker(ra.CommitStatusMarker):
    def __init__(self, initial=None):
        super().__init__("o/r", "abc123", "tok", request=self._fake)
        self.statuses = [] if initial is None else [{"context": ra.ANNOUNCE_CONTEXT, "state": initial}]
        self.writes = []

    def _fake(self, method, path, body=None):
        if method == "GET":
            return list(self.statuses)
        self.writes.append(body["state"])
        self.statuses.insert(0, {"context": body["context"], "state": body["state"]})
        return {}


def run(marker=None, env=ENV, dry_run=False, payload=PAYLOAD, tag="v1.9.0", send=None):
    sent = []

    def fake_send(config, text):
        sent.append((config, text))
        return 201

    outcome = ra.announce(tag=tag, origin="https://precis.example", since=None, max_items=8,
                          dry_run=dry_run, marker=marker, env=env, fetch=lambda url: payload,
                          sleep=lambda s: None, send=send or fake_send, out=lambda t: None)
    return outcome, sent


class MessageTests(unittest.TestCase):
    def test_version_from_tag(self):
        self.assertEqual(ra.version_from_tag("v1.9.0"), "1.9.0")
        self.assertEqual(ra.version_from_tag("1.10.2"), "1.10.2")
        with self.assertRaises(ra.AnnounceError):
            ra.version_from_tag("latest")

    def test_selects_only_this_version_by_importance(self):
        ids = [e["id"] for e in ra.select_elements(PAYLOAD)]
        self.assertEqual(ids, ["b", "a"])

    def test_since_widens_selection(self):
        ids = [e["id"] for e in ra.select_elements(PAYLOAD, since="2026-11-09")]
        self.assertEqual(ids, ["b", "c", "a"])

    def test_message_format(self):
        message = ra.build_message("1.9.0", ra.select_elements(PAYLOAD), "https://precis.example/")
        self.assertEqual(message, "\n".join([
            "✅ *Précis Translator 1.9.0 est en ligne*",
            "",
            "• *Export Word* — Fidèle.",
            "• *Glossaires partagés* — Une équipe, un glossaire.",
            "",
            "👉 https://precis.example",
        ]))

    def test_message_caps_items(self):
        elements = [{"titre": f"T{i}", "resume": ""} for i in range(5)]
        message = ra.build_message("2.0.0", elements, max_items=3)
        self.assertIn("• *T2*", message)
        self.assertNotIn("T3", message)
        self.assertIn("… et 2 autres nouveautés", message)

    def test_message_without_elements_keeps_link(self):
        self.assertEqual(ra.build_message("2.0.0", [], "https://p.example"),
                         "✅ *Précis Translator 2.0.0 est en ligne*\n\n👉 https://p.example")


class AnnounceTests(unittest.TestCase):
    def test_version_mismatch_fails_without_sending(self):
        marker = FakeMarker()
        with self.assertRaisesRegex(ra.AnnounceError, "1.9.0 au lieu de 2.0.0"):
            run(marker, tag="v2.0.0")
        self.assertEqual(marker.writes, [])

    def test_retries_until_version_is_served(self):
        calls = iter([{"version": "1.8.0"}, PAYLOAD])
        payload = ra.fetch_served_release("https://p", "1.9.0", fetch=lambda u: next(calls),
                                          sleep=lambda s: None)
        self.assertEqual(payload["version"], "1.9.0")

    def test_unreachable_production_fails(self):
        def boom(url):
            raise urllib.error.URLError("down")
        with self.assertRaisesRegex(ra.AnnounceError, "illisible"):
            ra.fetch_served_release("https://p", "1.9.0", attempts=2, fetch=boom, sleep=lambda s: None)

    def test_dry_run_sends_and_writes_nothing(self):
        marker = FakeMarker()
        outcome, sent = run(marker, dry_run=True)
        self.assertEqual((outcome, sent, marker.writes), ("dry-run", [], []))

    def test_unconfigured_is_noop(self):
        marker = FakeMarker()
        outcome, sent = run(marker, env={})
        self.assertEqual((outcome, sent, marker.writes), ("disabled", [], []))

    def test_half_configured_fails(self):
        with self.assertRaisesRegex(ra.AnnounceError, "NOTIFY_API_KEY"):
            run(FakeMarker(), env={"NOTIFY_SESSION": "s", "NOTIFY_CHAT_ID": "c"})

    def test_sends_once_then_rerun_is_noop(self):
        marker = FakeMarker()
        outcome, sent = run(marker)
        self.assertEqual(outcome, "sent")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0].chat_id, "123@g.us")
        self.assertEqual(marker.writes, ["pending", "success"])
        outcome, sent = run(marker)
        self.assertEqual((outcome, sent), ("already-sent", []))
        self.assertEqual(marker.writes, ["pending", "success"])

    def test_interrupted_send_blocks_resend(self):
        with self.assertRaisesRegex(ra.AnnounceError, "pending"):
            run(FakeMarker("pending"))

    def test_failed_send_marks_failure_and_retry_sends(self):
        marker = FakeMarker()

        def refuse(config, text):
            raise waha_notify.NotifyError("envoi WAHA refusé : HTTP 401")
        with self.assertRaisesRegex(ra.AnnounceError, "HTTP 401"):
            run(marker, send=refuse)
        self.assertEqual(marker.writes, ["pending", "failure"])
        outcome, sent = run(marker)
        self.assertEqual((outcome, len(sent)), ("sent", 1))

    def test_missing_marker_refuses_to_send(self):
        with self.assertRaisesRegex(ra.AnnounceError, "idempotence"):
            run(None)


class WahaNotifyTests(unittest.TestCase):
    def test_config_absent_is_disabled(self):
        self.assertIsNone(waha_notify.config_from_env({}))

    def test_config_requires_https(self):
        with self.assertRaises(waha_notify.NotifyError):
            waha_notify.config_from_env({**ENV, "NOTIFY_BASE_URL": "http://x"})

    def test_repr_hides_key(self):
        self.assertNotIn("s3cr3t-key", repr(waha_notify.config_from_env(ENV)))

    def test_send_text_request_shape(self):
        captured = {}

        class Response(io.BytesIO):
            status = 201

        def opener(request, timeout):
            captured["request"] = request
            return Response(b"{}")
        config = waha_notify.config_from_env({**ENV, "NOTIFY_BASE_URL": "https://notify.example/"})
        self.assertEqual(waha_notify.send_text(config, "Bonjour ✅", opener=opener), 201)
        request = captured["request"]
        self.assertEqual(request.full_url, "https://notify.example/api/sendText")
        self.assertEqual(request.get_header("X-api-key"), "s3cr3t-key")
        self.assertEqual(json.loads(request.data), {"session": "trigenys-test", "chatId": "123@g.us",
                                                    "text": "Bonjour ✅"})

    def test_http_error_message_has_no_key(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
        with self.assertRaises(waha_notify.NotifyError) as ctx:
            waha_notify.send_text(waha_notify.config_from_env(ENV), "x", opener=opener)
        self.assertIn("HTTP 401", str(ctx.exception))
        self.assertNotIn("s3cr3t-key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
