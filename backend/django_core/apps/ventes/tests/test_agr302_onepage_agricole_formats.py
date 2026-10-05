"""AGR302 — une-page agricole : chiffres à la française, libellés traduits,
m³/jour marqué « estimation » avec ses heures, plus de renvoi vers un « devis
multi-pages » qui n'existe pas en pompage.

Tests sur le HTML RÉELLEMENT rendu par le moteur (``render_html_for`` : la
chaîne exacte envoyée à WeasyPrint), sans base de données ni WeasyPrint — la
charge utile est la fixture canonique ``_moteur_fixtures`` (forme
``build_quote_data``). Le compte de pages reste prouvé par les tests rendus
de ``test_quote_engine_formats`` (une-page agricole = 1 page).
"""
from django.test import SimpleTestCase

from apps.ventes.tests import _moteur_fixtures as F


ETUDE_COURBE = {
    'pompe_cv': '5.5', 'pompe_kw': 3.7, 'type_pompe': 'immergee',
    'alim': 'tri', 'hmt_m': '62.5', 'debit_hmt_m3h': 30.5,
    'heures_pompage': 7, 'm3_jour': 213, 'champ_kwc': 5.68,
}

LIBELLES_FR_POMPAGE = (
    'Puissance pompe', 'D&#233;bit &#224;', 'Eau / jour', 'Champ PV',
)


def _html(langue=None, etude=None):
    surcharges = {'mode_installation': 'agricole',
                  'etude': dict(etude or ETUDE_COURBE)}
    if langue:
        from apps.ventes.quote_engine import i18n_labels
        surcharges['langue_sortie'] = langue
        surcharges['libelles_document'] = i18n_labels.libelles(langue)
    return F.html_onepage(**surcharges)


class Agr302ChiffresALaFrancaiseTests(SimpleTestCase):

    def test_cv_kw_et_hmt_sortent_avec_la_virgule_decimale(self):
        html = _html()
        self.assertIn('5,5 CV (3,7 kW)', html)
        self.assertIn('62,5 m<', html)
        self.assertIn('D&#233;bit &#224; 62,5 m', html)
        # Plus jamais le point décimal anglais dans le résumé pompage.
        self.assertNotIn('5.5 CV', html)
        self.assertNotIn('3.7 kW', html)
        self.assertNotIn('62.5 m<', html)
        self.assertNotIn('&#224; 62.5 m', html)

    def test_entier_reste_sans_decimale(self):
        html = _html(etude={**ETUDE_COURBE, 'pompe_cv': '10',
                            'pompe_kw': 7.5, 'hmt_m': '80'})
        self.assertIn('10 CV (7,5 kW)', html)
        self.assertIn('D&#233;bit &#224; 80 m', html)


class Agr302CarteEauEstimationTests(SimpleTestCase):

    def test_la_carte_eau_dit_estimation_et_hypothese_des_heures(self):
        html = _html()
        self.assertIn(
            'Eau / jour &#8212; estimation, sur 7 h de pompage '
            '(hypoth&#232;se)', html)

    def test_sans_courbe_aucune_carte_eau(self):
        html = _html(etude={**ETUDE_COURBE, 'debit_hmt_m3h': None,
                            'heures_pompage': None, 'm3_jour': None})
        self.assertNotIn('Eau / jour', html)
        self.assertNotIn('estimation', html)


class Agr302LibellesTraduitsTests(SimpleTestCase):

    def test_en_arabe_aucun_des_quatre_libelles_francais_ne_reste(self):
        html = _html(langue='ar')
        for libelle in LIBELLES_FR_POMPAGE:
            with self.subTest(libelle=libelle):
                self.assertNotIn(libelle, html)
        self.assertNotIn('estimation', html)
        self.assertNotIn('hypoth&#232;se', html)
        from apps.ventes.quote_engine import i18n_labels as L
        self.assertIn(L.libelle('puissance_pompe', 'ar'), html)
        self.assertIn(L.libelle('estimation', 'ar'), html)

    def test_en_anglais_les_libelles_sont_anglais(self):
        html = _html(langue='en')
        self.assertIn('Pump power', html)
        self.assertIn('Flow at 62,5 m', html)
        self.assertIn('over 7 h of pumping', html)
        self.assertIn('PV array', html)
        for libelle in LIBELLES_FR_POMPAGE:
            with self.subTest(libelle=libelle):
                self.assertNotIn(libelle, html)

    def test_les_nouvelles_cles_portent_les_trois_langues(self):
        from apps.ventes.quote_engine import i18n_labels as L
        for cle in ('puissance_pompe', 'debit_a_hmt', 'eau_jour',
                    'sur_heures_pompage', 'estimation', 'hypothese',
                    'champ_pv'):
            for langue in L.LANGUES:
                with self.subTest(cle=cle, langue=langue):
                    self.assertTrue(L.LIBELLES[cle][langue].strip())
        # Les gabarits gardent leur emplacement de nombre dans chaque langue.
        for langue in L.LANGUES:
            self.assertIn('{hmt}', L.LIBELLES['debit_a_hmt'][langue])
            self.assertIn('{heures}', L.LIBELLES['sur_heures_pompage'][langue])


class Agr302RenvoiTroncatureTests(SimpleTestCase):

    def _table_tronquee(self, mode):
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = F.donnees_legacy(
            'deux', pdf_mode='onepage', mode_installation=mode,
            etude=dict(ETUDE_COURBE) if mode == 'agricole' else {})
        G.render_html_for(data)  # pose l'état du module (globales du rendu)
        return G.build_html_onepage(list(data['all_items'])[:2], tronquees=3)

    def test_agricole_tronque_ne_renvoie_plus_au_devis_multi_pages(self):
        # AGR312 — re-épinglé : le renvoi pointe désormais vers le document
        # agricole complet de 3 pages (le renderer est branché au registre).
        html = self._table_tronquee('agricole')
        self.assertIn('autres lignes d&#8217;&#233;quipement', html)
        self.assertNotIn('multi-pages', html)
        self.assertIn('le document complet (3 pages)', html)

    def test_residentiel_tronque_garde_son_renvoi(self):
        html = self._table_tronquee('residentiel')
        self.assertIn('le devis multi-pages', html)
