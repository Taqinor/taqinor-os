"""QJ1bis (fondateur 07/09/2026) — CHAQUE ouverture cliente laisse une trace.

Avant : seule la PREMIÈRE ouverture du lien public notifiait le responsable
et posait une note chatter — un client qui revenait trois fois sur sa
proposition était invisible. Désormais chaque RÉOUVERTURE au-delà de la
fenêtre de sessionisation (15 min) pose une note « a rouvert » dans le
chatter du lead ET renvoie la notification ; deux GET rapprochés (le client
navigue/recharge) comptent pour UNE lecture. Le jeton interne (L-INTPREV)
reste sans aucune trace.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead, LeadActivity
from apps.notifications.models import Notification
from apps.ventes.models import Devis, ShareLink

User = get_user_model()

_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-QJ1BIS-0001.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub',
)


class ReouvertureTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='qj1bis', defaults={'nom': 'QJ1bis'})[0]
        self.owner = User.objects.create_user(
            username='qj1bis-owner', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJ1bis')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QJ1bis', owner=self.owner)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJ1BIS-0001',
            client=self.client_obj, lead=self.lead,
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    def _get(self):
        with _PATCH_GEN, _PATCH_DL:
            return APIClient().get(
                f'/api/django/public/document/{self.link.token}/')

    def _reculer_derniere_vue(self, minutes):
        ShareLink.objects.filter(pk=self.link.pk).update(
            last_viewed_at=timezone.now() - timedelta(minutes=minutes))

    def _notes_reouverture(self):
        return LeadActivity.objects.filter(
            lead=self.lead, user=None,
            body__contains='a rouvert le devis')

    def test_une_reouverture_apres_la_fenetre_note_et_notifie(self):
        self._get()
        avant = Notification.objects.filter(recipient=self.owner).count()
        self._reculer_derniere_vue(20)
        self._get()
        self.assertEqual(self._notes_reouverture().count(), 1)
        self.assertGreater(
            Notification.objects.filter(recipient=self.owner).count(), avant)

    def test_un_rechargement_dans_la_fenetre_ne_renotifie_pas(self):
        self._get()
        self._get()  # < 15 min après : même session de lecture
        self.assertEqual(self._notes_reouverture().count(), 0)

    def test_la_premiere_ouverture_garde_le_comportement_QJ1(self):
        self._get()
        self.assertEqual(LeadActivity.objects.filter(
            lead=self.lead, body__contains='a ouvert le devis').count(), 1)
        self.assertEqual(self._notes_reouverture().count(), 0)

    def test_le_jeton_interne_ne_declenche_jamais_rien(self):
        self._get()
        self._reculer_derniere_vue(20)
        interne = self.link.jeton_interne_effectif()
        with _PATCH_GEN, _PATCH_DL:
            APIClient().get(f'/api/django/public/document/{interne}/')
        self.assertEqual(self._notes_reouverture().count(), 0)

    def test_chaque_nouvelle_visite_est_dans_l_historique(self):
        """Trois visites espacées ⇒ trois traces chatter (1 ouverture +
        2 réouvertures) : l'historique du lead raconte TOUT, même quand les
        notifications ont disparu."""
        self._get()
        self._reculer_derniere_vue(30)
        self._get()
        self._reculer_derniere_vue(30)
        self._get()
        self.assertEqual(self._notes_reouverture().count(), 2)
