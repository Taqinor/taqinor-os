"""Tests hors ligne de la sonde (VEIL40) : aucun appel reseau, aucun vrai jeton.

    python -m unittest discover -s tools/adlib_probe -p "test_probe.py"
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe as sonde  # noqa: E402

TOKEN = "EAAFAKETOKEN1234567890abcdef"
TRAP_URL = "https://www.facebook.com/ads/archive/render_ad/?id=1&access_token=" + TOKEN


def ads(n, trap=False):
    return [{"id": str(i), "page_id": "p%d" % i, "page_name": "Shop %d" % i,
             "ad_snapshot_url": TRAP_URL if trap else "https://x/?id=%d" % i} for i in range(n)]


def ok(n=3, trap=False, usage=None, nxt=False):
    headers = {"X-App-Usage": json.dumps(usage)} if usage else {}
    body = {"data": ads(n, trap)}
    if nxt:
        body["paging"] = {"next": "https://graph/next?access_token=" + TOKEN, "cursors": {"after": "CUR"}}
    return sonde.Response(200, headers, body)


def err(code, sub=None, msg="boom"):
    return sonde.Response(400, {}, {"error": {"code": code, "error_subcode": sub, "type": "OAuthException",
                                              "message": msg + " " + TOKEN}})


class Script:
    """Transport scripte : renvoie les reponses dans l'ordre et memorise les appels."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params, headers):
        self.calls.append((url, dict(params), dict(headers)))
        if not self.responses:
            raise sonde.ProbeStop("script epuise")
        return self.responses.pop(0)


class ProbeCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(self.path) and os.remove(self.path))
        self.sleeps = []

    def probe(self, responses, max_calls=150):
        self.transport = Script(responses)
        return sonde.Probe(TOKEN, self.transport, self.path, max_calls=max_calls,
                           sleep=self.sleeps.append, pause_s=0, clock=lambda: 1)

    def journal(self):
        with open(self.path, encoding="utf-8") as fh:
            return fh.read()

    def test_journal_sans_secret_sur_fixtures_piegees(self):
        p = self.probe([ok(3, trap=True), err(100, msg="token " + TRAP_URL)])
        p.search("E7", "FR", "sandals", limit=25)
        p.search("E7", "FR", "sandals", limit=25)
        text = self.journal()
        self.assertTrue(text)
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("EAA", text)
        self.assertNotIn("access_token", text.lower())

    def test_e7_booleen_sans_url(self):
        p = self.probe([ok(3, trap=True)])
        sonde.e7(p, mots="sandals")
        text = self.journal()
        self.assertIn('"jeton_dans_snapshot": true', text)
        self.assertNotIn("render_ad", text)

    def test_613_attend_sans_nouvel_appel_puis_arret(self):
        p = self.probe([err(613), ok()])
        with self.assertRaises(sonde.ProbeStop):
            p.search("E1", "FR", "x")
        self.assertEqual(self.sleeps, [1800])
        self.assertEqual(len(self.transport.calls), 1)
        with self.assertRaises(sonde.ProbeStop):
            sonde.e1(self.probe([err(613), ok()]), mots="x")

    def test_attentes_par_code(self):
        for code, wait in ((4, 300), (17, 600), (32, 1200), (613, 1800)):
            self.sleeps.clear()
            p = self.probe([err(code)])
            with self.assertRaises(sonde.ProbeStop):
                p.search("E1", "FR", "x")
            self.assertEqual(self.sleeps, [wait])

    def test_code_10_et_190_arretent_avec_diagnostic(self):
        for code in (10, 190):
            self.sleeps.clear()
            p = self.probe([err(code, sub=2332002), ok()])
            with self.assertRaises(sonde.ProbeStop) as cm:
                p.search("E1", "FR", "x")
            self.assertEqual(cm.exception.diagnostic["code"], code)
            self.assertEqual(cm.exception.diagnostic["sous_code"], 2332002)
            self.assertEqual(self.sleeps, [])
            self.assertEqual(len(self.transport.calls), 1)
            self.assertIn("2332002", self.journal())

    def test_budget_max_calls_jamais_depasse(self):
        p = self.probe([ok() for _ in range(10)], max_calls=3)
        result = sonde.run(p, "sandals")
        self.assertEqual(len(self.transport.calls), 3)
        self.assertIn("budget", result)

    def test_plafond_dur_150(self):
        with self.assertRaises(ValueError):
            sonde.Probe(TOKEN, Script([]), self.path, max_calls=151)

    def test_usage_75_pour_cent_pause_avant_appel_suivant(self):
        p = self.probe([ok(usage={"call_count": 80, "total_time": 10, "total_cputime": 5}), ok()])
        p.search("E1", "FR", "x")
        self.assertEqual(self.sleeps, [])
        p.search("E1", "FR", "x")
        self.assertEqual(self.sleeps, [300])

    def test_usage_sous_seuil_pas_de_pause(self):
        p = self.probe([ok(usage={"call_count": 74}), ok()])
        p.search("E1", "FR", "x")
        p.search("E1", "FR", "x")
        self.assertEqual(self.sleeps, [])

    def test_jeton_en_parametre_par_defaut_en_entete_pour_e8(self):
        p = self.probe([ok(), ok()])
        p.search("E1", "FR", "x")
        p.search("E8", "FR", "x", use_header=True)
        self.assertEqual(self.transport.calls[0][1]["access_token"], TOKEN)
        self.assertNotIn("access_token", self.transport.calls[1][1])
        self.assertEqual(self.transport.calls[1][2]["Authorization"], "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, self.journal())

    def test_e5_suit_le_curseur_sans_le_journaliser(self):
        p = self.probe([ok(2, nxt=True), ok(2, nxt=True), ok(1)])
        sonde.e5(p, mots="x")
        self.assertEqual(self.transport.calls[1][1]["after"], "CUR")
        text = self.journal()
        self.assertNotIn("CUR", text)
        self.assertIn('"n_par_page": [2, 2, 1]', text)

    def test_rejeu_cli_sans_reseau_ni_jeton(self):
        fd, rec = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(os.remove, rec)
        with open(rec, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"status": 200, "headers": {}, "body": {"data": [{"id": "1"}]}}) + "\n")
            fh.write(json.dumps({"status": 400, "headers": {},
                                 "body": {"error": {"code": 10, "message": "perm " + TOKEN}}}) + "\n")
        rc = sonde.main(["--rejouer", rec, "--journal", self.path, "--only", "E1"])
        self.assertEqual(rc, 0)
        text = self.journal()
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("EAA", text)
        self.assertIn('"code": 10', text)
        self.assertIn("arret", text)

    def test_scrub_recursif(self):
        out = sonde.scrub({"access_token": TOKEN, "a": ["x?access_token=" + TOKEN, {"b": "Bearer " + TOKEN}]})
        self.assertNotIn(TOKEN, json.dumps(out))


if __name__ == "__main__":
    unittest.main()
