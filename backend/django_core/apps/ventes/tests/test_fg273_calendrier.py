"""FG273 — tests du calendrier réglementaire & alertes d'expiration.

Couvre : agrégation des échéances (pièces datées, dépôt en instruction, validité
d'accord), statuts d'alerte expire/imminent/a_venir, scope société, filtre.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg273_calendrier -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ventes.models import (
    Devis, RegulatoryDossier, DossierChecklistItem)
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_dossier(company, user, ref, **kw):
    client = Client.objects.create(
        company=company, nom='Naciri', prenom='Imane',
        email=f'i_{ref}@example.com', telephone='+212655555555')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)
    return RegulatoryDossier.objects.create(
        company=company, devis=devis, regime_8221='accord_raccordement',
        **kw)


class CalendrierReglementaireTest(TestCase):
    def setUp(self):
        self.company = make_company('cal-acme')
        self.other = make_company('cal-other')
        self.user = make_user(self.company, 'cal_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/calendrier-reglementaire/'
        self.today = timezone.now().date()

    def _checklist(self, dossier, days_offset, **kw):
        return DossierChecklistItem.objects.create(
            company=dossier.company, dossier=dossier,
            code=kw.pop('code', 'piece'), libelle=kw.pop('libelle', 'Pièce'),
            etape='depot', statut=kw.pop('statut', 'a_faire'),
            date_echeance=self.today + timedelta(days=days_offset), **kw)

    def test_overdue_and_imminent_and_future_buckets(self):
        d = make_dossier(self.company, self.user, 'DEV-CAL-1')
        self._checklist(d, -3, code='p_expire', libelle='Pièce expirée')
        self._checklist(d, 10, code='p_imminent', libelle='Pièce imminente')
        self._checklist(d, 90, code='p_future', libelle='Pièce future')
        resp = self.api.get(self.url, {'seuil': 30})
        self.assertEqual(resp.status_code, 200, resp.content)
        resume = resp.data['resume']
        self.assertEqual(resume['expire'], 1)
        self.assertEqual(resume['imminent'], 1)
        self.assertEqual(resume['a_venir'], 1)
        # Tri par date d'échéance croissante : l'expirée en premier.
        self.assertEqual(resp.data['echeances'][0]['statut_alerte'], 'expire')

    def test_validity_of_accord_creates_mes_deadline(self):
        # Accord approuvé il y a presque 1 an → date limite MES imminente.
        make_dossier(
            self.company, self.user, 'DEV-CAL-2', statut='approuve',
            date_decision=self.today - timedelta(days=350))
        resp = self.api.get(self.url, {'seuil': 30, 'validite': 365})
        types = {e['type'] for e in resp.data['echeances']}
        self.assertIn('validite_accord', types)
        mes = next(e for e in resp.data['echeances']
                   if e['type'] == 'validite_accord')
        self.assertEqual(mes['statut_alerte'], 'imminent')

    def test_filter_by_statut(self):
        d = make_dossier(self.company, self.user, 'DEV-CAL-3')
        self._checklist(d, -5, code='a', libelle='A')
        self._checklist(d, 60, code='b', libelle='B')
        resp = self.api.get(self.url, {'statut': 'expire'})
        self.assertTrue(all(
            e['statut_alerte'] == 'expire' for e in resp.data['echeances']))
        self.assertEqual(len(resp.data['echeances']), 1)

    def test_completed_pieces_excluded(self):
        d = make_dossier(self.company, self.user, 'DEV-CAL-4')
        self._checklist(d, -5, code='done', libelle='Fournie',
                        statut='fourni')
        resp = self.api.get(self.url)
        self.assertEqual(len(resp.data['echeances']), 0)

    def test_scoped_to_company(self):
        d = make_dossier(self.company, self.user, 'DEV-CAL-5')
        self._checklist(d, 5, code='mine', libelle='Mienne')
        other_user = make_user(self.other, 'cal_o')
        od = make_dossier(self.other, other_user, 'DEV-CAL-OTHER')
        DossierChecklistItem.objects.create(
            company=self.other, dossier=od, code='theirs',
            libelle='Autre société', etape='depot', statut='a_faire',
            date_echeance=self.today + timedelta(days=5))
        resp = self.api.get(self.url)
        libelles = {e['libelle'] for e in resp.data['echeances']}
        self.assertIn('Mienne', libelles)
        self.assertNotIn('Autre société', libelles)
