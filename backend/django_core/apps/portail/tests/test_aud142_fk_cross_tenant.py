"""Tests AUD142 — les FK cross-app des 5 ressources portail refusent l'id
d'une AUTRE société.

Défaut d'origine : ``devis_id``, ``facture_id``, ``client_id``, ``lead_id`` et
``chantier_id`` étaient de simples ``IntegerField(min_value=0)`` — aucun
``validate_*``, aucun queryset borné. Les ``perform_create`` ne posaient que
``company=request.user.company`` (SEUL ``ComptePortailClientViewSet``
vérifiait l'appartenance), et les FK portent ``db_constraint=False`` : la base
ne vérifiait ni existence ni tenant. Un Responsable de la société A créait donc
une ligne de paiement portail pointant sur la facture de la société B, et le
client de A voyait apparaître le montant d'un tiers.

Note de drain : AUD140 a fermé ENTIÈREMENT l'écriture ERP sur deux des cinq
ressources (acceptation de devis, paiement de facture) — leur POST répond 405,
ce qui satisfait « jamais 201 » plus fortement qu'un 400. Les validateurs y
sont malgré tout posés (défense en profondeur) et exercés ici AU NIVEAU
SERIALIZER, pour qu'une réouverture future de ces surfaces naisse gardée.

Ces tests étaient ROUGES avant le correctif (201 sur les cinq).

Run :
    python manage.py test apps.portail.tests.test_aud142_fk_cross_tenant -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.portail.serializers import (
    AcceptationDevisPortailSerializer,
    DemandeTicketPortailSerializer,
    DocumentClientPortailSerializer,
    JalonChantierPortailSerializer,
    PaiementFacturePortailSerializer,
)
from apps.crm.models import Client, Lead
from apps.facturation.models import Facture
from apps.installations.models import Installation
from apps.portail.models import (
    DemandeTicketPortail,
    DocumentClientPortail,
    JalonChantierPortail,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD142-{n}',
        email=f'aud142-{company.id}-{n}@example.invalid')


def make_responsable(company, username):
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role_legacy='responsable')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def contexte(user):
    """Contexte serializer minimal portant l'utilisateur (donc sa société)."""
    request = APIRequestFactory().post('/')
    request.user = user
    return {'request': request}


class FkCrossTenantPortailTests(TestCase):
    def setUp(self):
        self.a = make_company('aud142-co-a', 'AUD142 Société A')
        self.b = make_company('aud142-co-b', 'AUD142 Société B')
        self.user_a = make_responsable(self.a, 'aud142-resp-a')
        self.api = auth(self.user_a)

        # Objets appartenant à la société B — jamais atteignables depuis A.
        self.client_b = make_client_crm(self.b, 'Beta')
        self.lead_b = Lead.objects.create(company=self.b, nom='Lead Beta')
        self.chantier_b = Installation.objects.create(
            company=self.b, reference='CHT-AUD142-B')
        self.devis_b = Devis.objects.create(
            company=self.b, reference='DEV-AUD142-B', client=self.client_b,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        self.facture_b = Facture.objects.create(
            company=self.b, reference='FAC-AUD142-B', client=self.client_b)

        # Les mêmes objets, côté A — le témoin « ça passe quand c'est à moi ».
        self.client_a = make_client_crm(self.a, 'Alpha')
        self.chantier_a = Installation.objects.create(
            company=self.a, reference='CHT-AUD142-A')

    # ── Les 3 ressources encore écrivables : 404 (ERR-ENF11-FUZZ-PORTAIL ;
    #    400 avant), jamais 201 ───────────────────────────────────────────────

    def test_document_client_dun_autre_tenant_refuse(self):
        """ROUGE avant AUD142 : 201."""
        res = self.api.post('/api/django/portail/documents-client-portail/', {
            'client_id': self.client_b.id, 'type_document': 'facture_onee',
        }, format='multipart')  # CI #997 fuzz (2) : dépôt = formulaire seul
        self.assertEqual(res.status_code, 404, res.content)
        self.assertFalse(DocumentClientPortail.objects.filter(
            client_id=self.client_b.id).exists())

    def test_document_lead_dun_autre_tenant_refuse(self):
        res = self.api.post('/api/django/portail/documents-client-portail/', {
            'client_id': self.client_a.id, 'lead_id': self.lead_b.id,
        }, format='multipart')
        self.assertEqual(res.status_code, 404, res.content)

    def test_jalon_chantier_dun_autre_tenant_refuse(self):
        """ROUGE avant AUD142 : 201. ADOC129 — la création manuelle est
        désormais fermée pour TOUS (405) : a fortiori sur un chantier d'un
        autre tenant, aucune ligne n'est créée."""
        res = self.api.post('/api/django/portail/jalons-chantier-portail/', {
            'chantier_id': self.chantier_b.id, 'libelle': 'Installation',
        }, format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertFalse(JalonChantierPortail.objects.filter(
            chantier_id=self.chantier_b.id).exists())

    def test_demande_ticket_dun_autre_tenant_refusee(self):
        """ROUGE avant AUD142 : 201."""
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_b.id, 'sujet': 'Onduleur',
        }, format='json')
        self.assertEqual(res.status_code, 404, res.content)
        self.assertFalse(DemandeTicketPortail.objects.filter(
            client_id=self.client_b.id).exists())

    def test_demande_ticket_chantier_dun_autre_tenant_refusee(self):
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_a.id, 'sujet': 'Onduleur',
            'chantier_id': self.chantier_b.id,
        }, format='json')
        self.assertEqual(res.status_code, 404, res.content)

    def test_les_objets_de_ma_societe_passent_toujours(self):
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_a.id, 'sujet': 'Onduleur',
            'chantier_id': self.chantier_a.id,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)

    # ── Les 2 ressources fermées par AUD140 : 405 à l'API, garde au ────────
    #    niveau serializer (défense en profondeur)

    def test_acceptation_et_paiement_ne_sont_plus_creables_du_tout(self):
        for chemin, corps in (
            ('acceptations-devis-portail',
             {'devis_id': self.devis_b.id, 'nom_signataire': 'X'}),
            ('paiements-facture-portail',
             {'facture_id': self.facture_b.id, 'montant': '1.00'}),
        ):
            with self.subTest(chemin=chemin):
                res = self.api.post(
                    f'/api/django/portail/{chemin}/', corps, format='json')
                self.assertEqual(res.status_code, 405, res.content)

    def test_le_serializer_acceptation_refuse_un_devis_dun_autre_tenant(self):
        ser = AcceptationDevisPortailSerializer(
            data={'devis_id': self.devis_b.id, 'nom_signataire': 'X'},
            context=contexte(self.user_a))
        with self.assertRaises(NotFound) as ctx:
            ser.is_valid()
        self.assertIn('devis_id', ctx.exception.detail)

    def test_le_serializer_paiement_refuse_une_facture_dun_autre_tenant(self):
        ser = PaiementFacturePortailSerializer(
            data={'facture_id': self.facture_b.id, 'montant': '1.00'},
            context=contexte(self.user_a))
        with self.assertRaises(NotFound) as ctx:
            ser.is_valid()
        self.assertIn('facture_id', ctx.exception.detail)

    # ── Les cinq serializers, en un seul balayage ───────────────────────────
    # (ADOC129 : le cinquième, JalonChantierPortailSerializer, n'a plus de FK
    # écrivable — couvert par test_jalon_chantier_id_en_lecture_seule.)

    def test_les_cinq_serializers_refusent_lid_dun_autre_tenant(self):
        cas = (
            (AcceptationDevisPortailSerializer,
             {'devis_id': self.devis_b.id, 'nom_signataire': 'X'}, 'devis_id'),
            (PaiementFacturePortailSerializer,
             {'facture_id': self.facture_b.id, 'montant': '1.00'},
             'facture_id'),
            (DocumentClientPortailSerializer,
             {'client_id': self.client_b.id}, 'client_id'),
            (DemandeTicketPortailSerializer,
             {'client_id': self.client_b.id, 'sujet': 'X'}, 'client_id'),
        )
        for classe, donnees, champ in cas:
            with self.subTest(serializer=classe.__name__):
                ser = classe(data=donnees, context=contexte(self.user_a))
                with self.assertRaises(NotFound) as ctx:
                    ser.is_valid()
                self.assertIn(champ, ctx.exception.detail)

    def test_jalon_chantier_id_en_lecture_seule(self):
        """ADOC129 — le jalon portail ne se crée plus à la main (POST 405) et
        son chantier ne se corrige pas : ``chantier_id`` est en LECTURE
        SEULE. Un id d'un autre tenant est donc IGNORÉ (jamais écrit), au lieu
        d'être validé — la garde AUD142 n'a plus de champ écrivable à
        protéger sur ce serializer."""
        ser = JalonChantierPortailSerializer(
            data={'chantier_id': self.chantier_b.id, 'libelle': 'X'},
            context=contexte(self.user_a))
        self.assertTrue(ser.fields['chantier_id'].read_only)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn('chantier_id', ser.validated_data)
        self.assertNotIn('chantier', ser.validated_data)

    def test_un_id_inexistant_est_refuse_comme_un_id_dun_autre_tenant(self):
        """Aucun oracle : « d'une autre société » et « inexistant » se
        confondent dans le même message."""
        ser = DocumentClientPortailSerializer(
            data={'client_id': 987654321}, context=contexte(self.user_a))
        with self.assertRaises(NotFound) as inexistant:
            ser.is_valid()
        autre = DocumentClientPortailSerializer(
            data={'client_id': self.client_b.id}, context=contexte(self.user_a))
        with self.assertRaises(NotFound) as etranger:
            autre.is_valid()
        self.assertEqual(inexistant.exception.detail, etranger.exception.detail)


class ContratApiFuzzPortailTests(TestCase):
    """ERR-ENF11-FUZZ-PORTAIL — les données hors schéma OpenAPI sont refusées
    (400) au lieu d'être converties ou ignorées (api-fuzz « accepted
    schema-violating request », nocturne 38129616897)."""

    LISTES = ('acceptations-devis-portail', 'comptes-portail',
              'demandes-ticket-portail', 'documents-client-portail',
              'jalons-chantier-portail', 'paiements-facture-portail')
    URL = '/api/django/portail/demandes-ticket-portail/'

    def setUp(self):
        self.a = make_company('enf11-portail-a', 'ENF11 Portail A')
        self.api = auth(make_responsable(self.a, 'enf11-portail-resp'))
        self.client_a = make_client_crm(self.a, 'Alpha')
        self.demande = DemandeTicketPortail.objects.create(
            company=self.a, client_id=self.client_a.id, sujet='Onduleur')

    def test_listes_page_size_hors_schema_400(self):
        for liste in self.LISTES:
            with self.subTest(liste=liste):
                res = self.api.get(f'/api/django/portail/{liste}/',
                                   {'page_size': 'null'})
                self.assertEqual(res.status_code, 400, res.content)
                self.assertEqual(
                    self.api.get(f'/api/django/portail/{liste}/').status_code,
                    200)

    def test_demande_ticket_types_stricts_400(self):
        valide = {'client_id': self.client_a.id, 'sujet': 'Onduleur'}
        for champ, brut in (('client_id', str(self.client_a.id)),
                            ('client_id', True), ('chantier_id', '1'),
                            ('sujet', 123), ('description', False)):
            corps = {**valide, champ: brut}
            with self.subTest(champ=champ, brut=brut):
                res = self.api.post(self.URL, corps, format='json')
                self.assertEqual(res.status_code, 400, res.content)
                self.assertIn(champ, res.data)
                res = self.api.put(f'{self.URL}{self.demande.id}/', corps,
                                   format='json')
                self.assertEqual(res.status_code, 400, res.content)
                res = self.api.patch(f'{self.URL}{self.demande.id}/',
                                     {champ: brut}, format='json')
                self.assertEqual(res.status_code, 400, res.content)
        res = self.api.post(self.URL, [valide], format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertEqual(DemandeTicketPortail.objects.filter(
            company=self.a).count(), 1)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.sujet, 'Onduleur')

    def test_compte_portail_actif_booleen_strict_400(self):
        """CI #997 api-fuzz : PATCH {"actif": 0} était lu comme False (200)
        et désactivait le compte ; seul un vrai booléen JSON passe."""
        from apps.portail.models import ComptePortailClient
        compte = ComptePortailClient.objects.create(
            company=self.a, client=self.client_a, token_acces='enf11-ci997-jeton')
        url = f'/api/django/portail/comptes-portail/{compte.id}/'
        for brut in (0, 1, 'false', None):
            with self.subTest(brut=brut):
                res = self.api.patch(url, {'client': self.client_a.id,
                                           'actif': brut}, format='json')
                self.assertEqual(res.status_code, 400, res.content)
                self.assertIn('actif', res.data)
        compte.refresh_from_db()
        self.assertTrue(compte.actif)
        res = self.api.patch(url, {'actif': False}, format='json')
        self.assertIn(res.status_code, (200, 202), res.content)
        compte.refresh_from_db()
        self.assertFalse(compte.actif)

    def test_document_client_depot_formulaire_seul_marquer_traite_json(self):
        # CI #997 fuzz (2) : le dépôt est un formulaire (le champ ``fichier``
        # ne se porte pas en JSON) ; ``marquer_traite`` reste un appel JSON.
        from apps.portail.models import DocumentClientPortail
        liste = '/api/django/portail/documents-client-portail/'
        res = self.api.post(liste, {'client_id': self.client_a.id,
                                    'fichier': ''}, format='json')
        self.assertEqual(res.status_code, 415, res.content)
        doc = DocumentClientPortail.objects.create(
            company=self.a, client_id=self.client_a.id, type_document='autre')
        res = self.api.post(f'{liste}{doc.id}/marquer_traite/', {},
                            format='json')
        self.assertEqual(res.status_code, 200, res.content)
        doc.refresh_from_db()
        self.assertTrue(doc.traite)

    def test_modification_demande_id_inconnu_404_corps_identique(self):
        """ERR-ENF11-FUZZ-PORTAIL — PUT/PATCH : un entier conforme qui ne
        désigne rien dans la société (inexistant OU d'une autre société) est
        une ressource introuvable (404), au corps identique ; rien n'est écrit."""
        autre = make_company('enf11-portail-b', 'ENF11 Portail B')
        etranger = Installation.objects.create(
            company=autre, reference='CHT-ENF11-B')
        url = f'{self.URL}{self.demande.id}/'
        complet = {'client_id': self.client_a.id, 'sujet': 'Onduleur'}
        corps = []
        for chantier in (2147483647, etranger.id):
            res = self.api.put(
                url, {**complet, 'chantier_id': chantier}, format='json')
            self.assertEqual(res.status_code, 404, res.content)
            corps.append(res.json()['chantier_id'])
            res = self.api.patch(url, {'chantier_id': chantier}, format='json')
            self.assertEqual(res.status_code, 404, res.content)
            corps.append(res.json()['chantier_id'])
        self.assertEqual(len(set(map(tuple, corps))), 1)
        self.demande.refresh_from_db()
        self.assertIsNone(self.demande.chantier_id)

    def test_schema_depot_libelle_sans_nul(self):
        """ERR-ENF11-FUZZ-PORTAIL — ``libelle`` d'un dépôt est un texte strict,
        publié sans caractère nul (le serveur refuse ``U+0000``)."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator(patterns=[path(
            'api/django/portail/', include('apps.portail.urls'))]
        ).get_schema(request=None, public=True)
        composants = schema['components']['schemas']
        for nom in ('DocumentClientPortailRequest',
                    'PatchedDocumentClientPortailRequest'):
            self.assertIn(
                '\\u0000', composants[nom]['properties']['libelle']['pattern'])
        res = self.api.post(
            '/api/django/portail/documents-client-portail/',
            {'client_id': self.client_a.id, 'libelle': 'a\x00b'},
            format='multipart')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('libelle', res.json())
