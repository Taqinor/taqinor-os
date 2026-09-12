"""Tests NTPRT14 — « Mes chantiers » (portail client authentifié).

Timeline réutilisant la timeline PORTAIL déjà synchronisée (CHT10/CHT11 —
``JalonChantierPortail``, lecture seule) + galerie photos avant/pendant/après
filtrée sur ``records.Attachment``. AUCUNE donnée financière (BOM/prix
exclus) — le contrat de ``apps.installations.selectors``.

Couvre, comme NTPRT10/11 :

* la liste et le détail sont bornés au SEUL client rattaché (jamais un
  chantier d'un autre client de la même société, ni d'une autre société) ;
* le détail expose les MÊMES jalons que l'écran interne (synchronisés par
  CHT11), sans jamais de montant ;
* la galerie photo est filtrable par phase (avant/pendant/après) et sert les
  octets via une route scopée au client connecté (jamais l'endpoint interne
  ``records/attachments/<id>/download/``) ;
* un chantier annulé n'apparaît jamais côté client ;
* la portée doit être EXACTEMENT ``portail_client``.

PACT10 — la forme des payloads est celle des contrats COMMITTÉS
(``apps/portail/contract_samples/mes_chantiers_{liste,detail,photos}.json``,
les mêmes fichiers que lisent les tests frontend) — jamais un dictionnaire
réécrit à la main dans un second endroit.

Run :
    python manage.py test apps.portail.tests.test_ntprt14_mes_chantiers -v2
"""
import itertools
import json
import pathlib
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.services import upsert_jalon_chantier
from apps.records.models import Attachment
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

_CONTRACT_DIR = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'


def _contrat(nom):
    return json.loads((_CONTRACT_DIR / f'{nom}.json').read_text(encoding='utf-8'))


CONTRAT_LISTE = _contrat('mes_chantiers_liste')
CONTRAT_DETAIL = _contrat('mes_chantiers_detail')
CONTRAT_PHOTOS = _contrat('mes_chantiers_photos')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'NTPRT14-{n}',
        email=f'ntprt14-{company.id}-{n}@example.invalid')


def make_installation(company, client, annule=False):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-NTPRT14-{n}', client=client,
        site_ville='Casablanca', annule=annule)


def make_photo(company, installation, phase='avant', mime='image/jpeg'):
    n = next(_seq)
    ct = ContentType.objects.get_for_model(Installation)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=installation.id,
        file_key=f'attachments/chantier-{n}.jpg', filename=f'photo-{n}.jpg',
        size=1234, mime=mime, phase=phase)


_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_interne(company, username, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=f'role-{username}',
        defaults={'permissions': list(permissions)})
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)


class MesChantiersListeTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt14-co-a', 'NTPRT14 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.chantier_a = make_installation(self.company, self.client_a)
        self.chantier_b = make_installation(self.company, self.client_b)
        self.chantier_annule = make_installation(
            self.company, self.client_a, annule=True)
        self.user_a = make_portal_user(
            self.company, 'ntprt14-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_liste_bornee_au_client_rattache(self):
        res = self.api.get('/api/django/portail/mes-chantiers/')
        self.assertEqual(res.status_code, 200)
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertIn(self.chantier_a.id, ids)
        self.assertNotIn(self.chantier_b.id, ids)

    def test_chantier_annule_jamais_montre(self):
        res = self.api.get('/api/django/portail/mes-chantiers/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.chantier_annule.id, ids)

    def test_aucun_champ_financier_dans_le_payload(self):
        res = self.api.get('/api/django/portail/mes-chantiers/')
        corps = str(res.data)
        for interdit in ('prix_achat', 'marge', 'bom', 'total_ttc',
                         'montant'):
            self.assertNotIn(interdit, corps)

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_a_exactement_les_cles_du_contrat(self):
        res = self.api.get('/api/django/portail/mes-chantiers/')
        ligne = res.data['results'][0]
        self.assertEqual(
            set(ligne.keys()),
            set(CONTRAT_LISTE['exemple']['results'][0].keys()))

    def test_detail_dun_chantier_dautrui_est_introuvable(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_compte_portail_fournisseur_refuse(self):
        fournisseur = make_portal_user(
            self.company, 'ntprt14-portail-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        api = APIClient()
        api.force_authenticate(user=fournisseur)
        res = api.get('/api/django/portail/mes-chantiers/')
        self.assertEqual(res.status_code, 403)

    def test_utilisateur_interne_refuse(self):
        interne = make_interne(self.company, 'ntprt14-interne',
                               ['installations_voir'])
        api = APIClient()
        api.force_authenticate(user=interne)
        res = api.get('/api/django/portail/mes-chantiers/')
        self.assertEqual(res.status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get('/api/django/portail/mes-chantiers/')
        self.assertIn(res.status_code, (401, 403))

    def test_client_dune_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt14-co-b', 'NTPRT14 Société B')
        client_autre = make_client(autre, 'Gamma')
        make_installation(autre, client_autre)
        etranger = make_portal_user(
            autre, 'ntprt14-portail-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            client_autre.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        res = api.get('/api/django/portail/mes-chantiers/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.chantier_a.id, ids)
        self.assertNotIn(self.chantier_b.id, ids)


class MesChantiersJalonsTests(TestCase):
    """Le détail expose la MÊME timeline que l'écran interne (CHT10/CHT11),
    synchronisée automatiquement — jamais de double saisie."""

    def setUp(self):
        self.company = make_company('ntprt14-jal-co', 'NTPRT14 Jalons')
        self.client_a = make_client(self.company, 'Alpha')
        self.chantier = make_installation(self.company, self.client_a)
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude technique',
            atteint=True)
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'installation', 'Installation',
            atteint=False)
        self.user_a = make_portal_user(
            self.company, 'ntprt14-jal-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_le_detail_liste_les_jalons_synchronises(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier.id}/')
        self.assertEqual(res.status_code, 200, res.data)
        libelles = [j['libelle'] for j in res.data['jalons']]
        self.assertEqual(libelles, ['Étude technique', 'Installation'])
        self.assertTrue(res.data['jalons'][0]['atteint'])
        self.assertFalse(res.data['jalons'][1]['atteint'])

    def test_aucun_jalon_dun_autre_chantier_ne_fuit(self):
        autre_client = make_client(self.company, 'Beta')
        autre_chantier = make_installation(self.company, autre_client)
        upsert_jalon_chantier(
            self.company, autre_chantier.id, 'etude', 'Étude Beta',
            atteint=True)
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier.id}/')
        libelles = [j['libelle'] for j in res.data['jalons']]
        self.assertNotIn('Étude Beta', libelles)

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_a_exactement_les_cles_du_contrat(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier.id}/')
        self.assertEqual(set(res.data.keys()),
                         set(CONTRAT_DETAIL['exemple'].keys()))
        self.assertEqual(
            set(res.data['jalons'][0].keys()),
            set(CONTRAT_DETAIL['exemple']['jalons'][0].keys()))


class MesChantiersPhotosTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt14-photo-co', 'NTPRT14 Photos')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.chantier_a = make_installation(self.company, self.client_a)
        self.chantier_b = make_installation(self.company, self.client_b)
        self.photo_avant = make_photo(
            self.company, self.chantier_a, phase='avant')
        self.photo_apres = make_photo(
            self.company, self.chantier_a, phase='apres')
        self.photo_b = make_photo(self.company, self.chantier_b, phase='avant')
        self.user_a = make_portal_user(
            self.company, 'ntprt14-photo-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_liste_les_photos_du_chantier(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
            f'photos/')
        self.assertEqual(res.status_code, 200)
        ids = {p['id'] for p in res.data['results']}
        self.assertEqual(ids, {self.photo_avant.id, self.photo_apres.id})

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_a_exactement_les_cles_du_contrat(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
            f'photos/')
        ligne = res.data['results'][0]
        self.assertEqual(
            set(ligne.keys()),
            set(CONTRAT_PHOTOS['exemple']['results'][0].keys()))

    def test_filtre_par_phase(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
            f'photos/', {'phase': 'avant'})
        ids = {p['id'] for p in res.data['results']}
        self.assertEqual(ids, {self.photo_avant.id})

    def test_photos_dun_autre_client_introuvables(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_b.id}/'
            f'photos/')
        self.assertEqual(res.status_code, 404)

    def test_photo_dun_autre_client_introuvable(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_b.id}/'
            f'photo/{self.photo_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_photo_servie_via_route_portail_scopee(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'\xff\xd8\xff', None)):
            res = self.api.get(
                f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
                f'photo/{self.photo_avant.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'image/jpeg')

    def test_url_de_la_liste_pointe_vers_la_route_portail(self):
        res = self.api.get(
            f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
            f'photos/')
        ligne = next(
            p for p in res.data['results'] if p['id'] == self.photo_avant.id)
        self.assertEqual(
            ligne['url'],
            f'/api/django/portail/mes-chantiers/{self.chantier_a.id}/'
            f'photo/{self.photo_avant.id}/')
