"""AOF132 — acte d'engagement : mode autonome et mode fiche de report.

    python -m unittest apps.ao.tests.test_aof_acte -v
"""
import html as _html
import pathlib
import unittest
from decimal import Decimal

from apps.ao.fabrique.contexte import construire_contexte, litteraux_chiffres
from apps.ao.fabrique.rendus import acte_engagement as acte
from apps.ao.fabrique.rendus import bordereau_pdf, lettre
from apps.ao.tests.aof_fixtures import (ARRETE_TTC, TOTAL_HT, TOTAL_TTC, TVA,
                                        bordereau_depose, contexte_dossier,
                                        rendre_gabarit)

GABARITS = pathlib.Path(__file__).resolve().parents[3] / 'templates'

MODELE_ACHETEUR = {'reference': 'DCE-03', 'libelle': "Acte d'engagement (E3)"}


def donnees(modele_acheteur=None):
    lignes = bordereau_depose()
    contexte = construire_contexte(contexte_dossier(lignes))
    return lignes, contexte, acte.contexte_gabarit(
        lignes, contexte, modele_acheteur=modele_acheteur)


def rendu(modele_acheteur=None):
    _, _, vue = donnees(modele_acheteur)
    return _html.unescape(rendre_gabarit(acte.NOM_GABARIT, vue)), vue


class TestModeAutonome(unittest.TestCase):

    def setUp(self):
        self.html, self.vue = rendu()

    def test_le_mode_est_autonome_sans_modele_acheteur(self):
        self.assertEqual(self.vue['mode'], acte.MODE_AUTONOME)
        self.assertFalse(self.vue['mode_report'])
        self.assertIn("Acte d'engagement", self.html)

    def test_l_acte_porte_les_montants_en_chiffres_et_en_lettres(self):
        self.assertIn(ARRETE_TTC, self.html)
        self.assertIn(acte.valeur_du_blanc(self.vue, 'total_ttc'), self.html)

    def test_l_acte_porte_l_identite_complete(self):
        for mention in ('TAQINOR SARL', '002345678000091', '123456',
                        '55667788', '9988776', '30123456'):
            self.assertIn(mention, self.html, mention)

    def test_l_acte_porte_le_rib_et_la_banque(self):
        self.assertIn('011 780 0000012345678901 23', self.html)
        self.assertIn('Attijariwafa', self.html)

    def test_l_acte_porte_la_validite_et_le_delai(self):
        self.assertIn('75 jours', self.html)
        self.assertIn('Soixante-quinze jours', self.html)
        self.assertIn('120 jours', self.html)

    def test_le_cadre_de_signature_est_present(self):
        self.assertIn('signature et cachet', self.html)


class TestModeReport(unittest.TestCase):

    def setUp(self):
        self.html, self.vue = rendu(MODELE_ACHETEUR)

    def test_le_mode_bascule_avec_un_modele_acheteur(self):
        self.assertEqual(self.vue['mode'], acte.MODE_REPORT)
        self.assertTrue(self.vue['mode_report'])

    def test_l_acte_de_l_acheteur_n_est_pas_regenere(self):
        """La fiche DIT de remplir la pièce du DCE, elle ne la refabrique pas."""
        self.assertIn('sans être reproduit ni reconstitué', self.html)
        self.assertNotIn('signature et cachet', self.html)

    def test_la_piece_du_dce_est_nommee(self):
        self.assertIn("Acte d'engagement (E3)", self.html)
        self.assertIn('DCE-03', self.html)

    def test_chaque_blanc_porte_sa_valeur_et_sa_reference_dce(self):
        fiche = acte.fiche_de_report(self.vue)
        self.assertGreaterEqual(len(fiche), 18)
        for blanc in fiche:
            self.assertEqual(blanc['reference_dce'], 'DCE-03', blanc['code'])
        par_code = {blanc['code']: blanc for blanc in fiche}
        self.assertIn('DIRHAMS', par_code['total_ttc']['lettres'])
        self.assertTrue(par_code['rib']['valeur'])

    def test_la_fiche_couvre_les_rubriques_attendues(self):
        codes = {blanc['code'] for blanc in acte.fiche_de_report(self.vue)}
        for attendu in ('raison_sociale', 'ice', 'rc', 'if_fiscal', 'rib',
                        'total_ht', 'tva', 'total_ttc', 'validite',
                        'signataire', 'lieu_date'):
            self.assertIn(attendu, codes, attendu)


class TestValeursIdentiques(unittest.TestCase):
    """Acte, bordereau et lettre disent la même chose, au centime."""

    def setUp(self):
        self.lignes, self.contexte, self.vue = donnees()
        self.bordereau = bordereau_pdf.valeurs_de_controle(
            bordereau_pdf.contexte_gabarit(self.lignes, self.contexte))
        self.lettre = lettre.valeurs_de_controle(
            lettre.contexte_gabarit(self.lignes, self.contexte))

    def test_aucun_ecart_avec_le_bordereau_ni_la_lettre(self):
        self.assertEqual(acte.controler_vs(self.vue, self.bordereau,
                                           self.lettre), ())

    def test_les_montants_reels(self):
        portes = acte.valeurs_de_controle(self.vue)
        self.assertEqual(portes['total_ht'], TOTAL_HT)
        self.assertEqual(portes['tva'], TVA)
        self.assertEqual(portes['total_ttc'], TOTAL_TTC)

    def test_un_ecart_est_detecte(self):
        faux = dict(self.bordereau, total_ttc=Decimal('5219280'))
        ecarts = acte.controler_vs(self.vue, faux)
        self.assertEqual(len(ecarts), 1)
        self.assertIn('total_ttc', ecarts[0])

    def test_les_deux_modes_portent_les_memes_valeurs(self):
        _, _, report = donnees(MODELE_ACHETEUR)
        self.assertEqual(acte.valeurs_de_controle(report),
                         acte.valeurs_de_controle(self.vue))
        self.assertEqual(
            [blanc.valeur for blanc in report['blancs']],
            [blanc.valeur for blanc in self.vue['blancs']])


class TestCompletude(unittest.TestCase):

    def test_un_dossier_complet_ne_laisse_aucun_blanc(self):
        _, _, vue = donnees()
        self.assertEqual(acte.blancs_non_remplis(vue), ())

    def test_un_rib_absent_est_signale(self):
        lignes = bordereau_depose()
        dossier = contexte_dossier(lignes)
        dossier['identite']['rib'] = ''
        vue = acte.contexte_gabarit(lignes, construire_contexte(dossier))
        self.assertIn('rib', acte.blancs_non_remplis(vue))

    def test_les_rubriques_facultatives_ne_bloquent_pas(self):
        lignes = bordereau_depose()
        dossier = contexte_dossier(lignes)
        dossier['identite']['cnss'] = ''
        dossier['identite']['patente'] = ''
        vue = acte.contexte_gabarit(lignes, construire_contexte(dossier))
        self.assertEqual(acte.blancs_non_remplis(vue), ())


class TestGabarit(unittest.TestCase):

    def test_aucun_chiffre_litteral_dans_le_gabarit(self):
        source = (GABARITS / 'ao' / 'acte_engagement.html').read_text(
            encoding='utf-8')
        self.assertEqual(litteraux_chiffres(source), ())

    def test_sans_delai_l_acte_n_en_invente_pas(self):
        lignes = bordereau_depose()
        dossier = contexte_dossier(lignes)
        dossier['marche']['delai_execution_jours'] = None
        vue = acte.contexte_gabarit(lignes, construire_contexte(dossier))
        self.assertNotIn('delai', {b.code for b in vue['blancs']})


class TestEtancheite(unittest.TestCase):
    """AOF129 étendu à l'acte — dans le même commit, comme exigé."""

    def test_l_acte_est_dans_la_liste_du_ratchet(self):
        from apps.ao.tests.test_aof_etancheite_pack import ARTEFACTS_COUVERTS
        libelles = [libelle for libelle, _ in ARTEFACTS_COUVERTS]
        self.assertTrue(any("acte d'engagement" in libelle.lower()
                            for libelle in libelles), libelles)

    def test_les_deux_modes_sont_etanches(self):
        from apps.ao.tests.test_aof_etancheite_pack import scanner
        self.assertEqual(scanner(rendu()[0]), ())
        self.assertEqual(scanner(rendu(MODELE_ACHETEUR)[0]), ())


if __name__ == '__main__':
    unittest.main()
