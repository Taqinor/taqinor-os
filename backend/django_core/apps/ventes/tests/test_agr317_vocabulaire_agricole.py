"""AGR317 — garde de vocabulaire du devis agricole.

Jamais « eau gratuite », « à vie », « illimité », « coût nul », « 0 MAD de
carburant » (et leurs équivalents EN/AR) : la pompe se remplace au bout de 7
à 10 ans (Banque mondiale 2018). Jamais non plus une promesse d'ÉCONOMIE
D'EAU (« économise l'eau », « moins d'eau gaspillée ») : le goutte-à-goutte
ne réduit pas la consommation d'eau à la ferme (Banque mondiale ; GIZ/AGIRE
2019 mesure une HAUSSE chez 31 % à 60 % des agriculteurs passés au solaire).

La garde rend le document de 3 pages et le une-page agricoles en fr/en/ar,
et parcourt les textes de ``agricole/mentions.py``, la condition des
économies et les libellés ``agr_*`` du catalogue. Elle ne vise QUE le devis
agricole (jamais « étude gratuite » ailleurs sur le site). Une fixture qui
injecte « eau gratuite » dans un libellé prouve qu'elle mord.
"""
import re
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.quote_engine import i18n_labels as L
from apps.ventes.quote_engine.agricole import mentions, pages, renderer
from apps.ventes.quote_engine.agricole.synthese import CONDITION_ECONOMIES
from apps.ventes.tests import _moteur_fixtures as F
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, data_minimale,
)

#: Formulations ÉCONOMIQUES interdites (fr / en / ar).
INTERDITS_ECONOMIQUES = (
    r"eau\s+gratuite", r"gratuit[e]?\s+à\s+vie", r"(?<![\w-])à\s+vie\b",
    r"illimit[ée]e?s?", r"co[uû]t\s+nul", r"0\s*MAD\s+de\s+carburant",
    r"\bfree\s+water\b", r"\bfree\s+for\s+life\b", r"\bfor\s+life\b",
    r"\bunlimited\b", r"\bzero\s+cost\b", r"\bno\s+running\s+cost\b",
    r"0\s*MAD\s+of\s+fuel",
    r"مجان", r"مدى\s+الحياة", r"غير\s+محدود", r"بدون\s+تكلفة",
    r"تكلفة\s+منعدمة",
)
#: Promesses d'ÉCONOMIE D'EAU interdites (fr / en / ar).
INTERDITS_EAU = (
    r"[ée]conomise[rz]?\s+l['’]eau", r"[ée]conomies?\s+d['’]eau",
    r"moins\s+d['’]eau\s+gaspill[ée]e",
    r"\bsaves?\s+water\b", r"\bwater\s+savings?\b",
    r"\bless\s+water\s+wasted\b",
    r"توفير\s+الماء", r"يوفر\s+الماء", r"اقتصاد\s+الماء",
)
MOTIFS = [re.compile(m, re.IGNORECASE) for m in
          INTERDITS_ECONOMIQUES + INTERDITS_EAU]

ETUDE_UNE_PAGE = {
    'mode_pompe': 'neuve', 'pompe_cv': 10.2, 'pompe_kw': 7.5, 'hmt_m': 58.7,
    'debit_hmt_m3h': 30.5, 'm3_jour': 134.2, 'heures_pompage': 4.4,
    'champ_kwc': 9.94,
}


def _texte(html):
    """Le texte LU : sans feuille de style, images ``data:`` ni balises."""
    html = re.sub(r'<style>.*?</style>', ' ', html, flags=re.S)
    html = re.sub(r'data:[^"\')]+', ' ', html)
    return re.sub(r'<[^>]+>', ' ', html)


def violations(texte):
    return [m.pattern for m in MOTIFS if m.search(texte)]


def _trois_pages(langue, minimale=False):
    d = data_minimale() if minimale else data_complete(nb_options=2)
    d['langue_sortie'] = langue
    return pages.build_html(renderer._augment(d))


def _une_page(langue):
    surcharges = {'mode_installation': 'agricole',
                  'etude': dict(ETUDE_UNE_PAGE), 'langue_sortie': langue,
                  'libelles_document': L.libelles(langue)}
    return F.html_onepage(**surcharges)


def _textes_mentions():
    textes = []
    for f in mentions.formalites():
        textes += list(f['textes'].values())
    textes += list(mentions.regle_fda(None)['textes'].values())
    for phrases in mentions.PHRASES_PROVENANCE.values():
        textes += list(phrases.values())
    textes += list(CONDITION_ECONOMIES.values())
    for cle, trad in L.LIBELLES.items():
        if cle.startswith('agr_'):
            textes += list(trad.values())
    return textes


class Agr317GardeMordTests(SimpleTestCase):

    def test_la_garde_mord_sur_un_libelle_injecte(self):
        """La preuve qu'elle n'est pas vide : « eau gratuite » injecté dans
        un libellé du document rend la garde ROUGE."""
        faux = dict(L.LIBELLES)
        faux['agr_titre_p1'] = {**L.LIBELLES['agr_titre_p1'],
                                'fr': "L'eau gratuite de votre exploitation"}
        with mock.patch.object(L, 'LIBELLES', faux):
            html = _trois_pages('fr')
        self.assertIn(r"eau\s+gratuite", violations(_texte(html)))

    def test_la_garde_ne_vise_pas_etude_gratuite_hors_agricole(self):
        # « étude gratuite » n'est ni « eau gratuite » ni « gratuit à vie ».
        self.assertEqual(violations('Étude gratuite de votre toiture'), [])

    def test_chaque_motif_reconnait_sa_formulation(self):
        for exemple in ("l'eau gratuite", 'gratuit à vie', 'illimitée',
                        'coût nul', '0 MAD de carburant', 'free water',
                        'unlimited', 'مجانا', 'مدى الحياة',
                        "économise l'eau", "moins d'eau gaspillée",
                        'saves water', 'توفير الماء'):
            with self.subTest(exemple=exemple):
                self.assertTrue(violations(exemple))


class Agr317RendusReelsTests(SimpleTestCase):

    def test_document_de_trois_pages_fr_en_ar(self):
        for langue in ('fr', 'en', 'ar'):
            for minimale in (False, True):
                with self.subTest(langue=langue, minimale=minimale):
                    self.assertEqual(
                        violations(_texte(_trois_pages(langue, minimale))),
                        [])

    def test_une_page_fr_en_ar(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                self.assertEqual(violations(_texte(_une_page(langue))), [])
        # Le une-page agricole est bien celui qui a été lu.
        self.assertIn('Bon pour accord', _une_page('fr'))

    def test_textes_des_mentions_et_du_catalogue(self):
        for texte in _textes_mentions():
            with self.subTest(texte=texte[:60]):
                self.assertEqual(violations(texte), [])
