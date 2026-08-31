"""Tests de scripts/check_lead_webhook_parite.py (QJR230).

Stdlib pur (unittest), aucune base de donnees, aucun Django, aucun node.
Lancer :
    python -m unittest scripts.tests.test_check_lead_webhook_parite -v

Les tests qui comptent sont les NEGATIFS EXECUTES : une cle ajoutee au contrat
et non traitee par `_map_payload_to_fields` doit rougir, et une cle declaree
refusee mais lue quand meme doit rougir aussi. Une garde de parite qu'on n'a
jamais vue rougir ne prouve rien.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_lead_webhook_parite as parite  # noqa: E402


# --- une reduction FIDELE de apps/crm/webhooks.py (memes formes AST) -------
SOURCE = '''
def _extract_web_questionnaire(data):
    out = {}

    def _num(camel, snake, lo=0, hi=None):
        val = _clean_decimal(data.get(camel, data.get(snake)), lo=lo, hi=hi)
        if val is not None:
            out[snake] = val

    def _choice(camel, snake, values):
        val = _clean_choice(data.get(camel, data.get(snake)), values)
        if val is not None:
            out[snake] = val

    def _bool(camel, snake):
        val = data.get(camel, data.get(snake))
        if isinstance(val, bool):
            out[snake] = val

    _num('surfaceM2', 'surface_m2', hi=1000000)
    _choice('waterSource', 'water_source', ('puits', 'forage'))
    _bool('ombriere', 'ombriere')
    return out


def _map_payload_to_fields(data):
    utm = data.get('utm') or {}
    fields = {
        'nom': str(data.get('fullName') or '').strip(),
        'ville': str(data.get('city')).strip() if data.get('city') else None,
    }
    if 'whatsappOptIn' in data:
        fields['whatsapp_opt_in'] = bool(data['whatsappOptIn'])
    for key in ('utm_source', 'utm_medium'):
        value = utm.get(key) or data.get(key)
        fields[key] = value
    questionnaire = _extract_web_questionnaire(data)
    for equip_key in ('equip_clim', 'equip_piscine'):
        val = questionnaire.pop(equip_key, None)
        if val is not None:
            fields[equip_key] = val
    return fields


def website_lead_webhook(request):
    data = request.data
    jeton = str(data.get('idempotencyKey') or '')
    return jeton
'''


def _entree(destination, champ=None, blob=None):
    entree = {"destination": destination, "champ_lead": champ}
    if blob:
        entree["cle_blob"] = blob
    return entree


CONTRAT_VERT = {"cles": {
    "fullName": _entree(parite.COLONNE, "nom"),
    "city": _entree(parite.COLONNE, "ville"),
    "whatsappOptIn": _entree(parite.COLONNE, "whatsapp_opt_in"),
    "utm_source": _entree(parite.COLONNE, "utm_source"),
    "surfaceM2": _entree(parite.BLOB, "web_questionnaire", blob="surface_m2"),
    "waterSource": _entree(parite.BLOB, "web_questionnaire", blob="water_source"),
    "ombriere": _entree(parite.BLOB, "web_questionnaire", blob="ombriere"),
    "idempotencyKey": _entree(parite.VUE),
    "consent": _entree(parite.REFUS),
}}


def contrat(**surcharges):
    document = copy.deepcopy(CONTRAT_VERT)
    for cle, entree in surcharges.items():
        if entree is None:
            document["cles"].pop(cle, None)
        else:
            document["cles"][cle] = entree
    return document


class LectureAstTests(unittest.TestCase):
    """Ce que la garde considere comme « une cle du payload lue »."""

    def setUp(self):
        self.mapping, self.module, self.absentes = parite.lectures(SOURCE)

    def test_les_quatre_formes_de_lecture_sont_vues(self):
        # `data.get('X')`, `'X' in data`, `data['X']`, et les aides
        # `_num`/`_choice`/`_bool` (leurs DEUX premiers arguments).
        for cle in ("fullName", "city", "whatsappOptIn", "surfaceM2",
                    "surface_m2", "waterSource", "water_source", "ombriere"):
            self.assertIn(cle, self.mapping, cle)

    def test_la_boucle_utm_est_vue(self):
        # `for key in ('utm_source', 'utm_medium'): … data.get(key)`
        self.assertIn("utm_source", self.mapping)
        self.assertIn("utm_medium", self.mapping)

    def test_negatif_une_boucle_qui_POP_un_blob_n_est_PAS_une_lecture(self):
        # `questionnaire.pop(equip_key)` lit le BLOB deja construit, pas le
        # payload. Confondre les deux rendrait la garde aveugle a une vraie
        # perte de cle (elle croirait la cle lue).
        self.assertNotIn("equip_piscine", self.mapping)

    def test_la_vue_est_lue_au_niveau_du_MODULE_pas_du_mapping(self):
        self.assertNotIn("idempotencyKey", self.mapping)
        self.assertIn("idempotencyKey", self.module)

    def test_aucune_fonction_de_mapping_manquante(self):
        self.assertEqual(self.absentes, [])


class PariteTests(unittest.TestCase):
    """Les rouges. Chacun est EXECUTE, pas decrit."""

    def _cles(self, document):
        return [cle for cle, _ in parite.constats(document, SOURCE)]

    def test_le_contrat_conforme_ne_produit_rien(self):
        self.assertEqual(parite.constats(contrat(), SOURCE), [])

    def test_une_cle_AJOUTEE_au_contrat_et_non_traitee_ROUGIT(self):
        # LE point de QJR230 : une question de plus dans le tunnel, personne
        # ne la cable, et elle se perdait sans trace a l'arrivee.
        document = contrat(
            regionAgricole=_entree(parite.BLOB, "web_questionnaire",
                                   blob="region_agricole"))
        constats = parite.constats(document, SOURCE)
        self.assertEqual([c[0] for c in constats], ["regionAgricole"])
        self.assertIn("ne la lit NULLE PART", constats[0][1])
        self.assertIn("se perd sans trace", constats[0][1])

    def test_l_INVERSE_une_cle_declaree_REFUSEE_mais_lue_ROUGIT(self):
        # Un refus qui n'est plus tenu est aussi grave que la perte : le
        # contrat mentirait dans l'autre sens.
        document = contrat(city=_entree(parite.REFUS))
        constats = parite.constats(document, SOURCE)
        self.assertEqual([c[0] for c in constats], ["city"])
        self.assertIn("le refus n'est plus tenu", constats[0][1])

    def test_une_cle_VUE_lue_par_le_mapping_rougit(self):
        document = contrat(fullName=_entree(parite.VUE))
        constats = parite.constats(document, SOURCE)
        self.assertEqual([c[0] for c in constats], ["fullName"])
        self.assertIn("declarer `colonne_lead`", constats[0][1])

    def test_une_cle_VUE_que_PLUS_PERSONNE_ne_lit_rougit(self):
        # Une declaration qui ne verifie plus rien doit s'eteindre BRUYAMMENT.
        document = contrat(eventId=_entree(parite.VUE))
        constats = parite.constats(document, SOURCE)
        self.assertEqual([c[0] for c in constats], ["eventId"])
        self.assertIn("AUCUNE", constats[0][1])

    def test_une_cle_REFUSEE_et_jamais_lue_reste_verte(self):
        self.assertEqual(parite.constats(contrat(), SOURCE), [])

    def test_une_destination_inconnue_rougit(self):
        document = contrat(city={"destination": "peut_etre", "champ_lead": None})
        constats = parite.constats(document, SOURCE)
        self.assertEqual([c[0] for c in constats], ["city"])
        self.assertIn("destination inconnue", constats[0][1])

    def test_une_colonne_sans_champ_lead_rougit(self):
        document = contrat(city=_entree(parite.COLONNE))
        motifs = [motif for cle, motif in parite.constats(document, SOURCE)
                  if cle == "city"]
        self.assertTrue(any("sans `champ_lead`" in m for m in motifs), motifs)

    def test_un_blob_sans_cle_blob_rougit(self):
        document = contrat(surfaceM2=_entree(parite.BLOB, "web_questionnaire"))
        motifs = [motif for cle, motif in parite.constats(document, SOURCE)
                  if cle == "surfaceM2"]
        self.assertTrue(any("sans `cle_blob`" in m for m in motifs), motifs)

    def test_un_refus_qui_NOMME_un_champ_rougit(self):
        document = contrat(consent=_entree(parite.REFUS, "consent_timestamp"))
        motifs = [motif for cle, motif in parite.constats(document, SOURCE)
                  if cle == "consent"]
        self.assertTrue(any("n'atterrit dans aucune colonne" in m
                            for m in motifs), motifs)

    def test_la_disparition_de_la_fonction_de_mapping_rougit(self):
        # Un renommage silencieux de `_map_payload_to_fields` eteindrait la
        # garde : elle doit hurler, pas se taire.
        source = SOURCE.replace("def _map_payload_to_fields(data):",
                                "def _mapper_le_payload(data):")
        constats = parite.constats(contrat(), source)
        self.assertEqual([c[0] for c in constats], ["<_map_payload_to_fields>"])
        self.assertIn("FONCTIONS_MAPPING", constats[0][1])

    def test_un_contrat_sans_table_cles_rougit(self):
        constats = parite.constats({"exemple": {}}, SOURCE)
        self.assertEqual([c[0] for c in constats], ["<contrat>"])


class DepotReelTests(unittest.TestCase):
    """La garde sur le VRAI contrat et le VRAI webhook."""

    def setUp(self):
        self.contrat = parite.charger(parite.CONTRAT)
        self.source = parite.WEBHOOKS.read_text(encoding="utf-8")

    def test_le_depot_reel_est_VERT(self):
        self.assertEqual(parite.constats(self.contrat, self.source), [])

    def test_les_69_cles_du_registre_sont_toutes_declarees(self):
        cles = self.contrat["cles"]
        self.assertEqual(len(cles), 69)
        for cle, entree in cles.items():
            self.assertIn(entree["destination"], parite.DESTINATIONS, cle)

    def test_chaque_cle_NON_traitee_porte_une_raison_ECRITE(self):
        # « une exclusion volontaire s'ecrit dans le contrat avec sa raison,
        # jamais par omission ».
        for cle, entree in self.contrat["cles"].items():
            if entree["destination"] in (parite.REFUS, parite.VUE):
                self.assertTrue(len(entree.get("note") or "") > 40,
                                f"{cle} : refus sans raison ecrite")

    def test_main_rend_0_sur_le_depot_reel(self):
        self.assertEqual(parite.main([]), 0)

    def test_le_contrat_cite_bien_la_garde(self):
        # Les deux moities se NOMMENT l'une l'autre : sans ca, la prochaine
        # lane ne saura pas ou vit la parite.
        texte = json.dumps(self.contrat, ensure_ascii=False)
        self.assertIn("check_lead_webhook_parite.py", texte)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
