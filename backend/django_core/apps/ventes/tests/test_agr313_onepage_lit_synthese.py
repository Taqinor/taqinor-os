"""AGR313 — le une-page agricole (version courte) lit ``synthese_agricole`` :
mêmes chiffres que le 3 pages et que la page en ligne, une carte « besoin /
livré » seulement quand la synthèse la sert, et un « Bon pour accord »
compact.

HTML réel du moteur legacy (``render_html_for``, fixture ``_moteur_fixtures``)
sans base ; le compte d'UNE page est prouvé sur un rendu WeasyPrint réel
(non tagué : il tourne à chaque CI) avec 12 lignes.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
from apps.ventes.tests import _moteur_fixtures as F

ETUDE = {
    'mode_pompe': 'neuve',
    'pompe_cv': 10.2, 'pompe_kw': 7.5, 'hmt_m': 58.7,
    'debit_hmt_m3h': 30.5, 'm3_jour': 134.2, 'heures_pompage': 4.4,
    'champ_kwc': 9.94,
}
BESOIN = {
    'besoin_mensuel': {'m3_jour_mois': [135] * 12, 'nature': 'declare',
                       'source_et0': None},
    'production': {'m3_jour_mois': [140.3, 161.7, 186.0, 207.4, 219.6,
                                    225.7, 228.8, 222.7, 201.3, 173.8,
                                    146.4, 134.2],
                   'source_irradiation': 'pvgis', 'mode': 'courbe'},
    'conception': {'mois_critique': 12},
}


def _data(etude=None, **surcharges):
    return F.donnees_legacy('deux', pdf_mode='onepage',
                            mode_installation='agricole',
                            etude=dict(etude or ETUDE), **surcharges)


def _html(data):
    return G.render_html_for(data)


class Agr313MemesChiffresQueLaSyntheseTests(SimpleTestCase):

    def test_pompe_hmt_debit_eau_egaux_a_la_synthese(self):
        data = _data()
        s = synthese_agricole(data)
        html = _html(data)
        self.assertIn(f"{G._fdec_fr(s['pompe']['cv'])} CV "
                      f"({G._fdec_fr(s['pompe']['kw'])} kW)", html)
        self.assertIn(f"{G._fdec_fr(s['eau']['hmt_m'])} m<", html)
        self.assertIn(f"{G._fdec_fr(s['eau']['debit_hmt_m3h'], 1)} m&#179;/h",
                      html)
        self.assertIn(f"&#8776; {G.fnum(s['eau']['m3_jour'])} m&#179;", html)
        self.assertIn('10,2 CV (7,5 kW)', html)
        self.assertIn('58,7 m<', html)

    def test_carte_besoin_presente_seulement_si_servie(self):
        sans = _html(_data())
        self.assertNotIn('Mois le plus serr&#233;', sans)
        data = _data(etude={**ETUDE, **BESOIN})
        self.assertIn('besoin_vs_livre', synthese_agricole(data))
        avec = _html(data)
        self.assertIn('Mois le plus serr&#233; : besoin / livr&#233;', avec)
        self.assertIn('135 / 134 m&#179;', avec)

    def test_estimation_suit_la_synthese(self):
        # Production sur courbe + PVGIS : le volume n'est plus une estimation.
        html = _html(_data(etude={**ETUDE, **BESOIN}))
        self.assertIn('Eau / jour &#8212; sur 4,4 h de pompage', html)
        html = _html(_data())
        self.assertIn('Eau / jour &#8212; estimation, sur 4,4 h', html)

    def test_bon_pour_accord_compact(self):
        html = _html(_data())
        self.assertIn('Bon pour accord &#8212; signature du client', html)
        self.assertIn('Date&#160;:', html)

    def test_residentiel_inchange_sans_bon_pour_accord(self):
        html = F.html_onepage()
        self.assertNotIn('Bon pour accord', html)
        self.assertNotIn('Mois le plus serr', html)


# Volontairement SANS ``@tag('pdf')`` (la CI passe ``--exclude-tag=pdf``) :
# le compte d'UNE page doit tourner à chaque run — un seul rendu, rapide.
class Agr313PdfReelTests(SimpleTestCase):

    def test_douze_lignes_tiennent_sur_une_page(self):
        from weasyprint import HTML
        data = _data()
        base = dict(data['all_items'][0])
        data['all_items'] = [
            {**base, 'designation': f'Accessoire de pompage n°{i}'}
            for i in range(12)]
        html = _html(data)
        self.assertEqual(len(HTML(string=html).render().pages), 1)
        self.assertIn('Bon pour accord', html)
