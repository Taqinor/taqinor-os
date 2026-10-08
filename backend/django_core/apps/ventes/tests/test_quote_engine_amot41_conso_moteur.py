"""AMOT41 (C-AMOT-051) — la couverture industrielle imprime la consommation de
référence du MOTEUR C&I (``synthese_ci.baseline.kwh_an`` : Σ des 12 mois
résolus du bilan), jamais la saisie d'écran ``etude.conso_annuelle``.

Sonde VC ci1 : moteur à 12 × 20 000 kWh, ``etude_params['conso_annuelle'] =
1`` ⇒ la page imprimait « Consommation ≈ 1 kWh/an · Production estimée ≈
79 482 kWh/an ». Sans baseline moteur, la ligne est OMISE (une seule
consommation par page). Rendu HTML RÉEL du gabarit (aucun mock du moteur).
"""
import copy
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"
ETUDE_CI = json.loads((_CONTRATS / "etude_ci_preview.json").read_text(
    encoding="utf-8"))

_CONSO = re.compile(r"Consommation ≈ ([0-9][0-9\s  .,&#;a-z]*) kWh/an")


def _data(*, douze_mois=True):
    data = copy.deepcopy(i_sample.build())
    etude_ci = copy.deepcopy(ETUDE_CI["exemple"])
    if douze_mois:
        for m in etude_ci["bilan"]["par_mois"]:
            m["consommation_kwh"] = 20000
    else:
        etude_ci["bilan"]["par_mois"] = etude_ci["bilan"]["par_mois"][:11]
    # La saisie d'écran contradictoire de la sonde : JAMAIS imprimée.
    data["etude"] = dict(data.get("etude") or {}, etude_ci=etude_ci,
                         conso_annuelle=1)
    data["conso_annuelle_kwh"] = 1
    return data


def _chiffre(texte):
    return int(re.sub(r"\D", "", re.sub(r"&#\d+;", "", texte)))


class ConsoMoteurTests(SimpleTestCase):

    def test_baseline_porte_la_somme_des_douze_mois(self):
        s = synthese_ci(_data())
        self.assertEqual(s["baseline"]["kwh_an"], 240000)
        self.assertEqual(chiffres_cles(s)["conso_kwh_an"], 240000)

    def test_couverture_imprime_la_conso_du_moteur(self):
        html = i_render.build_html(i_renderer._augment(_data()))
        trouvees = _CONSO.findall(html)
        self.assertEqual(len(trouvees), 1, trouvees)
        self.assertEqual(_chiffre(trouvees[0]), 240000)

    def test_saisie_ecran_jamais_imprimee(self):
        html = i_render.build_html(i_renderer._augment(_data()))
        self.assertNotIn("Consommation ≈ 1 kWh/an", html)

    def test_sans_douze_mois_moteur_ligne_omise(self):
        data = _data(douze_mois=False)
        self.assertNotIn("kwh_an", synthese_ci(data).get("baseline") or {})
        html = i_render.build_html(i_renderer._augment(data))
        self.assertEqual(_CONSO.findall(html), [])
        self.assertNotIn("Consommation à confirmer", html)
