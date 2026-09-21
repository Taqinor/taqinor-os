"""NTDATA20 — file de revue des doublons (jamais de fusion silencieuse).

Couvre :
  * le critère d'acceptation : une proposition IGNORÉE ne réapparaît pas au
    prochain scan ;
  * le scan crée une proposition `en_attente` par groupe détecté, et ne
    duplique pas au second passage ;
  * l'empreinte est STABLE quel que soit l'ordre des identifiants ;
  * `fusionner` délègue à la fusion supervisée existante et journalise ;
  * une proposition déjà tranchée refuse une seconde décision ;
  * fusionner vers une fiche HORS du groupe est refusé ;
  * le scoping société ;
  * les endpoints `/dataquality/fusions/` (+ actions) et le refus d'un
    utilisateur non responsable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.models import GoldenRecord, PropositionFusion
from apps.dataquality.views import PropositionFusionViewSet
from authentication.models import Company

User = get_user_model()
CLIENT = GoldenRecord.Entite.CLIENT


class FileFusionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA20 SA',
                                             slug='ntdata20-sa')
        cls.autre = Company.objects.create(nom='NTDATA20 Autre',
                                           slug='ntdata20-autre')
        cls.user = User.objects.create_user(
            username='ntdata20_u', password='x', company=cls.company,
            role_legacy='admin')

    def _deux_clients(self, company=None, ice='001234567000089'):
        company = company or self.company
        premier = Client.objects.create(
            company=company, nom='Atlas Energie', ice=ice,
            telephone='0600000001')
        second = Client.objects.create(
            company=company, nom='ATLAS ENERGIE SARL', ice=ice,
            email='contact@atlas.ma')
        return premier, second

    # ── Scan ───────────────────────────────────────────────────────────────
    def test_scan_cree_une_proposition_en_attente(self):
        premier, second = self._deux_clients()
        nouvelles = services.scanner_propositions(self.company, CLIENT,
                                                  self.user)
        self.assertEqual(len(nouvelles), 1)
        proposition = nouvelles[0]
        self.assertEqual(proposition.statut,
                         PropositionFusion.Statut.EN_ATTENTE)
        self.assertEqual(proposition.ids_groupe,
                         sorted([premier.pk, second.pk]))
        self.assertIn('ice', proposition.motifs)
        self.assertFalse(proposition.est_tranchee)

    def test_second_scan_ne_duplique_pas(self):
        self._deux_clients()
        services.scanner_propositions(self.company, CLIENT, self.user)
        nouvelles = services.scanner_propositions(self.company, CLIENT,
                                                  self.user)
        self.assertEqual(nouvelles, [])
        self.assertEqual(
            PropositionFusion.objects.filter(company=self.company).count(), 1)

    def test_proposition_ignoree_ne_reapparait_pas(self):
        """Critère d'acceptation de NTDATA20."""
        self._deux_clients()
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.user)[0]
        services.ignorer_proposition(proposition, self.user)

        nouvelles = services.scanner_propositions(self.company, CLIENT,
                                                  self.user)
        self.assertEqual(nouvelles, [])
        self.assertEqual(
            services.propositions_en_attente(self.company).count(), 0)
        proposition.refresh_from_db()
        self.assertEqual(proposition.statut,
                         PropositionFusion.Statut.IGNORE)
        self.assertEqual(proposition.decideur_id, self.user.pk)
        self.assertIsNotNone(proposition.decide_le)

    def test_ignorer_ne_touche_aucune_fiche(self):
        premier, second = self._deux_clients()
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.user)[0]
        services.ignorer_proposition(proposition, self.user)
        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(premier.avertissement_bloquant)
        self.assertFalse(second.avertissement_bloquant)
        self.assertEqual(premier.nom, 'Atlas Energie')
        self.assertEqual(second.nom, 'ATLAS ENERGIE SARL')

    def test_empreinte_stable_quel_que_soit_l_ordre(self):
        self.assertEqual(PropositionFusion.empreinte_de([3, 1, 2]),
                         PropositionFusion.empreinte_de([1, 2, 3]))

    def test_scoping_societe(self):
        self._deux_clients(company=self.autre)
        self.assertEqual(
            services.scanner_propositions(self.company, CLIENT, self.user),
            [])

    def test_entite_inconnue_refusee_en_francais(self):
        with self.assertRaises(ValueError) as leve:
            services.scanner_propositions(self.company, 'licorne', self.user)
        self.assertIn('licorne', str(leve.exception))

    # ── Décisions ──────────────────────────────────────────────────────────
    def test_fusionner_delegue_et_journalise(self):
        premier, second = self._deux_clients()
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.user)[0]
        proposition, rapport = services.fusionner_proposition(
            proposition, self.user, premier.pk)

        self.assertEqual(proposition.statut,
                         PropositionFusion.Statut.FUSIONNE)
        self.assertEqual(proposition.detail_decision['survivant'], premier.pk)
        self.assertEqual(rapport['survivant'].pk, premier.pk)
        # Le doublon est NEUTRALISÉ (avertissement bloquant), jamais supprimé.
        second.refresh_from_db()
        self.assertTrue(second.avertissement_bloquant)
        self.assertEqual((second.custom_data or {}).get('fusionne_dans'),
                         premier.pk)

    def test_une_proposition_tranchee_refuse_une_seconde_decision(self):
        premier, _second = self._deux_clients()
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.user)[0]
        services.ignorer_proposition(proposition, self.user)
        with self.assertRaises(ValueError):
            services.ignorer_proposition(proposition, self.user)
        with self.assertRaises(ValueError):
            services.fusionner_proposition(proposition, self.user,
                                           premier.pk)

    def test_survivant_hors_du_groupe_refuse(self):
        self._deux_clients()
        etranger = Client.objects.create(company=self.company, nom='Ailleurs')
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.user)[0]
        with self.assertRaises(ValueError) as leve:
            services.fusionner_proposition(proposition, self.user,
                                           etranger.pk)
        self.assertIn(str(etranger.pk), str(leve.exception))


class FileFusionEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA20 API',
                                             slug='ntdata20-api')
        cls.responsable = User.objects.create_user(
            username='ntdata20_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata20_simple', password='x', company=cls.company,
            role_legacy='normal')
        cls.premier = Client.objects.create(
            company=cls.company, nom='Atlas Energie',
            ice='001234567000089', telephone='0600000001')
        cls.second = Client.objects.create(
            company=cls.company, nom='ATLAS ENERGIE SARL',
            ice='001234567000089', email='contact@atlas.ma')

    def _appel(self, methode, chemin, vue, user=None, data=None, **kwargs):
        fabrique = APIRequestFactory()
        requete = getattr(fabrique, methode)(chemin, data, format='json')
        force_authenticate(requete, user=user or self.responsable)
        return vue(requete, **kwargs)

    def test_scanner_puis_lister(self):
        reponse = self._appel(
            'post', '/api/django/dataquality/fusions/scanner/',
            PropositionFusionViewSet.as_view({'post': 'scanner'}))
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['nouvelles'], 1)
        self.assertEqual(reponse.data['en_attente'], 1)

        liste = self._appel(
            'get', '/api/django/dataquality/fusions/',
            PropositionFusionViewSet.as_view({'get': 'list'}))
        self.assertEqual(liste.status_code, status.HTTP_200_OK)

    def test_ignorer_via_endpoint(self):
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.responsable)[0]
        reponse = self._appel(
            'post', f'/api/django/dataquality/fusions/{proposition.pk}/ignorer/',
            PropositionFusionViewSet.as_view({'post': 'ignorer'}),
            pk=proposition.pk)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['statut'],
                         PropositionFusion.Statut.IGNORE)

    def test_fusionner_sans_survivant_refuse(self):
        proposition = services.scanner_propositions(
            self.company, CLIENT, self.responsable)[0]
        reponse = self._appel(
            'post',
            f'/api/django/dataquality/fusions/{proposition.pk}/fusionner/',
            PropositionFusionViewSet.as_view({'post': 'fusionner'}),
            data={}, pk=proposition.pk)
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('survivant', reponse.data)

    def test_utilisateur_non_responsable_refuse(self):
        reponse = self._appel(
            'get', '/api/django/dataquality/fusions/',
            PropositionFusionViewSet.as_view({'get': 'list'}),
            user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)
