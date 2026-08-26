"""VAO17 — le parseur de ligne, figé sur les fixtures committées.

Aucune base, aucun réseau : ce module ne parle qu'aux fichiers de
``portail/fixtures/``. Les valeurs attendues sont FIGÉES ici — c'est ce qui
fait de ce test un détecteur de dérive du portail (le jour où les ancres
bougent, il rougit) et non une simple redite du code.

Le point qui mérite d'être lu en entier : **la référence AFFICHÉE et
l'identité de portail sont deux choses différentes**. La ligne montre
« 12/2026/K1Z » ; l'URL porte ``refConsultation=812340&orgAcronyme=k1z``. Le
dédoublonnage de niveau 1 (VAO11) repose sur la SECONDE — confondre les deux
ferait entrer deux fois la même consultation.
"""
from __future__ import annotations

import datetime as dt

from django.test import SimpleTestCase

from apps.veille_ao.portail import fixtures
from apps.veille_ao.portail import parser as portail_parser
from apps.veille_ao.services import CHAMPS_RECTIFIABLES
from apps.veille_ao.tests.test_purete_portail import GardeReseau

URL_BASE = 'https://portail.test.invalid/'


def _page(nom):
    return fixtures.charger(nom)


class NormalisationTests(SimpleTestCase):
    """Les petites fonctions pures — testées une par une, sans HTML."""

    def test_les_espaces_insecables_sont_ecrases(self):
        self.assertEqual(
            portail_parser.normaliser('  Commune\xa0de   Test-Sud \n'),
            'Commune de Test-Sud')

    def test_une_date_simple_est_lue(self):
        self.assertEqual(portail_parser.lire_date('28/07/2026'),
                         dt.date(2026, 7, 28))

    def test_une_date_impossible_ne_leve_pas(self):
        self.assertIsNone(portail_parser.lire_date('31/02/2026'))
        self.assertIsNone(portail_parser.lire_date('sans date'))

    def test_une_date_limite_est_AWARE_en_heure_marocaine(self):
        """Naïve, elle décalerait « expiré » d'une heure selon la saison."""
        limite = portail_parser.lire_date_heure('02/09/2026 10:00')
        self.assertIsNotNone(limite.tzinfo)
        self.assertEqual(limite.astimezone(dt.timezone.utc).hour, 9)

    def test_la_variante_a_10h30_est_lue_aussi(self):
        self.assertEqual(
            portail_parser.lire_date_heure('02/09/2026 à 10h30'),
            dt.datetime(2026, 9, 2, 10, 30, tzinfo=portail_parser.CASABLANCA))

    def test_les_identifiants_viennent_de_l_url(self):
        ref, org = portail_parser.lire_identifiants(
            'index.php?page=entreprise.EntrepriseDetailConsultation'
            '&refConsultation=812340&orgAcronyme=k1z')
        self.assertEqual((ref, org), ('812340', 'k1z'))

    def test_une_url_sans_identifiant_rend_du_vide_sans_lever(self):
        self.assertEqual(portail_parser.lire_identifiants('index.php'), ('', ''))
        self.assertEqual(portail_parser.lire_identifiants(''), ('', ''))

    def test_le_decodage_est_en_utf8(self):
        octets = 'bâtiment — écolé'.encode('utf-8')
        self.assertEqual(portail_parser.decoder_utf8(octets), 'bâtiment — écolé')

    def test_un_octet_fautif_ne_perd_pas_la_page(self):
        self.assertIn('timent', portail_parser.decoder_utf8(b'b\xe2timent'))


class PremiereLigneTests(SimpleTestCase):
    """Les valeurs de la première ligne, FIGÉES champ par champ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with GardeReseau():
            cls.extraction = portail_parser.analyser_page(
                _page(fixtures.RESULTATS_10), url_base=URL_BASE)
        cls.ligne = cls.extraction.lignes[0]

    def test_l_identite_de_portail_vient_de_l_url(self):
        self.assertEqual(self.ligne['ref_consultation'], '812340')
        self.assertEqual(self.ligne['org_acronyme'], 'k1z')

    def test_la_reference_affichee_est_distincte_de_l_identite(self):
        self.assertEqual(self.ligne['reference_avis'], '12/2026/K1Z')
        self.assertNotEqual(self.ligne['reference_avis'],
                            self.ligne['ref_consultation'])

    def test_l_objet_est_lu_en_entier_et_accentue(self):
        self.assertEqual(
            self.ligne['objet'],
            "Fourniture et installation d'une centrale photovoltaïque "
            'raccordée au réseau de 250 kWc — bâtiment administratif '
            "(dossier d'essai)")

    def test_l_acheteur_le_lieu_la_procedure_et_la_categorie(self):
        self.assertEqual(self.ligne['acheteur'], 'Commune de Test-Sud')
        self.assertEqual(self.ligne['lieu'], 'Test-Sud')
        self.assertEqual(self.ligne['procedure'], "Appel d'offres ouvert")
        self.assertEqual(self.ligne['categorie'], 'Travaux')

    def test_la_date_de_publication_vient_de_la_premiere_cellule(self):
        self.assertEqual(self.ligne['date_publication'], dt.date(2026, 7, 28))

    def test_la_date_limite_est_lue_avec_son_heure(self):
        self.assertEqual(
            self.ligne['date_limite_remise'],
            dt.datetime(2026, 9, 2, 10, 0, tzinfo=portail_parser.CASABLANCA))

    def test_l_url_de_detail_est_absolue(self):
        self.assertTrue(self.ligne['url_detail'].startswith(URL_BASE))
        self.assertIn('refConsultation=812340', self.ligne['url_detail'])
        self.assertIn('orgAcronyme=k1z', self.ligne['url_detail'])

    def test_toutes_les_cles_rendues_sont_enregistrables(self):
        """Le dictionnaire se donne TEL QUEL à ``enregistrer_avis`` (VAO11)."""
        for cle in self.ligne:
            with self.subTest(cle=cle):
                self.assertIn(cle, CHAMPS_RECTIFIABLES)

    def test_aucune_cle_vide_n_est_rendue(self):
        """Une clé qu'on ne sait pas remplir est ABSENTE, jamais vide.

        Une chaîne vide ÉCRASERAIT, à la ré-collecte, une valeur qu'un humain
        ou la page de détail avait renseignée (VAO18).
        """
        for cle, valeur in self.ligne.items():
            with self.subTest(cle=cle):
                self.assertNotEqual(valeur, '', cle)
                self.assertIsNotNone(valeur, cle)


class VolumetrieTests(SimpleTestCase):
    """Les 5 fixtures, parsées — et le compte des lignes."""

    def test_la_page_get_rend_les_dix_lignes_affichees(self):
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_10))
        self.assertEqual(extraction.total_lu, 10)
        self.assertEqual(extraction.ignorees, [])

    def test_la_reponse_a_500_rend_les_34_lignes(self):
        """Le total mesuré de « solaire » le 2026-08-01 : 34 avis en cours."""
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_500))
        self.assertEqual(extraction.total_lu, 34)
        self.assertEqual(extraction.ignorees, [])

    def test_la_page_vide_rend_zero_ligne_sans_lever(self):
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_VIDE))
        self.assertEqual(extraction.lignes, [])
        self.assertEqual(extraction.ignorees, [])

    def test_la_page_403_rend_zero_ligne_sans_lever(self):
        """Le parseur ne juge pas : c'est VAO20 qui en fait un ÉCHEC."""
        extraction = portail_parser.analyser_page(_page(fixtures.ERREUR_403))
        self.assertEqual(extraction.lignes, [])

    def test_la_page_derivee_rend_zero_ligne_sans_lever(self):
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_DERIVE))
        self.assertEqual(extraction.lignes, [])

    def test_la_page_incoherente_rend_ses_trois_lignes(self):
        extraction = portail_parser.analyser_page(
            _page(fixtures.RESULTATS_INCOHERENT))
        self.assertEqual(extraction.total_lu, 3)

    def test_les_identifiants_sont_tous_distincts(self):
        """Un parseur qui recopierait la même ligne 34 fois passerait le compte."""
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_500))
        identites = {(ligne['ref_consultation'], ligne['org_acronyme'])
                     for ligne in extraction.lignes}
        self.assertEqual(len(identites), 34)

    def test_chaque_ligne_porte_le_minimum_vital(self):
        extraction = portail_parser.analyser_page(_page(fixtures.RESULTATS_500))
        for ligne in extraction.lignes:
            with self.subTest(ref=ligne['ref_consultation']):
                self.assertTrue(ligne['objet'])
                self.assertTrue(ligne['acheteur'])
                self.assertTrue(ligne['date_limite_remise'])

    def test_le_parsing_n_ouvre_aucune_socket(self):
        with GardeReseau():
            self.assertTrue(
                portail_parser.analyser_page(_page(fixtures.RESULTATS_500)).lignes)


class LigneMalformeeTests(SimpleTestCase):
    """Une ligne fautive est ÉCARTÉE avec son motif — jamais fatale.

    C'est la promesse de la tâche : « une ligne malformée est ignorée avec un
    motif journalisé sans faire tomber la collecte entière ». Une exception
    qui remonte ferait perdre 33 avis bons pour un avis bancal.
    """

    def _sans_lien_sur_la_premiere_ligne(self):
        page = _page(fixtures.RESULTATS_10)
        depart = page.index('<a href="index.php?page=entreprise.Entreprise')
        fin = page.index('</a>', depart) + len('</a>')
        return page[:depart] + 'Consulter' + page[fin:]

    def test_une_ligne_sans_lien_de_detail_est_ignoree_avec_son_motif(self):
        extraction = portail_parser.analyser_page(
            self._sans_lien_sur_la_premiere_ligne())
        self.assertEqual(extraction.total_lu, 9)
        self.assertEqual(len(extraction.ignorees), 1)
        indice, motif = extraction.ignorees[0]
        self.assertEqual(indice, 1)
        self.assertIn('détail', motif)

    def test_les_neuf_autres_lignes_passent_quand_meme(self):
        extraction = portail_parser.analyser_page(
            self._sans_lien_sur_la_premiere_ligne())
        self.assertEqual(extraction.total_vu, 10)
        self.assertEqual(extraction.lignes[0]['ref_consultation'], '812347')

    def test_une_ligne_sans_objet_est_ignoree(self):
        page = _page(fixtures.RESULTATS_10).replace(
            '<strong> Objet : </strong>', '<strong> Autre : </strong>', 1)
        extraction = portail_parser.analyser_page(page)
        self.assertEqual(extraction.total_lu, 9)
        self.assertIn('objet', extraction.ignorees[0][1])

    def test_une_url_de_detail_sans_refconsultation_est_ignoree(self):
        page = _page(fixtures.RESULTATS_10).replace(
            'refConsultation=812340', 'refAutreChose=812340', 1)
        extraction = portail_parser.analyser_page(page)
        self.assertEqual(extraction.total_lu, 9)
        self.assertIn('refConsultation', extraction.ignorees[0][1])

    def test_le_journal_nomme_la_ligne_fautive(self):
        with self.assertLogs('apps.veille_ao.portail.parser', level='WARNING') as journal:
            portail_parser.analyser_page(self._sans_lien_sur_la_premiere_ligne())
        self.assertTrue(any('ignorée' in ligne for ligne in journal.output))


class ResistanceALaMiseEnFormeTests(SimpleTestCase):
    """Un restylage du portail ne doit pas rendre 0 avis là où il y en a 10."""

    def test_l_identifiant_de_table_peut_changer(self):
        page = _page(fixtures.RESULTATS_10).replace(
            'ctl0_CONTENU_PAGE_resultSearch_tableauResultat', 'nouveauTableau')
        self.assertEqual(
            portail_parser.analyser_page(page).total_lu, 10)

    def test_les_libelles_sans_accent_restent_trouvables(self):
        page = _page(fixtures.RESULTATS_10).replace('Procédure', 'Procedure')
        ligne = portail_parser.analyser_page(page).lignes[0]
        self.assertEqual(ligne['procedure'], "Appel d'offres ouvert")
