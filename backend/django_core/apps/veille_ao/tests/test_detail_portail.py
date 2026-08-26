"""VAO18 — l'enrichissement du détail : à la demande, et qui échoue PROPREMENT.

Trois promesses de la tâche, trois familles de tests :
  1. l'enrichissement lit bien la fixture de détail (estimation, caution,
     lots, marqueur PME, lien DCE + taille) ;
  2. **un délai dépassé laisse l'avis INTACT** — ``donnees`` vide, message
     « Détail indisponible, réessayer » — après 2-3 tentatives à repli
     exponentiel, et sans dormir pour de vrai dans le test ;
  3. **aucun appel de détail depuis la tâche planifiée** : un test
     d'introspection relit l'arbre syntaxique de ``tasks.py`` et de
     ``services.py`` et rougit si l'un d'eux touche à ``portail.detail``.

Le téléchargement du DCE reste hors périmètre : on vérifie que le lien est
RENDU, pas qu'il est suivi.
"""
from __future__ import annotations

import ast
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
from django.test import SimpleTestCase

from apps.veille_ao.portail import client as portail_client
from apps.veille_ao.portail import detail as portail_detail
from apps.veille_ao.portail import fixtures
from apps.veille_ao.tests.test_purete_portail import GardeReseau

URL_BASE = 'https://portail.test.invalid'
APP = Path(portail_detail.__file__).resolve().parent.parent


@dataclass
class SourceFictive:
    libelle: str = 'Portail de test'
    url_base: str = URL_BASE
    actif: bool = True


class Dormeur:
    """Un ``time.sleep`` de test : il NOTE l'attente au lieu de la subir."""

    def __init__(self):
        self.attentes = []

    def __call__(self, secondes):
        self.attentes.append(secondes)


class LectureMontantTests(SimpleTestCase):
    def test_le_format_marocain_est_lu_en_decimal(self):
        self.assertEqual(portail_detail.lire_montant('2 450 000,00 MAD TTC'),
                         Decimal('2450000.00'))

    def test_les_points_de_milliers_aussi(self):
        self.assertEqual(portail_detail.lire_montant('2.450.000,00 MAD'),
                         Decimal('2450000.00'))

    def test_un_montant_sans_decimale(self):
        self.assertEqual(portail_detail.lire_montant('35 000 MAD'),
                         Decimal('35000'))

    def test_un_texte_sans_montant_rend_None(self):
        """« Non communiqué » n'est pas zéro — un zéro inventé serait un chiffre
        faux dans un dossier d'appel d'offres."""
        self.assertIsNone(portail_detail.lire_montant('Non communiqué'))
        self.assertIsNone(portail_detail.lire_montant(''))

    def test_le_resultat_est_un_Decimal_jamais_un_float(self):
        self.assertIsInstance(portail_detail.lire_montant('1 000,50 MAD'),
                              Decimal)


class AnalyseDuDetailTests(SimpleTestCase):
    """La fixture de détail, lue champ par champ (aucun réseau)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with GardeReseau():
            cls.detail = portail_detail.analyser_detail(
                fixtures.charger(fixtures.DETAIL))

    def test_l_estimation_et_la_caution_sont_lues(self):
        self.assertEqual(self.detail.donnees['montant_estime'],
                         Decimal('2450000.00'))
        self.assertEqual(self.detail.donnees['caution_provisoire'],
                         Decimal('35000.00'))

    def test_la_date_d_ouverture_est_AWARE(self):
        ouverture = self.detail.donnees['date_ouverture']
        self.assertEqual(ouverture.hour, 10)
        self.assertEqual(ouverture.minute, 30)
        self.assertIsNotNone(ouverture.tzinfo)

    def test_la_date_limite_est_lue_aussi(self):
        self.assertEqual(
            self.detail.donnees['date_limite_remise'].astimezone(
                dt.timezone.utc).hour, 9)

    def test_les_deux_lots_sont_lus_avec_leurs_montants(self):
        self.assertEqual(len(self.detail.lots), 2)
        premier = self.detail.lots[0]
        self.assertEqual(premier.numero, '1')
        self.assertEqual(premier.intitule, 'Fourniture des modules et onduleurs')
        self.assertEqual(premier.estimation, Decimal('1700000.00'))
        self.assertEqual(premier.caution, Decimal('25000.00'))

    def test_le_champ_lot_reste_vide_quand_il_y_a_PLUSIEURS_lots(self):
        """Écrire « 1 » sur un avis à deux lots serait une donnée fausse."""
        self.assertNotIn('lot', self.detail.donnees)

    def test_le_marqueur_pme_est_lu(self):
        self.assertIs(self.detail.reserve_pme, True)

    def test_une_page_muette_sur_les_pme_rend_None_et_non_False(self):
        page = fixtures.charger(fixtures.DETAIL).replace(
            'marqueur-pme', 'autre-chose').replace('Réservé aux PME', 'Divers')
        self.assertIsNone(portail_detail.analyser_detail(page).reserve_pme)

    def test_le_lien_du_dce_et_sa_taille_sont_rendus_pas_suivis(self):
        self.assertIn('TelechargementDce', self.detail.lien_dce)
        self.assertEqual(self.detail.taille_dce, '18,4 Mo')

    def test_les_cles_rendues_sont_enregistrables(self):
        from apps.veille_ao.services import CHAMPS_RECTIFIABLES
        for cle in self.detail.donnees:
            with self.subTest(cle=cle):
                self.assertIn(cle, CHAMPS_RECTIFIABLES)

    def test_une_page_sans_aucune_ancre_est_une_derive_nommee(self):
        with self.assertRaises(portail_client.ReponseInattendue):
            portail_detail.analyser_detail(
                '<html><body><p>Bonjour</p></body></html>')


class EnrichissementTests(SimpleTestCase):
    """Le chemin complet, contre un transport bouchonné."""

    def _transport(self, *reponses):
        etat = {'i': 0}

        def repondre(requete):
            indice = min(etat['i'], len(reponses) - 1)
            etat['i'] += 1
            fabrique = reponses[indice]
            if callable(fabrique):
                return fabrique(requete)
            return fabrique

        return httpx.MockTransport(repondre)

    def test_le_detail_est_lu_en_une_tentative(self):
        with GardeReseau():
            detail = portail_detail.enrichir(
                SourceFictive(), '812340', 'k1z',
                transport=self._transport(httpx.Response(
                    200, text=fixtures.charger(fixtures.DETAIL))))
        self.assertTrue(detail.disponible)
        self.assertEqual(detail.tentatives, 1)
        self.assertEqual(detail.donnees['montant_estime'], Decimal('2450000.00'))

    def test_l_url_porte_les_deux_identifiants(self):
        url = portail_detail.url_de_detail(URL_BASE, '812340', 'k1z')
        self.assertIn('refConsultation=812340', url)
        self.assertIn('orgAcronyme=k1z', url)
        self.assertIn('page=entreprise.EntrepriseDetailConsultation', url)
        self.assertNotIn('page=Entreprise.', url)

    def test_un_delai_depasse_laisse_l_avis_INTACT(self):
        """La promesse centrale : aucune donnée rendue, donc rien à écraser."""
        def expirer(requete):
            raise httpx.ReadTimeout('délai dépassé', request=requete)

        dormeur = Dormeur()
        detail = portail_detail.enrichir(
            SourceFictive(), '812340', 'k1z',
            transport=httpx.MockTransport(expirer), dormir=dormeur)

        self.assertFalse(detail.disponible)
        self.assertEqual(detail.donnees, {})
        self.assertEqual(detail.lots, [])
        self.assertEqual(detail.message, portail_detail.MESSAGE_INDISPONIBLE)
        self.assertIn('réessayer', detail.message)

    def test_trois_tentatives_a_repli_exponentiel(self):
        def expirer(requete):
            raise httpx.ReadTimeout('délai dépassé', request=requete)

        dormeur = Dormeur()
        detail = portail_detail.enrichir(
            SourceFictive(), '812340', 'k1z',
            transport=httpx.MockTransport(expirer), dormir=dormeur)

        self.assertEqual(detail.tentatives, portail_detail.TENTATIVES)
        # 2 attentes pour 3 tentatives, et la seconde vaut le double.
        self.assertEqual(dormeur.attentes,
                         [portail_detail.REPLI_INITIAL,
                          portail_detail.REPLI_INITIAL * 2])

    def test_une_seconde_tentative_qui_reussit_rend_les_donnees(self):
        def expirer(requete):
            raise httpx.ReadTimeout('délai dépassé', request=requete)

        dormeur = Dormeur()
        detail = portail_detail.enrichir(
            SourceFictive(), '812340', 'k1z',
            transport=self._transport(
                expirer,
                httpx.Response(200, text=fixtures.charger(fixtures.DETAIL))),
            dormir=dormeur)
        self.assertTrue(detail.disponible)
        self.assertEqual(detail.tentatives, 2)
        self.assertEqual(dormeur.attentes, [portail_detail.REPLI_INITIAL])

    def test_un_refus_n_est_JAMAIS_reessaye(self):
        """403 = arrêt définitif (VAO16) : marteler serait le contraire."""
        appels = []

        def refuser(requete):
            appels.append(requete)
            return httpx.Response(
                403, text=fixtures.charger(fixtures.ERREUR_403))

        dormeur = Dormeur()
        detail = portail_detail.enrichir(
            SourceFictive(), '812340', 'k1z',
            transport=httpx.MockTransport(refuser), dormir=dormeur)

        self.assertEqual(len(appels), 1)
        self.assertEqual(dormeur.attentes, [])
        self.assertFalse(detail.disponible)
        self.assertEqual(detail.cause, 'ClientRefuse')

    def test_une_source_inactive_n_appelle_rien(self):
        appels = []

        def repondre(requete):
            appels.append(requete)
            return httpx.Response(200, text='')

        detail = portail_detail.enrichir(
            SourceFictive(actif=False), '812340', 'k1z',
            transport=httpx.MockTransport(repondre))
        self.assertFalse(detail.disponible)
        self.assertEqual(appels, [])

    def test_le_user_agent_reste_honnete_sur_le_detail(self):
        envoyes = []

        def repondre(requete):
            envoyes.append(requete.headers.get('user-agent', ''))
            return httpx.Response(200, text=fixtures.charger(fixtures.DETAIL))

        portail_detail.enrichir(SourceFictive(), '812340', 'k1z',
                                transport=httpx.MockTransport(repondre))
        self.assertIn('Taqinor', envoyes[0])
        for jeton in ('mozilla', 'chrome', 'safari'):
            self.assertNotIn(jeton, envoyes[0].lower())


class AucunAppelDeDetailEnMasseTests(SimpleTestCase):
    """Le test d'introspection : la tâche planifiée ne touche pas au détail.

    C'est la garde qui empêche la dérive la plus tentante — « tant qu'à
    collecter, autant enrichir tout de suite ». 34 appels sur un point de
    terminaison qui met 110 s à répondre, c'est une collecte qui ne finit
    jamais et un pare-feu qui nous voit marteler.
    """

    FICHIERS_DE_COLLECTE = ('tasks.py', 'services.py', 'portail/client.py')

    def _references(self, chemin):
        """Les noms de modules/attributs cités par un fichier, à plat."""
        arbre = ast.parse(Path(chemin).read_text(encoding='utf-8'))
        cites = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                cites.update(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                base = noeud.module or ''
                cites.add(base)
                cites.update(f'{base}.{alias.name}' for alias in noeud.names)
            elif isinstance(noeud, ast.Attribute):
                cites.add(noeud.attr)
            elif isinstance(noeud, ast.Name):
                cites.add(noeud.id)
        return cites

    def test_aucun_fichier_de_collecte_n_appelle_le_detail(self):
        for nom in self.FICHIERS_DE_COLLECTE:
            with self.subTest(fichier=nom):
                cites = self._references(APP / nom)
                self.assertNotIn('enrichir', cites)
                self.assertFalse(
                    any(reference.endswith('portail.detail')
                        or reference.endswith('.detail')
                        for reference in cites),
                    f'{nom} référence le module de détail : '
                    "l'enrichissement se fait sur CLIC, jamais en masse.")

    def test_la_garde_sait_rougir(self):
        """Une garde qu'on ne teste pas à l'envers finit verte pour rien."""
        faux = ast.parse('from .portail.detail import enrichir\n')
        cites = set()
        for noeud in ast.walk(faux):
            if isinstance(noeud, ast.ImportFrom):
                base = noeud.module or ''
                cites.add(base)
                cites.update(f'{base}.{alias.name}' for alias in noeud.names)
        self.assertIn('portail.detail', cites)
        self.assertIn('portail.detail.enrichir', cites)
