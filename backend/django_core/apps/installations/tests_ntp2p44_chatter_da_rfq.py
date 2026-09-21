"""NTP2P44 — Historique chatter sur ``DemandeAchat``.

Réutilise le chatter générique ``records.Activity`` (patron ``crm.LeadActivity``
/ ``innovation.idee``, ARC8/ARC30) — AUCUN modèle ``DemandeAchatActivity``
maison : ``installations.demandeachat`` était déjà une cible ARC30 (SCA36,
``ChatterViewSetMixin`` déjà câblé sur ``DemandeAchatViewSet``) : ce lot
ajoute l'AUTO-LOG ancien→nouveau à chaque transition réelle, posé dans le
service partagé ``appliquer_statut_document`` (AUD819) — critère
d'acceptation : approuver une demande d'achat crée l'entrée automatiquement,
sans action manuelle de l'approbateur.

Run :
    python manage.py test apps.installations.tests_ntp2p44_chatter_da_rfq -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p44-co-{n}', defaults={'nom': f'NTP2P44 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p44-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _chatter(api, base, obj_id):
    return api.get(f'{base}/{obj_id}/chatter/historique/')


class DemandeAchatAutoLogChatterTests(TestCase):
    """AUD819 + NTP2P44 — ``appliquer_statut_document`` journalise CHAQUE
    transition réelle sur le chatter générique de la ``DemandeAchat``."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{next(_seq)}',
            objet='Panneaux chantier X', created_by=self.user)

    def test_approuver_cree_entree_chatter_automatiquement(self):
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)

        r = _chatter(self.api, f'{BASE}/demandes-achat', self.da.id)
        self.assertEqual(r.status_code, 200, r.data)
        entries = {(e['field'], e['old_value'], e['new_value'])
                   for e in r.data}
        self.assertIn(('statut', 'brouillon', 'soumise'), entries)
        self.assertIn(('statut', 'soumise', 'approuvee'), entries)
        for e in r.data:
            if e['new_value'] == 'approuvee':
                self.assertEqual(e['kind'], 'modification')
                self.assertEqual(e['user_username'], self.user.username)

    def test_refuser_cree_entree_chatter(self):
        self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/refuser/',
            {'motif_refus': 'Budget dépassé'})
        self.assertEqual(r.status_code, 200, r.data)

        r = _chatter(self.api, f'{BASE}/demandes-achat', self.da.id)
        entries = {(e['field'], e['old_value'], e['new_value'])
                   for e in r.data}
        self.assertIn(('statut', 'soumise', 'refusee'), entries)

    def test_reapplication_idempotente_ne_journalise_rien(self):
        """Re-soumettre une demande déjà ``soumise`` (statut inchangé) ne
        transite pas (cf. ``appliquer_statut_document``) et ne doit donc
        journaliser aucune entrée supplémentaire."""
        self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        r_avant = _chatter(self.api, f'{BASE}/demandes-achat', self.da.id)
        n_avant = len(r_avant.data)

        self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        r_apres = _chatter(self.api, f'{BASE}/demandes-achat', self.da.id)
        self.assertEqual(len(r_apres.data), n_avant)

    def test_noter_manuel_toujours_disponible(self):
        """Le chatter générique reste utilisable pour une note manuelle
        (déjà câblé SCA36) — non-régression."""
        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/noter/',
            {'body': 'Fournisseur relancé par téléphone.'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['kind'], 'note')
