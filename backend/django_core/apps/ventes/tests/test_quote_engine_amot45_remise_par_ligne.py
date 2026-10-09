"""AMOT45 (C-AMOT-057) — la remise GLOBALE est portée ligne par ligne (QJRREM)
dans le tableau de l'AGRICOLE et dans la page équipements COMMERCIALE /
INDUSTRIELLE, par le helper unique ``montants.lignes_remisees`` (extrait du
résidentiel) : P.U. catalogue barré + P.U. remisé, et Σ des totaux de ligne
remisés = Total HT. La chaîne Sous-total → Remise → Total HT est inchangée.
Devis aux règles d'origine (``regles_calcul_origine``) : l'affichage d'hier.

Rejoue la sonde VC agr4 : remise 5 %, ``prix_unit_ht 20000.0`` →
``pu_ht_remise 19000.0``.

Test-du-test : remettre ``pu = _num(it.get("prix_unit_ht"))`` dans
``agricole/pages._lignes`` ⇒ ``test_agricole`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_quote_engine_amot45_remise_par_ligne"
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import montants
from apps.ventes.quote_engine.agricole import pages as agricole_pages
from apps.ventes.quote_engine.commercial import render as commercial_render
from apps.ventes.quote_engine.commercial import sample_data as commercial_sample
from apps.ventes.quote_engine.industriel import render as industriel_render
from apps.ventes.quote_engine.industriel import sample_data as industriel_sample
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete

REMISE = 0.05


def _remiser(items):
    """Annote les items comme le builder (``_annoter_remise``) : P.U. et total
    remisés au centime, Σ totaux remisés renvoyée."""
    total_net = 0.0
    for it in items:
        pu = float(it['prix_unit_ht'])
        q = float(it['quantite'])
        it['pu_ht_remise'] = round(pu * (1 - REMISE), 2)
        it['total_ht_remise'] = round(it['pu_ht_remise'] * q, 2)
        total_net += it['total_ht_remise']
    return round(total_net, 2)


def _nombre(texte):
    """« 19 000,00 » (espaces fines comprises) → 19000.0 ; dernier nombre non barré."""
    texte = re.sub(r'<s[^>]*>.*?</s>', '', texte)
    texte = re.sub(r'<[^>]+>', '', texte)
    m = re.findall(r'-?\d[\d\s  ]*,\d{2}', texte)
    return float(m[-1].replace(' ', '').replace(' ', '').replace(' ', '').replace(',', '.'))


class RemiseParLigneTests(SimpleTestCase):

    def test_helper_unique(self):
        it = {'prix_unit_ht': 20000.0, 'quantite': 1, 'pu_ht_remise': 19000.0, 'total_ht_remise': 19000.0}
        (ligne,) = montants.lignes_remisees([it])
        self.assertEqual((ligne['pu_catalogue'], ligne['pu'], ligne['total']), (20000.0, 19000.0, 19000.0))
        (origine,) = montants.lignes_remisees([it], catalogue_seul=True)
        self.assertEqual(origine['pu'], 20000.0)
        self.assertEqual(montants.deux_prix(montants.fmt_centimes, 20000.0, 20000.0),
                         montants.fmt_centimes(20000.0))

    def test_agricole(self):
        d = data_complete()
        items = [it for it in d['all_items'] if float(it.get('quantite') or 0) > 0]
        ht_net = _remiser(items)
        html = agricole_pages._lignes(d)
        self.assertIn('<s>', html)
        lignes = re.findall(r'<tr>(.*?)</tr>', html)
        totaux = [_nombre(re.findall(r'<td[^>]*>(.*?)</td>', ligne)[-1]) for ligne in lignes]
        self.assertAlmostEqual(sum(totaux), ht_net, places=2)
        pompe = items[0]
        self.assertIn(montants.fmt_centimes(pompe['pu_ht_remise']), html)

    def test_agricole_regles_origine_inchange(self):
        d = data_complete()
        _remiser([it for it in d['all_items'] if float(it.get('quantite') or 0) > 0])
        d['regles_calcul_origine'] = True
        self.assertNotIn('<s>', agricole_pages._lignes(d))

    def _equip(self, render, data):
        ht_net = _remiser(data['all_items'])
        html = render.build_html(data)
        cellules = re.findall(r'<td class="c2-t">(.*?)</td>', html)
        self.assertTrue(cellules)
        self.assertIn('<s>', ''.join(cellules))
        self.assertAlmostEqual(sum(_nombre(c) for c in cellules), ht_net, delta=0.05)

    def test_commercial(self):
        self._equip(commercial_render, commercial_sample.build())

    def test_industriel(self):
        self._equip(industriel_render, industriel_sample.build())
