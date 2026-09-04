"""AUD143 — un client portail ne peut plus télécharger le PDF d'un devis
BROUILLON via le chemin `/proposal` authentifié.

Deux gardes divergaient sur le MÊME document : ``ventes.selectors.
devis_du_client_portail`` (utilisé par « Mes devis ») exclut explicitement le
brouillon — « un devis non envoyé n'a jamais été montré au client, l'exposer
serait une fuite de travail en cours » — tandis que ``DevisViewSet.
get_queryset`` (chemin PDF canonique NTPRT10, règle #4) ne bornait un compte
portail QUE par ``client_id=scope``, sans exclure aucun statut. Un client
devinant l'id d'un devis en préparation (chiffrage non finalisé, marges de
négociation) pouvait donc l'ouvrir en PDF via
``GET /api/django/ventes/devis/<id>/proposal/``.

Le test ROUGE de référence est conservé en commentaire : avant ce correctif,
``test_brouillon_est_desormais_introuvable_pour_le_portail`` répondait 200
avec le PDF plutôt que 404.

Run :
    python manage.py test apps.ventes.tests.test_aud143_devis_brouillon_portail -v2
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD143-{n}',
        email=f'aud143-{company.id}-{n}@example.invalid')


def make_devis(company, client, statut=Devis.Statut.ENVOYE):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-AUD143-{n}', client=client,
        statut=statut, taux_tva=Decimal('20'))


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


# Le rendu PDF réel n'est pas en cause ici (couvert par test_quote_engine.py
# et test_arc5_proposal_public_access.py) : on teste UNIQUEMENT le scoping
# d'accès (get_queryset), donc le moteur est mocké.
_PATCH_GEN = patch(
    'apps.ventes.quote_engine.generate_premium_devis_pdf',
    return_value='devis/1/DEV-AUD143.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.utils.pdf.download_pdf',
    return_value=b'%PDF-1.4 stub aud143',
)


class DevisBrouillonPortailProposalTests(TestCase):
    def setUp(self):
        self.company = make_company('aud143-co', 'AUD143 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.brouillon = make_devis(
            self.company, self.client_a, statut=Devis.Statut.BROUILLON)
        self.envoye = make_devis(
            self.company, self.client_a, statut=Devis.Statut.ENVOYE)
        self.user_a = make_portal_user(
            self.company, 'aud143-portail-a', self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    # ROUGE avant correctif : `get_queryset` ne filtrait QUE par
    # `client_id=scope`, sans exclure BROUILLON -> 200 + PDF.
    def test_brouillon_est_desormais_introuvable_pour_le_portail(self):
        resp = self.api.get(
            f'/api/django/ventes/devis/{self.brouillon.id}/proposal/')
        self.assertEqual(resp.status_code, 404)

    # Jamais 403 : un brouillon d'autrui répondait déjà 404 (existence
    # masquée) ; un brouillon DU CLIENT LUI-MÊME doit se comporter à
    # l'identique — aucun oracle d'existence ne doit fuiter.
    def test_le_404_ne_distingue_pas_dun_devis_dautrui(self):
        autre_client = make_client(self.company, 'Beta')
        devis_autrui = make_devis(
            self.company, autre_client, statut=Devis.Statut.ENVOYE)
        resp_brouillon = self.api.get(
            f'/api/django/ventes/devis/{self.brouillon.id}/proposal/')
        resp_autrui = self.api.get(
            f'/api/django/ventes/devis/{devis_autrui.id}/proposal/')
        self.assertEqual(resp_brouillon.status_code, resp_autrui.status_code)
        self.assertEqual(resp_brouillon.status_code, 404)

    @_PATCH_GEN
    @_PATCH_DL
    def test_un_devis_envoye_reste_accessible(self, m_dl, m_gen):
        resp = self.api.get(
            f'/api/django/ventes/devis/{self.envoye.id}/proposal/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_le_brouillon_est_deja_absent_de_mes_devis(self):
        """Non-régression : le sélecteur « Mes devis » excluait déjà le
        brouillon — cette tâche aligne `/proposal`, elle ne le duplique pas."""
        resp = self.api.get('/api/django/portail/mes-devis/')
        ids = {ligne['id'] for ligne in resp.data['results']}
        self.assertNotIn(self.brouillon.id, ids)
        self.assertIn(self.envoye.id, ids)
