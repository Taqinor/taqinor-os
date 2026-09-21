"""VAO16 — le client PRADO : la recette mesurée, et RIEN de plus.

Tout ce module tourne contre les **fixtures committées**, via un transport
``httpx.MockTransport`` : aucune socket n'est ouverte (``GardeReseau`` le
prouve à l'exécution). Le seul test qui parlerait au portail est marqué
``skip`` par défaut, et le restera tant que la règle #5 n'aura pas reçu
l'accord daté du fondateur (VAO4).

Ce qui est vérifié, dans l'ordre des enjeux :
  1. **un 403 arrête le client**, en UNE requête, sans la moindre tentative
     de repli sous un User-Agent de navigateur — la règle qui prime sur tout ;
  2. une recherche **sans mot-clé restrictif** est refusée AVANT d'ouvrir quoi
     que ce soit (un balayage doit être impossible à écrire par accident) ;
  3. une source **inactive** ne part pas ;
  4. les 3 étapes mesurées : GET → postback 500 → page suivante ;
  5. le pagestate est **déséchappé** (le « + » servi en ``&#43;``) ;
  6. **aucune URL de portail en dur** dans le module.
"""
from __future__ import annotations

import os
import re
import unittest
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from django.test import SimpleTestCase

from apps.veille_ao.portail import client as portail_client
from apps.veille_ao.portail import fixtures
from apps.veille_ao.tests.test_purete_portail import GardeReseau

URL_BASE = 'https://portail.test.invalid'

#: Les jetons qu'un User-Agent honnête ne contient JAMAIS. Ils sont écrits ici
#: — dans le TEST — précisément parce qu'ils sont interdits dans le module.
JETONS_NAVIGATEUR = ('Mozilla', 'Chrome', 'Safari', 'AppleWebKit', 'Gecko',
                     'Firefox', 'Edg/', 'Trident')


@dataclass
class SourceFictive:
    """Une ``SourceVeille`` en canard : le client ne connaît pas Django."""

    libelle: str = 'Portail de test'
    url_base: str = URL_BASE
    actif: bool = True


@dataclass
class TransportEnregistreur:
    """Un ``MockTransport`` qui GARDE la trace de tout ce qui est envoyé.

    C'est lui qui permet de prouver une ABSENCE : « aucune deuxième requête
    n'a été tentée après le 403 » ne se démontre pas autrement.
    """

    reponses: list = field(default_factory=list)
    requetes: list = field(default_factory=list)

    def transport(self):
        def repondre(requete):
            self.requetes.append(requete)
            indice = min(len(self.requetes) - 1, len(self.reponses) - 1)
            statut, corps, entetes = self.reponses[indice]
            return httpx.Response(statut, text=corps, headers=entetes or {})

        return httpx.MockTransport(repondre)

    @property
    def methodes(self):
        return [r.method for r in self.requetes]


def _page(nom):
    return fixtures.charger(nom)


def rechercher(*args, **kwargs):
    """Le client, garde NEUTRALISÉE.

    Ces tests vérifient le PROTOCOLE PRADO ; la cadence, le quota, le verrou
    et l'interrupteur d'arrêt ont leur propre module de tests
    (``test_garde_fous.py``), qui vérifie aussi que la garde par défaut de
    ``rechercher`` est bien la garde RÉELLE — pas celle-ci.
    """
    kwargs.setdefault('garde', portail_client.GardeNeutre())
    return portail_client.rechercher(*args, **kwargs)


def _reponse(corps, statut=200, entetes=None):
    return (statut, corps, entetes)


class IdentiteHonneteTests(SimpleTestCase):
    """La règle de conduite : une identité déclarée, jamais un déguisement."""

    def test_le_user_agent_declare_taqinor_et_un_contact(self):
        ua = portail_client.user_agent()
        self.assertIn('Taqinor', ua)
        self.assertIn('taqinor.ma', ua)

    def test_le_user_agent_ne_ressemble_a_aucun_navigateur(self):
        ua = portail_client.user_agent()
        for jeton in JETONS_NAVIGATEUR:
            self.assertNotIn(jeton.lower(), ua.lower(), jeton)

    def test_une_identite_de_navigateur_est_refusee(self):
        with self.assertRaises(portail_client.MaquillageRefuse):
            portail_client.verifier_identite_honnete(
                'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36')

    def test_le_contact_se_configure_mais_pas_l_identite(self):
        """Seul le CONTACT est paramétrable : le reste du UA est en dur.

        Si l'environnement pouvait réécrire tout le User-Agent, la règle
        « jamais de maquillage » se contournerait par une ligne de ``.env``.
        """
        ancien = os.environ.get('VEILLE_AO_CONTACT')
        os.environ['VEILLE_AO_CONTACT'] = 'veille@exemple.test'
        try:
            self.assertIn('veille@exemple.test', portail_client.user_agent())
            self.assertIn('Taqinor', portail_client.user_agent())
        finally:
            if ancien is None:
                os.environ.pop('VEILLE_AO_CONTACT', None)
            else:
                os.environ['VEILLE_AO_CONTACT'] = ancien


class RefusDuPortailTests(SimpleTestCase):
    """LE test de la tâche : un 403 arrête tout, sans repli déguisé."""

    def test_un_403_arrete_le_client_en_une_seule_requete(self):
        enregistreur = TransportEnregistreur(
            reponses=[_reponse(_page(fixtures.ERREUR_403), statut=403)])
        with GardeReseau():
            with self.assertRaises(portail_client.ClientRefuse) as capture:
                rechercher(
                    SourceFictive(), 'solaire',
                    transport=enregistreur.transport())
        self.assertEqual(len(enregistreur.requetes), 1, enregistreur.methodes)
        self.assertIn('403', str(capture.exception))
        self.assertIn('ARRÊT DÉFINITIF', str(capture.exception))

    def test_aucune_tentative_sous_un_user_agent_de_navigateur(self):
        """La preuve d'ABSENCE : ce qui a été envoyé, et rien d'autre."""
        enregistreur = TransportEnregistreur(
            reponses=[_reponse(_page(fixtures.ERREUR_403), statut=403)])
        with GardeReseau():
            with self.assertRaises(portail_client.ClientRefuse):
                rechercher(
                    SourceFictive(), 'solaire',
                    transport=enregistreur.transport())
        for requete in enregistreur.requetes:
            envoye = requete.headers.get('user-agent', '')
            self.assertIn('Taqinor', envoye)
            for jeton in JETONS_NAVIGATEUR:
                self.assertNotIn(jeton.lower(), envoye.lower(), jeton)

    def test_un_429_est_aussi_un_refus_definitif(self):
        enregistreur = TransportEnregistreur(
            reponses=[_reponse('trop de requêtes', statut=429)])
        with self.assertRaises(portail_client.ClientRefuse):
            rechercher(SourceFictive(), 'solaire',
                       transport=enregistreur.transport())
        self.assertEqual(len(enregistreur.requetes), 1)

    def test_un_500_est_une_indisponibilite_pas_un_refus(self):
        """Les deux ne se réessaient pas de la même façon — on les distingue."""
        enregistreur = TransportEnregistreur(
            reponses=[_reponse('erreur serveur', statut=503)])
        with self.assertRaises(portail_client.PortailIndisponible):
            rechercher(SourceFictive(), 'solaire',
                       transport=enregistreur.transport())

    def test_un_delai_depasse_est_une_indisponibilite_nommee(self):
        def expirer(requete):
            raise httpx.ReadTimeout('délai dépassé', request=requete)

        with self.assertRaises(portail_client.PortailIndisponible):
            rechercher(
                SourceFictive(), 'solaire',
                transport=httpx.MockTransport(expirer))


class RechercheRestreinteTests(SimpleTestCase):
    """Un balayage du portail doit être IMPOSSIBLE À ÉCRIRE, pas déconseillé."""

    def _refuse(self, mot_cle):
        enregistreur = TransportEnregistreur(reponses=[_reponse('', 200)])
        with self.assertRaises(portail_client.RechercheNonRestreinte):
            rechercher(SourceFictive(), mot_cle,
                       transport=enregistreur.transport())
        # Rien n'est parti : la garde s'applique AVANT toute connexion.
        self.assertEqual(enregistreur.requetes, [])

    def test_une_recherche_sans_mot_cle_est_refusee(self):
        self._refuse('')

    def test_une_recherche_a_blanc_est_refusee(self):
        self._refuse('   ')

    def test_un_joker_est_refuse(self):
        self._refuse('*')
        self._refuse('%solaire%')

    def test_un_mot_cle_trop_court_est_refuse(self):
        self._refuse('a')

    def test_les_mots_cles_metier_reels_passent(self):
        for mot in ('solaire', 'photovolta', 'pompage', 'ombrière'):
            with self.subTest(mot=mot):
                self.assertEqual(
                    portail_client.exiger_mot_cle_restrictif(mot), mot)


class SourceInactiveTests(SimpleTestCase):
    """L'interrupteur d'arrêt de la source est un interrupteur RÉEL."""

    def test_une_source_inactive_ne_part_pas(self):
        enregistreur = TransportEnregistreur(reponses=[_reponse('', 200)])
        with self.assertRaises(portail_client.SourceNonCollectable):
            rechercher(
                SourceFictive(actif=False), 'solaire',
                transport=enregistreur.transport())
        self.assertEqual(enregistreur.requetes, [])

    def test_une_source_sans_url_ne_part_pas(self):
        enregistreur = TransportEnregistreur(reponses=[_reponse('', 200)])
        with self.assertRaises(portail_client.SourceNonCollectable):
            rechercher(
                SourceFictive(url_base=''), 'solaire',
                transport=enregistreur.transport())
        self.assertEqual(enregistreur.requetes, [])


class LectureDeLaPageTests(SimpleTestCase):
    """Le compteur et le pagestate, lus sur les fixtures réelles du groupe."""

    def test_le_total_est_lu_sur_la_page_de_resultats(self):
        self.assertEqual(
            portail_client.lire_total(_page(fixtures.RESULTATS_10)), 34)
        self.assertEqual(
            portail_client.lire_total(_page(fixtures.RESULTATS_500)), 34)
        self.assertEqual(
            portail_client.lire_total(_page(fixtures.RESULTATS_VIDE)), 0)

    def test_un_compteur_absent_rend_None_et_non_zero(self):
        """« Introuvable » et « zéro » ne sont pas le même fait."""
        self.assertIsNone(
            portail_client.lire_total(_page(fixtures.RESULTATS_DERIVE)))
        self.assertIsNone(portail_client.lire_total(''))

    def test_le_pagestate_est_desechappe(self):
        brut = _page(fixtures.RESULTATS_10)
        self.assertIn('&#43;', brut)  # la fixture le sert bien échappé
        pagestate = portail_client.lire_pagestate(brut)
        self.assertTrue(pagestate)
        self.assertIn('+', pagestate)
        self.assertNotIn('&#43;', pagestate)
        self.assertNotIn('&amp;', pagestate)

    def test_un_pagestate_absent_rend_None(self):
        self.assertIsNone(
            portail_client.lire_pagestate(_page(fixtures.ERREUR_403)))


class SequenceMesureeTests(SimpleTestCase):
    """Les 3 étapes vérifiées en main le 2026-08-01, rejouées sur fixtures."""

    def test_etape1_seule_quand_le_total_tient_dans_la_page(self):
        enregistreur = TransportEnregistreur(
            reponses=[_reponse(_page(fixtures.RESULTATS_VIDE))])
        with GardeReseau():
            recherche = rechercher(
                SourceFictive(), 'solaire',
                transport=enregistreur.transport())
        self.assertEqual(recherche.total_annonce, 0)
        self.assertEqual(enregistreur.methodes, ['GET'])
        self.assertEqual(recherche.requetes, 1)

    def test_etape2_le_postback_500_quand_le_total_depasse_dix(self):
        enregistreur = TransportEnregistreur(reponses=[
            _reponse(_page(fixtures.RESULTATS_10),
                     entetes={'set-cookie': 'PHPSESSID=abc123; Path=/'}),
            _reponse(_page(fixtures.RESULTATS_500)),
        ])
        with GardeReseau():
            recherche = rechercher(
                SourceFictive(), 'solaire',
                transport=enregistreur.transport())

        self.assertEqual(enregistreur.methodes, ['GET', 'POST'])
        self.assertEqual(recherche.total_annonce, 34)
        self.assertEqual(recherche.requetes, 2)

        get, post = enregistreur.requetes
        # Même URL, exactement.
        self.assertEqual(str(get.url), str(post.url))
        # Même jarre de cookies : le POST n'est servi qu'avec le PHPSESSID du GET.
        self.assertIn('PHPSESSID=abc123', post.headers.get('cookie', ''))

        corps = post.content.decode('utf-8')
        self.assertIn('PRADO_PAGESTATE=', corps)
        self.assertIn('listePageSizeTop', corps)
        self.assertIn('500', corps)

    def test_le_postback_rejoue_le_pagestate_desechappe(self):
        enregistreur = TransportEnregistreur(reponses=[
            _reponse(_page(fixtures.RESULTATS_10)),
            _reponse(_page(fixtures.RESULTATS_500)),
        ])
        rechercher(SourceFictive(), 'solaire',
                   transport=enregistreur.transport())
        envoye = dict(
            httpx.QueryParams(enregistreur.requetes[1].content.decode('utf-8')))
        attendu = portail_client.lire_pagestate(_page(fixtures.RESULTATS_10))
        self.assertEqual(envoye['PRADO_PAGESTATE'], attendu)
        self.assertEqual(envoye['PRADO_POSTBACK_TARGET'],
                         portail_client.CIBLE_TAILLE_PAGE)
        self.assertEqual(envoye['PRADO_POSTBACK_PARAMETER'], '')
        self.assertEqual(envoye[portail_client.CIBLE_TAILLE_PAGE],
                         str(portail_client.TAILLE_PAGE_MAX))

    def test_etape3_page_suivante_avec_le_NOUVEAU_pagestate(self):
        """Le mécanisme de la page 2 : nouveau pagestate + numPageTop.

        700 résultats = 2 pages de 500 → GET, postback (page 1), page 2.
        """
        page1 = _page(fixtures.RESULTATS_10).replace('>34<', '>700<')
        page500 = _page(fixtures.RESULTATS_500).replace('>34<', '>700<')
        page500_bis = page500.replace('c29sYWlyZS0yMDI2LTA4LTAx',
                                      'UEFHRS1TVUlWQU5URQ')
        enregistreur = TransportEnregistreur(reponses=[
            _reponse(page1), _reponse(page500_bis), _reponse(page500),
        ])
        with GardeReseau():
            recherche = rechercher(
                SourceFictive(), 'solaire',
                transport=enregistreur.transport())

        self.assertEqual(enregistreur.methodes, ['GET', 'POST', 'POST'])
        self.assertEqual(recherche.requetes, 3)

        page2 = dict(
            httpx.QueryParams(enregistreur.requetes[2].content.decode('utf-8')))
        self.assertEqual(page2[portail_client.CIBLE_NUMERO_PAGE], '2')
        # Le pagestate rejoué est celui de la RÉPONSE PRÉCÉDENTE, pas du GET.
        self.assertEqual(page2['PRADO_PAGESTATE'],
                         portail_client.lire_pagestate(page500_bis))
        self.assertNotEqual(page2['PRADO_PAGESTATE'],
                            portail_client.lire_pagestate(page1))

    def test_le_plafond_de_pages_tronque_mais_le_DIT(self):
        """Au-delà de 3 pages, on ne pagine pas en silence : on le signale."""
        page1 = _page(fixtures.RESULTATS_10).replace('>34<', '>3380<')
        page500 = _page(fixtures.RESULTATS_500).replace('>34<', '>3380<')
        enregistreur = TransportEnregistreur(reponses=[
            _reponse(page1)] + [_reponse(page500)] * 6)
        recherche = rechercher(
            SourceFictive(), 'solaire', transport=enregistreur.transport())
        self.assertTrue(recherche.tronquee)
        self.assertLessEqual(recherche.requetes,
                             portail_client.PAGES_MAX + 1)

    def test_un_compteur_introuvable_est_une_erreur_pas_un_vide(self):
        enregistreur = TransportEnregistreur(
            reponses=[_reponse(_page(fixtures.RESULTATS_DERIVE))])
        with self.assertRaises(portail_client.ReponseInattendue):
            rechercher(SourceFictive(), 'solaire',
                       transport=enregistreur.transport())

    def test_un_pagestate_absent_est_une_erreur_nommee(self):
        sans_pagestate = _page(fixtures.RESULTATS_10).replace(
            'PRADO_PAGESTATE', 'PRADO_AUTRE_CHOSE')
        enregistreur = TransportEnregistreur(
            reponses=[_reponse(sans_pagestate)])
        with self.assertRaises(portail_client.ReponseInattendue) as capture:
            rechercher(SourceFictive(), 'solaire',
                       transport=enregistreur.transport())
        self.assertIn('PAGESTATE', str(capture.exception).upper())

    def test_chaque_requete_passe_par_la_garde(self):
        """Chaque aller-retour réseau passe par la garde, sans exception.

        C'est la prise sur laquelle VAO19 branche la cadence, le quota et
        l'interrupteur : une requête qui la contournerait échapperait à TOUTES
        les mitigations d'un coup.
        """

        class GardeCompteuse(portail_client.GardeNeutre):
            def __init__(self):
                self.appels = []

            def avant_requete(self, description=''):
                self.appels.append(description)

        garde = GardeCompteuse()
        enregistreur = TransportEnregistreur(reponses=[
            _reponse(_page(fixtures.RESULTATS_10)),
            _reponse(_page(fixtures.RESULTATS_500)),
        ])
        rechercher(SourceFictive(), 'solaire', garde=garde,
                   transport=enregistreur.transport())
        self.assertEqual(len(garde.appels), 2)


class UrlDeRechercheTests(SimpleTestCase):
    """L'URL est CONSTRUITE depuis la source — jamais écrite dans le code."""

    def test_l_url_vient_de_la_source(self):
        url = portail_client.url_de_recherche('https://autre.test.invalid/',
                                              'solaire')
        self.assertTrue(url.startswith('https://autre.test.invalid/index.php'))

    def test_entreprise_est_en_minuscules(self):
        """Mesuré : une majuscule rend un 404."""
        url = portail_client.url_de_recherche(URL_BASE, 'solaire')
        self.assertIn('page=entreprise.EntrepriseAdvancedSearch', url)
        self.assertNotIn('page=Entreprise.', url)

    def test_les_trois_drapeaux_restent_sans_valeur(self):
        url = portail_client.url_de_recherche(URL_BASE, 'solaire')
        for drapeau in ('&AllCons', '&EnCours', '&searchAnnCons'):
            self.assertIn(drapeau, url)
            self.assertNotIn(drapeau + '=', url)

    def test_aucun_parametre_de_date(self):
        """Mesuré : ignorés en GET, peu fiables par formulaire. On s'abstient."""
        url = portail_client.url_de_recherche(URL_BASE, 'solaire')
        for interdit in ('dateMiseEnLigne', 'dateFin', 'dateDebut'):
            self.assertNotIn(interdit, url)

    def test_le_mot_cle_est_encode(self):
        url = portail_client.url_de_recherche(URL_BASE, 'pompage solaire')
        self.assertIn('keyWord=pompage%20solaire', url)

    def test_aucune_url_de_portail_en_dur_dans_le_module(self):
        """La SEULE adresse écrite dans le module est notre propre contact.

        L'adresse du portail vit en base (``SourceVeille.url_base``) : c'est ce
        qui permet d'ajouter MASEN, la CDG ou Marsa Maroc — qui tournent le
        même logiciel Atexo — sans toucher une ligne du collecteur.
        """
        source = Path(portail_client.__file__).read_text(encoding='utf-8')
        adresses = set(re.findall(r'https?://[^\s\'"`,)]+', source))
        etrangeres = {a for a in adresses
                      if not a.startswith(portail_client.CONTACT_DEFAUT)}
        self.assertEqual(etrangeres, set(),
                         f'URL étrangère écrite en dur : {sorted(etrangeres)}')
        for interdit in ('marchespublics.gov.ma', '.gov.ma', 'sslip'):
            self.assertNotIn(interdit, source, f'« {interdit} » en dur')


class IntegrationReseauTests(SimpleTestCase):
    """Le SEUL test qui parlerait au portail — désarmé par défaut.

    Il ne s'exécute que si ``VEILLE_AO_TEST_RESEAU=1`` est posé À LA MAIN, ce
    qui n'arrive ni en CI ni dans un run d'agent. Tant que la ligne « Founder
    approval » de ``tos_risk/marchespublics_gov_ma.md`` est vide, l'exécuter
    serait une violation de la règle #5 : c'est la tâche VAO4 qui l'autorise,
    et elle appartient au fondateur seul.
    """

    @unittest.skipUnless(
        os.environ.get('VEILLE_AO_TEST_RESEAU') == '1',
        'Test réseau désarmé (règle #5 — armement fondateur, VAO4).')
    def test_la_sequence_contre_le_portail_reel(self):  # pragma: no cover
        url_base = os.environ.get('VEILLE_AO_URL_BASE', '')
        self.assertTrue(
            url_base,
            "VEILLE_AO_URL_BASE doit être posée à la main : aucune adresse de "
            'portail ne vit dans le code.')
        recherche = rechercher(
            SourceFictive(url_base=url_base), 'solaire')
        self.assertIsNotNone(recherche.total_annonce)
        self.assertTrue(recherche.pages)
