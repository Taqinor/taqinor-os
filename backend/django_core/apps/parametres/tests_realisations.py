"""Catalogue « Réalisations » — le modèle, l'API et le CHOIX de la preuve.

Ordre fondateur du 08/09/2026 : la touche J4 ne promet plus une preuve qu'elle
n'a pas. Ce fichier verrouille les trois garanties qui font que le message
reste vrai :

  1. **une réalisation = une installation réelle**, décrite par une ville
     CANONISÉE (« belksiri » → « Mechraa Bel Ksiri ») et un mois — jamais un
     jour inventé ;
  2. **le choix est géographique, pas décoratif** : même ville d'abord, sinon
     la plus proche dans le rayon, sinon RIEN (une installation à 400 km n'est
     pas « comparable à la vôtre ») ;
  3. **cloisonnement société** : le catalogue d'une société n'est ni lisible ni
     modifiable par une autre, et `company` n'est jamais lue du corps.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from apps.parametres.models_realisations import Realisation
from apps.parametres.selectors import RAYON_PREUVE_KM, realisation_pour_lead

User = get_user_model()

URL = '/api/django/parametres/realisations/'


#: Suffixe d'URL unique par ligne créée dans les tests. Un compteur en mémoire
#: plutôt qu'un `count()` en base : l'unicité `(company, url_page)` doit être
#: satisfaite sans dépendre de l'état de la table.
_SUITE_URL = itertools.count(1)


def _societe(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def _realisation(company, ville, **kwargs):
    kwargs.setdefault('titre', f'Chantier {ville}')
    kwargs.setdefault(
        'url_page',
        f'https://taqinor.ma/realisations/r-{next(_SUITE_URL)}/')
    return Realisation.objects.create(company=company, ville=ville, **kwargs)


class ModeleTests(TestCase):
    """Ce que le modèle NORMALISE tout seul, sur tous les chemins d'écriture."""

    def setUp(self):
        self.company = _societe('real-modele')

    def test_la_ville_est_canonisee_a_l_enregistrement(self):
        """Sans ça, une réalisation saisie « belksiri » ne serait jamais
        appariée au lead de « Mechraa Bel Ksiri » : deux graphies, aucune
        preuve envoyée."""
        realisation = _realisation(self.company, 'belksiri')
        realisation.refresh_from_db()
        self.assertEqual(realisation.ville, 'Mechraa Bel Ksiri')

    def test_une_ville_inconnue_est_conservee_telle_quelle(self):
        """Règle « zéro fait inventé » : le gazetier ne devine pas un douar."""
        realisation = _realisation(self.company, 'Douar Zaouiat Lakhmiss 42')
        realisation.refresh_from_db()
        self.assertEqual(realisation.ville, 'Douar Zaouiat Lakhmiss 42')

    def test_la_mise_en_service_est_ramenee_au_premier_du_mois(self):
        """Le message ne dit jamais mieux que le mois : stocker le 18 laisserait
        croire à une précision qu'on n'affiche pas."""
        realisation = _realisation(
            self.company, 'Casablanca',
            mise_en_service=datetime.date(2026, 7, 18))
        realisation.refresh_from_db()
        self.assertEqual(realisation.mise_en_service,
                         datetime.date(2026, 7, 1))

    def test_une_mise_en_service_absente_le_reste(self):
        realisation = _realisation(self.company, 'Casablanca')
        realisation.refresh_from_db()
        self.assertIsNone(realisation.mise_en_service)
        self.assertIsNone(realisation.puissance_kwc)


class ApiTests(TestCase):
    """Cloisonnement société + `company` jamais lue du corps."""

    def setUp(self):
        self.company = _societe('real-api')
        self.autre = _societe('real-api-autre')
        self.admin = User.objects.create_user(
            username='real-admin', password='x', role_legacy='admin',
            company=self.company)
        self.voisin = User.objects.create_user(
            username='real-voisin', password='x', role_legacy='admin',
            company=self.autre)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _api_voisin(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.voisin)}')
        return api

    def test_creation_force_la_societe_du_demandeur(self):
        """`company` envoyée dans le corps est IGNORÉE (elle ne fait même pas
        partie du sérialiseur) : la ligne appartient au demandeur."""
        resp = self.api.post(URL, {
            'titre': 'Villa à Bouskoura',
            'ville': 'Bouskoura',
            'url_page': 'https://taqinor.ma/realisations/villa-bouskoura/',
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('company', resp.data)
        realisation = Realisation.objects.get(pk=resp.data['id'])
        self.assertEqual(realisation.company_id, self.company.id)

    def test_la_ville_envoyee_par_l_api_est_canonisee(self):
        resp = self.api.post(URL, {
            'titre': 'Ferme',
            'ville': 'belksiri',
            'url_page': 'https://taqinor.ma/realisations/ferme-bk/',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Realisation.objects.get(pk=resp.data['id']).ville,
            'Mechraa Bel Ksiri')

    def test_une_autre_societe_ne_voit_pas_le_catalogue(self):
        _realisation(self.company, 'Casablanca')
        resp = self._api_voisin().get(URL)
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data if isinstance(resp.data, list) else resp.data[
            'results']
        self.assertEqual(lignes, [])

    def test_une_autre_societe_ne_peut_pas_modifier(self):
        realisation = _realisation(self.company, 'Casablanca')
        resp = self._api_voisin().patch(
            f'{URL}{realisation.pk}/', {'titre': 'Détourné'}, format='json')
        self.assertEqual(resp.status_code, 404)
        realisation.refresh_from_db()
        self.assertNotEqual(realisation.titre, 'Détourné')

    def test_filtre_actif(self):
        _realisation(self.company, 'Casablanca', actif=False)
        vivante = _realisation(self.company, 'Mohammedia')
        resp = self.api.get(URL, {'actif': 'true'})
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data if isinstance(resp.data, list) else resp.data[
            'results']
        self.assertEqual([r['id'] for r in lignes], [vivante.pk])

    def test_la_date_de_creation_est_exposee(self):
        """`date_creation` = `created_at` du socle, exposé sous son nom métier
        (aucune colonne d'horodatage dupliquée)."""
        realisation = _realisation(self.company, 'Casablanca')
        resp = self.api.get(f'{URL}{realisation.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['date_creation'])


class SelecteurTests(TestCase):
    """Le CHOIX de la preuve : même ville d'abord, puis la plus proche."""

    def setUp(self):
        self.company = _societe('real-selecteur')
        self.autre = _societe('real-selecteur-autre')

    def _lead(self, **kwargs):
        kwargs.setdefault('nom', 'Benali')
        kwargs.setdefault('telephone', '+212651971400')
        return Lead.objects.create(company=self.company, **kwargs)

    def test_la_meme_ville_prime_sur_la_plus_proche(self):
        """Bouskoura est à 16 km de Casablanca : sans la règle « même ville »
        elle gagnerait, alors que le lead EST à Casablanca."""
        proche = _realisation(self.company, 'Bouskoura')
        meme = _realisation(self.company, 'Casablanca')
        choisie = realisation_pour_lead(self._lead(ville='Casablanca'))
        self.assertEqual(choisie, meme)
        self.assertNotEqual(choisie, proche)

    def test_la_ville_de_rattachement_prime_sur_la_ville_tapee(self):
        """VREF : le client tape son douar, Meryem rattache la ville ERP —
        c'est le rattachement qui décide de la preuve."""
        _realisation(self.company, 'Casablanca')
        agadir = _realisation(self.company, 'Agadir')
        lead = self._lead(ville='Douar Zaouiat Lakhmiss 42',
                          ville_reference='Agadir')
        self.assertEqual(realisation_pour_lead(lead), agadir)

    def test_a_defaut_la_plus_proche_dans_le_rayon(self):
        """Mohammedia est à 24 km de Casablanca — dans le rayon."""
        voisine = _realisation(self.company, 'Mohammedia')
        self.assertEqual(realisation_pour_lead(self._lead(ville='Casablanca')),
                         voisine)

    def test_la_plus_proche_gagne_sur_une_autre_du_rayon(self):
        _realisation(self.company, 'Mohammedia')          # 24 km
        bouskoura = _realisation(self.company, 'Bouskoura')  # 16 km
        self.assertEqual(realisation_pour_lead(self._lead(ville='Casablanca')),
                         bouskoura)

    def test_rien_au_dela_du_rayon(self):
        """Settat est à 65 km de Casablanca (rayon = 60) : au-delà, « une
        installation comparable à la vôtre » deviendrait faux — on préfère
        n'envoyer aucune preuve."""
        self.assertEqual(RAYON_PREUVE_KM, 60)
        _realisation(self.company, 'Settat')
        _realisation(self.company, 'Agadir')
        self.assertIsNone(realisation_pour_lead(self._lead(ville='Casablanca')))

    def test_une_realisation_inactive_est_ignoree(self):
        _realisation(self.company, 'Casablanca', actif=False)
        self.assertIsNone(realisation_pour_lead(self._lead(ville='Casablanca')))

    def test_entre_plusieurs_de_la_meme_ville_la_plus_recente(self):
        _realisation(self.company, 'Casablanca',
                     mise_en_service=datetime.date(2025, 3, 1))
        recente = _realisation(self.company, 'Casablanca',
                               mise_en_service=datetime.date(2026, 7, 1))
        self.assertEqual(realisation_pour_lead(self._lead(ville='Casablanca')),
                         recente)

    def test_un_lead_sans_ville_ne_recoit_aucune_preuve(self):
        """« Comparable à la vôtre » est une affirmation géographique : sans
        ville, on ne la fait pas au hasard."""
        _realisation(self.company, 'Casablanca')
        self.assertIsNone(realisation_pour_lead(self._lead()))

    def test_le_catalogue_d_une_autre_societe_n_est_jamais_servi(self):
        _realisation(self.autre, 'Casablanca')
        self.assertIsNone(realisation_pour_lead(self._lead(ville='Casablanca')))
