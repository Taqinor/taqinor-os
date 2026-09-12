"""NTDATA17 — dédoublonnage cross-module : clients.

Couvre :
  * le critère d'acceptation : deux clients au MÊME téléphone normalisé
    (« +212 6 12-34-56-78 » et « 0612345678 ») remontent dans un groupe ;
  * ICE / nom approché (l'e-mail, lui, ne peut plus être en double EN BASE —
    contrainte CRX24 — son critère est couvert au niveau du moteur) ;
  * la transitivité (deux liens différents = UN seul groupe) ;
  * la détection ne MODIFIE rien ;
  * le scoping société ;
  * l'endpoint `/dataquality/doublons/clients/` et son 404 explicite.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.crm.selectors import normalize_email_key
from apps.dataquality import services
from apps.dataquality.dedoublonnage import POIDS_CRITERES, grouper_doublons
from apps.dataquality.views import DoublonsView
from authentication.models import Company

User = get_user_model()


class DoublonsClientsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA17 SA',
                                             slug='ntdata17-sa')
        cls.autre = Company.objects.create(nom='NTDATA17 Autre',
                                           slug='ntdata17-autre')
        cls.user = User.objects.create_user(
            username='ntdata17_u', password='x', company=cls.company,
            role_legacy='admin')

    def _client(self, nom, **kw):
        return Client.objects.create(company=self.company, nom=nom, **kw)

    def test_meme_telephone_normalise(self):
        a = self._client('Kasri Reda', telephone='+212 6 12-34-56-78')
        b = self._client('R. Kasri', telephone='0612345678')
        self._client('Sans doublon', telephone='0655555555')
        groupes = services.doublons_clients(self.company, self.user)
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertIn('telephone', groupes[0]['motifs'])
        self.assertEqual(groupes[0]['score'], POIDS_CRITERES['telephone'])

    def test_email_en_double_impossible_en_base_mais_critere_couvert(self):
        """Deux clients d'une même société ne PEUVENT plus partager un e-mail :
        CRX24 (`crx24_client_email_unique_ci`) l'interdit, casse ignorée.

        Le doublon d'e-mail se joue donc à la CRÉATION, pas à la détection : le
        scénario « deux fiches, même e-mail » n'est plus instanciable en base.
        Le critère `email` du détecteur reste utile (fournisseurs, données
        importées) et est donc vérifié ici au niveau du MOTEUR, sur des lignes
        brutes — la seule façon honnête de le couvrir côté clients."""
        self._client('Alpha', email='Contact@Exemple.MA')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._client('Beta', email='contact@exemple.ma')

        groupes = grouper_doublons(
            [{'id': 1, 'nom': 'Alpha', 'email': 'Contact@Exemple.MA'},
             {'id': 2, 'nom': 'Beta', 'email': 'contact@exemple.ma'}],
            criteres=('email',),
            normaliseurs={'email': normalize_email_key},
        )
        self.assertEqual(groupes[0]['ids'], [1, 2])
        self.assertIn('email', groupes[0]['motifs'])

    def test_meme_ice(self):
        a = self._client('Société A', ice='001234567000089')
        b = self._client('Societe A SARL', ice='001234567000089')
        groupes = services.doublons_clients(self.company, self.user)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertEqual(groupes[0]['score'], POIDS_CRITERES['ice'])

    def test_nom_approche(self):
        a = self._client('Belkacem Karim')
        b = self._client('Bélkacem  Karim')
        groupes = services.doublons_clients(self.company, self.user)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertEqual(groupes[0]['motifs'], ['nom'])

    def test_transitivite_un_seul_groupe(self):
        # a—b par TÉLÉPHONE, b—c par NOM : deux critères différents, un seul
        # groupe. (L'e-mail ne peut pas servir de second lien entre deux
        # clients d'une même société — CRX24 l'interdit en base.)
        a = self._client('Alpha', telephone='0612345678')
        b = self._client('Belkacem Karim', telephone='0612345678')
        c = self._client('Bélkacem  Karim')
        groupes = services.doublons_clients(self.company, self.user)
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id, c.id]))
        self.assertEqual(set(groupes[0]['motifs']), {'telephone', 'nom'})
        # Score = poids du critère le PLUS FORT concordant.
        self.assertEqual(groupes[0]['score'], POIDS_CRITERES['telephone'])

    def test_champs_vides_ne_rapprochent_jamais(self):
        self._client('Vide 1')
        self._client('Autre chose')
        self.assertEqual(services.doublons_clients(self.company, self.user),
                         [])

    def test_detection_ne_modifie_rien(self):
        a = self._client('Alpha', telephone='0612345678')
        b = self._client('Beta', telephone='0612345678')
        services.doublons_clients(self.company, self.user)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(Client.objects.filter(company=self.company).count(),
                         2)
        self.assertEqual(a.nom, 'Alpha')
        self.assertEqual(b.nom, 'Beta')

    def test_scoping_societe(self):
        self._client('Alpha', telephone='0612345678')
        Client.objects.create(company=self.autre, nom='Ailleurs',
                              telephone='0612345678')
        self.assertEqual(services.doublons_clients(self.company, self.user),
                         [])


class DoublonsEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA17 API',
                                             slug='ntdata17-api')
        cls.responsable = User.objects.create_user(
            username='ntdata17_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata17_simple', password='x', company=cls.company,
            role_legacy='normal')
        Client.objects.create(company=cls.company, nom='A',
                              telephone='0612345678')
        Client.objects.create(company=cls.company, nom='B',
                              telephone='+212612345678')

    def _get(self, entite, user=None):
        requete = APIRequestFactory().get(
            '/api/django/dataquality/doublons/%s/' % entite)
        force_authenticate(requete, user=user or self.responsable)
        return DoublonsView.as_view()(requete, entite=entite)

    def test_endpoint_clients(self):
        reponse = self._get('clients')
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['nb_groupes'], 1)
        self.assertEqual(len(reponse.data['groupes'][0]['ids']), 2)

    def test_entite_inconnue_404(self):
        reponse = self._get('licornes')
        self.assertEqual(reponse.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('licornes', reponse.data['detail'])

    def test_utilisateur_non_responsable_refuse(self):
        self.assertEqual(self._get('clients', user=self.simple).status_code,
                         status.HTTP_403_FORBIDDEN)
