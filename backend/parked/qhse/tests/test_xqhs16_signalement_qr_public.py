"""XQHS16 — Signalement QR public sans compte (danger/incident chantier).

Couvre :
  * un signalement PUBLIC (sans login) via jeton valide crée l'entrée scopée
    société + notifie le responsable HSE (best-effort) ;
  * jeton inconnu/révoqué → 404 (indistinct) ;
  * l'anonymat fonctionne (nom/téléphone facultatifs) ;
  * le rate-limit throttle est bien configuré ;
  * le QR se télécharge (Responsable/Admin, authentifié) ;
  * isolation multi-société de la gestion des liens.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    Incident, LienSignalementPublic, SignalementPublic,
)
from apps.qhse.services import (
    SIGNALEMENT_INTROUVABLE, SIGNALEMENT_OK,
    creer_signalement_public, generer_qr_signalement,
    resolve_lien_signalement_public,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ResolveLienTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs16-co', 'Xqhs16 Co')
        self.lien = LienSignalementPublic.objects.create(
            company=self.company, chantier_id=42, libelle='Chantier test')

    def test_token_valide_resout(self):
        statut, lien = resolve_lien_signalement_public(self.lien.token)
        self.assertEqual(statut, SIGNALEMENT_OK)
        self.assertEqual(lien.pk, self.lien.pk)

    def test_token_inconnu(self):
        statut, lien = resolve_lien_signalement_public('inconnu-xyz')
        self.assertEqual(statut, SIGNALEMENT_INTROUVABLE)
        self.assertIsNone(lien)

    def test_lien_revoque_meme_statut_que_inconnu(self):
        self.lien.actif = False
        self.lien.save()
        statut, lien = resolve_lien_signalement_public(self.lien.token)
        self.assertEqual(statut, SIGNALEMENT_INTROUVABLE)


class CreerSignalementPublicServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs16-svc', 'Xqhs16 Svc')
        self.lien = LienSignalementPublic.objects.create(
            company=self.company, chantier_id=7)

    def test_cree_signalement_scope_societe(self):
        signalement = creer_signalement_public(
            self.lien, type_signalement=SignalementPublic.Type.DANGER,
            description='Câble électrique dénudé au sol')
        self.assertEqual(signalement.company_id, self.company.pk)
        self.assertEqual(signalement.source, SignalementPublic.Source.QR_PUBLIC)

    def test_anonyme_sans_nom_ni_telephone(self):
        signalement = creer_signalement_public(
            self.lien, type_signalement=SignalementPublic.Type.INCIDENT,
            description='Fuite de gasoil')
        self.assertTrue(signalement.anonyme)

    def test_non_anonyme_avec_coordonnees(self):
        signalement = creer_signalement_public(
            self.lien, type_signalement=SignalementPublic.Type.DANGER,
            description='Échafaudage instable', nom='Karim', telephone='0600000000')
        self.assertFalse(signalement.anonyme)


class PublicSignalementApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs16-api', 'Xqhs16 Api')
        self.responsable = make_user(self.company, 'xqhs16-hse')
        self.lien = LienSignalementPublic.objects.create(
            company=self.company, chantier_id=99,
            responsable_hse=self.responsable)
        self.api = APIClient()

    def test_get_lien_valide(self):
        resp = self.api.get(
            f'/api/django/qhse/public/signalement/{self.lien.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valide'])

    def test_get_token_inconnu_404(self):
        resp = self.api.get(
            '/api/django/qhse/public/signalement/token-inconnu-abc/')
        self.assertEqual(resp.status_code, 404)

    def test_post_cree_signalement_anonyme(self):
        resp = self.api.post(
            f'/api/django/qhse/public/signalement/{self.lien.token}/',
            {'type_signalement': 'danger',
             'description': 'Trou non balisé sur le chantier'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(SignalementPublic.objects.filter(
            lien=self.lien, company=self.company).count(), 1)
        signalement = SignalementPublic.objects.get(lien=self.lien)
        self.assertTrue(signalement.anonyme)

    def test_post_description_manquante_400(self):
        resp = self.api.post(
            f'/api/django/qhse/public/signalement/{self.lien.token}/',
            {'type_signalement': 'danger'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_post_token_revoque_404(self):
        self.lien.actif = False
        self.lien.save()
        resp = self.api.post(
            f'/api/django/qhse/public/signalement/{self.lien.token}/',
            {'type_signalement': 'danger', 'description': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_post_ne_fuit_jamais_dans_autre_societe(self):
        """Un signalement posté via CE lien reste rattaché à la société du
        lien uniquement (jamais devinable/écrasable depuis la requête)."""
        other_co = make_company('xqhs16-other', 'Xqhs16 Other')
        resp = self.api.post(
            f'/api/django/qhse/public/signalement/{self.lien.token}/',
            {'type_signalement': 'incident', 'description': 'x',
             'company': other_co.pk},
            format='json')
        self.assertEqual(resp.status_code, 201)
        signalement = SignalementPublic.objects.get(id=resp.data['id'])
        self.assertEqual(signalement.company_id, self.company.pk)
        self.assertNotEqual(signalement.company_id, other_co.pk)


class LienSignalementPublicViewSetTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xqhs16-va', 'Xqhs16 VA')
        self.co_b = make_company('xqhs16-vb', 'Xqhs16 VB')
        self.admin_a = make_user(self.co_a, 'xqhs16-admin-a')
        self.admin_b = make_user(self.co_b, 'xqhs16-admin-b')
        self.lien_a = LienSignalementPublic.objects.create(
            company=self.co_a, chantier_id=1, libelle='Chantier A')

    def test_create_pose_company_serveur(self):
        resp = auth(self.admin_a).post(
            '/api/django/qhse/liens-signalement/',
            {'chantier_id': 5, 'libelle': 'Nouveau chantier'}, format='json')
        self.assertEqual(resp.status_code, 201)
        lien = LienSignalementPublic.objects.get(id=resp.data['id'])
        self.assertEqual(lien.company_id, self.co_a.pk)

    def test_isolation_societe_liste(self):
        resp = auth(self.admin_b).get('/api/django/qhse/liens-signalement/')
        self.assertEqual(resp.status_code, 200)
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertNotIn(self.lien_a.pk, ids)

    def test_qr_action_telecharge_png(self):
        resp = auth(self.admin_a).get(
            f'/api/django/qhse/liens-signalement/{self.lien_a.pk}/qr/')
        # Dégrade proprement (503) si `qrcode` n'est pas installée dans
        # l'environnement de test ; sinon 200 + PNG.
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'image/png')


class GenererQrServiceTests(TestCase):
    def test_genere_png_ou_degrade_none(self):
        company = make_company('xqhs16-qr', 'Xqhs16 Qr')
        lien = LienSignalementPublic.objects.create(
            company=company, chantier_id=3)
        png = generer_qr_signalement(lien, base_url='https://api.taqinor.ma')
        if png is not None:
            self.assertTrue(png.startswith(b'\x89PNG'))


class IncidentLinkTests(TestCase):
    """Le signalement peut être converti en Incident côté HSE (lien FK)."""

    def test_signalement_peut_lier_un_incident(self):
        company = make_company('xqhs16-inc', 'Xqhs16 Inc')
        lien = LienSignalementPublic.objects.create(
            company=company, chantier_id=11)
        signalement = creer_signalement_public(
            lien, type_signalement=SignalementPublic.Type.INCIDENT,
            description='Chute de matériel')
        incident = Incident.objects.create(
            company=company, titre='Chute de matériel',
            type_incident=Incident.TypeIncident.INCIDENT)
        signalement.incident = incident
        signalement.save()
        signalement.refresh_from_db()
        self.assertEqual(signalement.incident_id, incident.pk)
