"""AUD301 — la preuve de livraison est CONSULTABLE depuis le portail client.

Défaut d'origine : `selectors.livraisons_client_portail` construisait
`pod_url = /api/django/installations/preuves-livraison/<id>/`, résolu vers
`PreuveLivraisonViewSet` (`IsAnyRole`), dont `authentication.permissions`
exclut explicitement `portee != 'interne'` — un compte `portee=portail_client`
échouait TOUJOURS. `MesLivraisonsPortailViewSet` servait ce même `pod_url` tel
quel, et le frontend le rendait en lien cliquable : un client avec
`pod_disponible=true` obtenait 403 à chaque clic depuis l'introduction de la
fonctionnalité. Même en interne, `PreuveLivraisonSerializer` renvoyait du JSON
brut (photo = un id d'Attachment), pas un document consultable.

Le test ROUGE de référence est conservé : l'ANCIEN chemin interne répond bien
403 à un compte portail — c'est ce que le lien servait.

PACT10 — l'exemple de réponse est celui COMMITTÉ dans
`apps/portail/contract_samples/mes_livraisons_preuve.json`, jamais un
dictionnaire réécrit à la main ici.

Run :
    python manage.py test apps.portail.tests.test_aud301_preuve_livraison -v2
"""
import itertools
import json
import pathlib

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Livraison, PreuveLivraison,
)
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'mes_livraisons_preuve.json')
    .read_text(encoding='utf-8'))


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD301-{n}',
        email=f'aud301-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, scope_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = scope_id
    user.save()
    return user


class PreuveLivraisonPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('aud301-co-a', 'AUD301 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.inst_a = Installation.objects.create(
            company=self.company, client=self.client_a,
            reference=f'CH-AUD301-{next(_seq)}')
        self.inst_b = Installation.objects.create(
            company=self.company, client=self.client_b,
            reference=f'CH-AUD301-{next(_seq)}')
        self.liv_a = Livraison.objects.create(
            company=self.company, installation=self.inst_a,
            reference='LIV-AUD301-A', cout_transport=500)
        self.liv_b = Livraison.objects.create(
            company=self.company, installation=self.inst_b,
            reference='LIV-AUD301-B')
        self.pod_a = PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv_a,
            signataire_nom='Karim Bennani',
            signature_data='data:image/png;base64,AAAA',
            note='Remis en main propre.', horodatage=timezone.now())
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv_b,
            signataire_nom='Autre', horodatage=timezone.now())
        self.user_a = make_portal_user(
            self.company, 'aud301-portail-a', self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    # ── Le défaut d'origine, conservé comme preuve ──────────────────────────
    def test_ancien_endpoint_interne_repond_403_a_un_compte_portail(self):
        r = self.api.get(
            f'/api/django/installations/preuves-livraison/{self.pod_a.id}/')
        self.assertEqual(r.status_code, 403)

    # ── Le nouveau chemin portail ───────────────────────────────────────────
    def test_pod_url_pointe_desormais_vers_la_route_portail(self):
        r = self.api.get('/api/django/portail/mes-livraisons/')
        ligne = next(
            x for x in r.data['results'] if x['id'] == self.liv_a.id)
        self.assertTrue(ligne['pod_disponible'])
        self.assertEqual(
            ligne['pod_url'],
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertNotIn('installations/preuves-livraison',
                         ligne['pod_url'])

    def test_le_client_lit_sa_propre_preuve(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['signataire_nom'], 'Karim Bennani')
        self.assertEqual(r.data['signature_image'],
                         'data:image/png;base64,AAAA')
        self.assertIsNotNone(r.data['horodatage'])
        self.assertEqual(r.data['note'], 'Remis en main propre.')
        # Pas de JSON interne : jamais l'id brut de la pièce jointe.
        self.assertNotIn('photo_attachment_id', r.data)

    def test_le_pod_url_servi_est_effectivement_atteignable(self):
        """Le contrat de bout en bout : ce que la liste donne s'ouvre."""
        liste = self.api.get('/api/django/portail/mes-livraisons/')
        ligne = next(
            x for x in liste.data['results'] if x['id'] == self.liv_a.id)
        r = self.api.get(ligne['pod_url'])
        self.assertEqual(r.status_code, 200, r.data)

    def test_la_preuve_dun_autre_client_est_introuvable(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_b.id}/preuve/')
        self.assertEqual(r.status_code, 404)

    def test_la_preuve_dune_autre_societe_est_introuvable(self):
        autre = make_company('aud301-co-b', 'AUD301 Société B')
        client_autre = make_client(autre, 'Gamma')
        etranger = make_portal_user(
            autre, 'aud301-portail-b', client_autre.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        r = api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertEqual(r.status_code, 404)

    def test_livraison_sans_preuve_404(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst_a,
            reference='LIV-AUD301-SANS')
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{liv.id}/preuve/')
        self.assertEqual(r.status_code, 404)

    def test_anonyme_refuse(self):
        r = APIClient().get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertIn(r.status_code, (401, 403))

    def test_aucun_cout_de_transport_ne_fuit(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertNotIn('cout_transport', str(r.data))
        self.assertNotIn('500', str(r.data))

    def test_sans_photo_le_lien_photo_est_nul(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertIsNone(r.data['photo_url'])
        r2 = self.api.get(
            f'/api/django/portail/mes-livraisons/'
            f'{self.liv_a.id}/preuve-photo/')
        self.assertEqual(r2.status_code, 404)

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_a_exactement_les_cles_du_contrat(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_a.id}/preuve/')
        self.assertEqual(set(r.data.keys()),
                         set(CONTRAT['exemple'].keys()))
        self.assertEqual(set(CONTRAT['exemple'].keys()),
                         set(CONTRAT['exemple_sans_photo_ni_gps'].keys()))
        self.assertEqual(
            CONTRAT['endpoint'],
            'GET /api/django/portail/mes-livraisons/{id}/preuve/')
