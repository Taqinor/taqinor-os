"""VAO20 — échouer FORT : les trois cas, sur les fixtures committées.

Le mode de défaillance que ce module interdit : un collecteur qui casse et
rend « 0 résultat ». On se croit couvert, on ne l'est plus, et on rate un
appel d'offres sans jamais voir passer d'erreur.

Les trois cas, jamais confondus :
  1. **succès** — collecte réussie, 0 nouveauté possible (page vide) ;
  2. **anomalie** — collecte réussie mais la structure a bougé : lignes
     illisibles, ou le contrôle croisé lignes/total ne tombe pas juste ;
  3. **échec** — compteur introuvable, page de refus, ou 0 ligne lue là où le
     portail en annonce : une ERREUR NOMMÉE, jamais un tableau vide.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.test import SimpleTestCase

from apps.veille_ao.portail import fixtures
from apps.veille_ao.portail import resultats as portail_resultats
from apps.veille_ao.tests.test_purete_portail import GardeReseau

URL_BASE = 'https://portail.test.invalid/'


def _page(nom):
    return fixtures.charger(nom)


@dataclass
class RechercheFictive:
    """Ce que le client (VAO16) rend — en canard, sans réseau."""

    total_annonce: int | None = None
    pages: list = field(default_factory=list)
    tronquee: bool = False

    @property
    def html(self):
        return self.pages[-1] if self.pages else ''


class CasUnSuccesTests(SimpleTestCase):
    """« Collecte réussie, 0 nouveauté » est NORMAL — jamais une erreur."""

    def test_la_page_vide_est_un_SUCCES(self):
        with GardeReseau():
            resultat = portail_resultats.analyser_resultats(
                _page(fixtures.RESULTATS_VIDE))
        self.assertTrue(resultat.est_succes)
        self.assertEqual(resultat.total_annonce, 0)
        self.assertEqual(resultat.lignes, [])
        self.assertEqual(resultat.anomalies, [])

    def test_le_message_du_vide_dit_bien_qu_il_n_y_a_RIEN_a_signaler(self):
        resultat = portail_resultats.analyser_resultats(
            _page(fixtures.RESULTATS_VIDE))
        self.assertIn('réussie', resultat.message)
        self.assertIn('aucune consultation', resultat.message.lower())

    def test_la_page_get_a_dix_lignes_sur_34_annonces_est_un_SUCCES(self):
        """Le portail plafonne l'affichage à 10 : ce n'est pas une anomalie."""
        recherche = RechercheFictive(
            total_annonce=34, pages=[_page(fixtures.RESULTATS_10)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertTrue(resultat.est_succes, resultat.anomalies)
        self.assertEqual(resultat.total_lu, 10)

    def test_la_sequence_complete_34_sur_34_est_un_SUCCES(self):
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10), _page(fixtures.RESULTATS_500)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertTrue(resultat.est_succes, resultat.anomalies)
        self.assertEqual(resultat.total_lu, 34)

    def test_la_page_GET_n_est_pas_comptee_deux_fois(self):
        """Ses 10 lignes sont RÉPÉTÉES dans le postback : les additionner
        ferait un doublon systématique de 10 avis à chaque collecte."""
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10), _page(fixtures.RESULTATS_500)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertEqual(resultat.total_lu, 34)  # et non 44
        identites = {(ligne['ref_consultation'], ligne['org_acronyme'])
                     for ligne in resultat.lignes}
        self.assertEqual(len(identites), 34)


class CasDeuxAnomalieTests(SimpleTestCase):
    """Le contrôle croisé : un écart lignes/total N'EST PAS un résultat."""

    def test_34_annonces_3_servies_est_une_ANOMALIE(self):
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10),
                   _page(fixtures.RESULTATS_INCOHERENT)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertTrue(resultat.est_anomalie)
        self.assertFalse(resultat.est_succes)
        self.assertEqual(resultat.total_lu, 3)

    def test_l_anomalie_NOMME_l_ecart_chiffres_a_l_appui(self):
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10),
                   _page(fixtures.RESULTATS_INCOHERENT)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        anomalie = ' '.join(resultat.anomalies)
        self.assertIn('contrôle croisé', anomalie)
        self.assertIn('3', anomalie)
        self.assertIn('34', anomalie)

    def test_les_donnees_LUES_sont_quand_meme_rendues(self):
        """Une anomalie n'est pas une perte : les 3 lignes restent lisibles.

        Jeter ce qu'on a su lire ferait perdre des avis réels à cause d'un
        doute sur le compte.
        """
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10),
                   _page(fixtures.RESULTATS_INCOHERENT)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertEqual(len(resultat.lignes), 3)
        self.assertTrue(resultat.lignes[0]['objet'])

    def test_une_ligne_illisible_est_une_ANOMALIE_pas_un_echec(self):
        page = _page(fixtures.RESULTATS_500).replace(
            '<strong> Objet : </strong>', '<strong> Autre : </strong>', 1)
        resultat = portail_resultats.analyser_resultats(
            page, url_base=URL_BASE, lignes_attendues=34)
        self.assertTrue(resultat.est_anomalie)
        self.assertEqual(resultat.total_lu, 33)
        self.assertIn('illisible', ' '.join(resultat.anomalies))

    def test_une_collecte_TRONQUEE_est_une_anomalie_declaree(self):
        recherche = RechercheFictive(
            total_annonce=3380,
            pages=[_page(fixtures.RESULTATS_10), _page(fixtures.RESULTATS_500)],
            tronquee=True)
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertTrue(resultat.est_anomalie)
        self.assertIn('TRONQUÉE', ' '.join(resultat.anomalies))

    def test_une_collecte_tronquee_ne_crie_pas_DEUX_fois(self):
        """L'écart lignes/total est ATTENDU quand on a tronqué volontairement.

        Ajouter « contrôle croisé » par-dessus noierait le message utile.
        """
        recherche = RechercheFictive(
            total_annonce=3380,
            pages=[_page(fixtures.RESULTATS_10), _page(fixtures.RESULTATS_500)],
            tronquee=True)
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertEqual(len(resultat.anomalies), 1)
        self.assertNotIn('contrôle croisé', resultat.anomalies[0])

    def test_le_message_d_anomalie_est_lisible_dans_le_journal(self):
        recherche = RechercheFictive(
            total_annonce=34,
            pages=[_page(fixtures.RESULTATS_10),
                   _page(fixtures.RESULTATS_INCOHERENT)])
        resultat = portail_resultats.analyser_recherche(recherche,
                                                        url_base=URL_BASE)
        self.assertIn('anomalie', resultat.message.lower())

    def test_l_anomalie_est_JOURNALISEE(self):
        with self.assertLogs('apps.veille_ao.portail.resultats',
                             level='WARNING') as journal:
            portail_resultats.analyser_resultats(
                _page(fixtures.RESULTATS_INCOHERENT), url_base=URL_BASE)
        self.assertTrue(any('ANORMALE' in ligne for ligne in journal.output))


class CasTroisEchecTests(SimpleTestCase):
    """Un HTML dérivé produit une ERREUR NOMMÉE, jamais un tableau vide."""

    def test_un_html_derive_LEVE_au_lieu_de_rendre_une_liste_vide(self):
        with self.assertRaises(portail_resultats.ReponseInattendue) as capture:
            portail_resultats.analyser_resultats(
                _page(fixtures.RESULTATS_DERIVE))
        self.assertIn('Compteur de résultats introuvable',
                      str(capture.exception))

    def test_le_message_d_echec_explique_ce_qui_manque(self):
        """« La page a changé » sans plus n'aide personne à réparer."""
        with self.assertRaises(portail_resultats.ReponseInattendue) as capture:
            portail_resultats.analyser_resultats(
                _page(fixtures.RESULTATS_DERIVE))
        message = str(capture.exception)
        self.assertIn('ÉCHEC', message)
        self.assertIn('pas un résultat vide', message)

    def test_la_fixture_403_est_un_ECHEC_nomme_comme_un_REFUS(self):
        with self.assertRaises(portail_resultats.ReponseInattendue) as capture:
            portail_resultats.analyser_resultats(_page(fixtures.ERREUR_403))
        self.assertIn('REFUS', str(capture.exception))

    def test_un_refus_ne_se_confond_pas_avec_une_derive_de_structure(self):
        derive = str(portail_resultats.ressemble_a_un_refus(
            _page(fixtures.RESULTATS_DERIVE)))
        self.assertEqual(derive, 'False')
        self.assertTrue(
            portail_resultats.ressemble_a_un_refus(_page(fixtures.ERREUR_403)))

    def test_34_annonces_ZERO_ligne_lue_est_un_ECHEC(self):
        """Le pire cas : le compteur tient, le tableau a disparu."""
        page = _page(fixtures.RESULTATS_500)
        debut = page.index('<tbody>')
        fin = page.index('</tbody>') + len('</tbody>')
        sans_lignes = page[:debut] + '<tbody></tbody>' + page[fin:]
        with self.assertRaises(portail_resultats.ReponseInattendue) as capture:
            portail_resultats.analyser_resultats(sans_lignes, url_base=URL_BASE)
        self.assertIn('AUCUNE', str(capture.exception))

    def test_une_recherche_sans_aucune_page_est_un_ECHEC(self):
        with self.assertRaises(portail_resultats.ReponseInattendue):
            portail_resultats.analyser_recherche(RechercheFictive())

    def test_un_compteur_absent_n_est_pas_zero(self):
        self.assertIsNone(
            portail_resultats.lire_total(_page(fixtures.RESULTATS_DERIVE)))
        self.assertEqual(
            portail_resultats.lire_total(_page(fixtures.RESULTATS_VIDE)), 0)


class LectureDuProtocoleTests(SimpleTestCase):
    """Les deux lecteurs PRADO ont UNE seule implémentation, partagée.

    Deux lectures divergentes du même compteur — l'une dans le client, l'autre
    dans le verdict — seraient un bug qu'aucun test unitaire ne verrait.
    """

    def test_le_client_et_le_verdict_lisent_le_MEME_compteur(self):
        from apps.veille_ao.portail import client as portail_client
        self.assertIs(portail_client.lire_total, portail_resultats.lire_total)
        self.assertIs(portail_client.lire_pagestate,
                      portail_resultats.lire_pagestate)

    def test_le_pagestate_est_desechappe(self):
        pagestate = portail_resultats.lire_pagestate(
            _page(fixtures.RESULTATS_10))
        self.assertIn('+', pagestate)
        self.assertNotIn('&#43;', pagestate)

    def test_le_verdict_n_ouvre_aucune_socket(self):
        with GardeReseau():
            for nom in (fixtures.RESULTATS_VIDE, fixtures.RESULTATS_500):
                self.assertTrue(
                    portail_resultats.analyser_resultats(_page(nom)) is not None)
