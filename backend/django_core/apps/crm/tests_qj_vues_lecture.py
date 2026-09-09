"""QJ-VUES (fondateur 09/09/2026) — « un endroit où je vois combien de fois le
devis a été consulté, sur chaque fiche lead, à tout moment ».

Côté serveur : la fiche lead (`GET /crm/leads/<id>/`) expose PAR devis un bloc
`lecture` — `{nombre_vues, premiere_consultation, derniere_consultation}` —
agrégé sur TOUS les ShareLink du devis (expirés compris : re-minter un lien
après expiration ne remet jamais l'historique à zéro), via le sélecteur
cross-app `apps.ventes.selectors.share_link_lecture_map` (CLAUDE.md : lecture
inter-app par le selectors.py de l'app cible, jamais ses modèles).

Distinct de `share_link` (L-NIV : badge du lien VALIDE le plus récent —
absent si tout est expiré) : `lecture` est un HISTORIQUE, il survit à
l'expiration.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qj_vues_lecture -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import share_link_lecture_map

User = get_user_model()


def make_company(slug):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestShareLinkLectureMapSelector(TestCase):
    """(a) le sélecteur pur : agrégat multi-liens, expirés compris."""

    def setUp(self):
        self.company = make_company('qjv-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJV',
            email='qjv@example.com', telephone='+212600000021')
        self.lead = Lead.objects.create(company=self.company, nom='QJV')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJV-1', lead=self.lead,
            client=self.client_obj, statut='envoye', taux_tva=20,
            remise_globale=0)

    def test_devis_jamais_partage_absent(self):
        self.assertEqual(share_link_lecture_map([self.devis.id]), {})
        self.assertEqual(share_link_lecture_map([]), {})
        self.assertEqual(share_link_lecture_map(None), {})

    def test_agregat_sur_liens_valide_et_expire(self):
        now = timezone.now()
        # Lien EXPIRÉ avec 3 vues anciennes…
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            expires_at=now - timedelta(days=2),
            view_count=3,
            first_viewed_at=now - timedelta(days=10),
            last_viewed_at=now - timedelta(days=5))
        # …et lien VALIDE re-minté, 2 vues récentes.
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            view_count=2,
            first_viewed_at=now - timedelta(days=1),
            last_viewed_at=now - timedelta(hours=2))

        result = share_link_lecture_map([self.devis.id])
        row = result[self.devis.id]
        # Somme des vues des DEUX liens — l'expiration n'efface rien.
        self.assertEqual(row['nombre_vues'], 5)
        # Première = la plus ancienne, dernière = la plus récente.
        self.assertIn('T', row['premiere_consultation'])
        self.assertIn('T', row['derniere_consultation'])
        self.assertLess(row['premiere_consultation'],
                        row['derniere_consultation'])

    def test_lien_jamais_ouvert_compte_zero(self):
        ShareLink.objects.create(company=self.company, devis=self.devis)
        row = share_link_lecture_map([self.devis.id])[self.devis.id]
        self.assertEqual(row['nombre_vues'], 0)
        self.assertIsNone(row['premiere_consultation'])
        self.assertIsNone(row['derniere_consultation'])


class TestLeadDetailExposesLecture(TestCase):
    """(b) bout en bout : GET fiche lead → devis[].lecture."""

    def setUp(self):
        self.company = make_company('qjv-e2e')
        self.user = User.objects.create_user(
            username='qjv_e2e', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='QJV', prenom='E2E',
            email='qjv-e2e@example.com', telephone='0612345679')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJVE2E',
            email='qjv-e2e-cl@example.com', telephone='+212600000022')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJV-2', lead=self.lead,
            client=self.client_obj, statut='envoye', taux_tva=20,
            remise_globale=0, created_by=self.user)

    def _devis_row(self, resp):
        return next(d for d in resp.data['devis'] if d['id'] == self.devis.id)

    def test_devis_sans_lien_lecture_null(self):
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self._devis_row(resp)['lecture'])

    def test_devis_consulte_expose_vues_et_dates(self):
        now = timezone.now()
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            view_count=4,
            first_viewed_at=now - timedelta(days=3),
            last_viewed_at=now - timedelta(minutes=30))

        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        row = self._devis_row(resp)
        self.assertEqual(row['lecture']['nombre_vues'], 4)
        self.assertIn('T', row['lecture']['derniere_consultation'])
        # Le badge L-NIV coexiste, inchangé (lien valide → présent).
        self.assertIsNotNone(row['share_link'])

    def test_liste_leads_expose_aussi_lecture(self):
        """La LISTE (préchargement `lecture_map` du viewset) porte le même
        bloc — l'écran kanban/liste n'a pas un contrat différent du détail."""
        ShareLink.objects.create(
            company=self.company, devis=self.devis, view_count=1,
            first_viewed_at=timezone.now(), last_viewed_at=timezone.now())
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results', resp.data)
        lead_row = next(r for r in rows if r['id'] == self.lead.id)
        devis_row = next(d for d in lead_row['devis']
                         if d['id'] == self.devis.id)
        self.assertEqual(devis_row['lecture']['nombre_vues'], 1)
