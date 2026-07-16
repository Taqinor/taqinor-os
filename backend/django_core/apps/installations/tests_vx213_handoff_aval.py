"""VX213 — Notifier les handoffs AVAL (exécution), longtemps muets.

(a) ``create_installation_from_devis`` assigne un technicien SANS notify — le
    plus gros transfert de l'entreprise est silencieux → notify à created=True
    (jamais au ré-accept idempotent) ;
(b) réassigner un chantier (PATCH ``technicien_responsable``) ne notifie pas le
    nouveau technicien → diff pré/post ;
(c) approuver/refuser une demande d'achat ne notifie jamais le DEMANDEUR →
    notify created_by à la décision (motif si refus, corps client-safe : aucun
    montant dérivé de prix_achat) ;
(d) une DA restée SOUMISE au-delà du seuil ne relance personne →
    ``_sweep_da_soumise_stale`` (miroir de ``_sweep_sav_breaching``).

Run :
    docker compose exec django_core python manage.py test \
        apps.installations.tests_vx213_handoff_aval -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.installations.models import DemandeAchat
from apps.installations.services import create_installation_from_devis
from apps.notifications.models import EventType, Notification

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestChantierAssigneNotify(TestCase):
    def setUp(self):
        self.company = _company('vx213-co', 'VX213 Co')
        self.resp = User.objects.create_user(
            username='vx213_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='VX',
            email='vx213@example.com', telephone='+212600000213')

    def _devis(self, num):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def test_a_creation_notifie_le_technicien(self):
        """(a) créer le chantier depuis un devis notifie l'installateur."""
        devis = self._devis(1)
        inst, created = create_installation_from_devis(
            devis, self.resp, self.company)
        self.assertTrue(created)
        notifs = Notification.objects.filter(
            recipient=self.resp, event_type=EventType.CHANTIER_ASSIGNE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(inst.reference, notifs.first().title)
        # Company posée serveur = celle du devis.
        self.assertEqual(notifs.first().company_id, self.company.id)

    def test_a_reaccept_idempotent_ne_re_notifie_pas(self):
        """(a) ré-accepter (chantier déjà présent) ne recrée pas de notif."""
        devis = self._devis(2)
        create_installation_from_devis(devis, self.resp, self.company)
        # 2e appel : le service renvoie le chantier existant (created=False).
        inst2, created2 = create_installation_from_devis(
            devis, self.resp, self.company)
        self.assertFalse(created2)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.resp,
                event_type=EventType.CHANTIER_ASSIGNE).count(),
            1)

    def test_b_reassignation_notifie_le_nouveau_technicien(self):
        """(b) PATCH technicien_responsable notifie le NOUVEAU technicien."""
        autre = User.objects.create_user(
            username='vx213_tech2', password='x', role_legacy='normal',
            company=self.company)
        devis = self._devis(3)
        inst, _ = create_installation_from_devis(
            devis, self.resp, self.company)
        Notification.objects.all().delete()  # ignore la notif de création
        api = _auth(self.resp)
        res = api.patch(
            f'/api/django/installations/chantiers/{inst.pk}/',
            {'technicien_responsable': autre.pk}, format='json')
        self.assertIn(res.status_code, (200, 202), res.content)
        notifs = Notification.objects.filter(
            recipient=autre, event_type=EventType.CHANTIER_ASSIGNE)
        self.assertEqual(notifs.count(), 1)

    def test_b_patch_sans_changement_ne_notifie_pas(self):
        """(b) un PATCH qui ne change pas le titulaire ne notifie pas."""
        devis = self._devis(4)
        inst, _ = create_installation_from_devis(
            devis, self.resp, self.company)
        Notification.objects.all().delete()
        api = _auth(self.resp)
        res = api.patch(
            f'/api/django/installations/chantiers/{inst.pk}/',
            {'site_ville': 'Casablanca'}, format='json')
        self.assertIn(res.status_code, (200, 202), res.content)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.CHANTIER_ASSIGNE).count(),
            0)


class TestDemandeAchatDecisionNotify(TestCase):
    def setUp(self):
        self.company = _company('vx213-da', 'VX213 DA')
        self.demandeur = User.objects.create_user(
            username='vx213_dem', password='x', role_legacy='normal',
            company=self.company)
        self.approbateur = User.objects.create_user(
            username='vx213_appro', password='x', role_legacy='responsable',
            company=self.company)

    def _da(self, statut=DemandeAchat.Statut.SOUMISE):
        return DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{MONTH}-0001',
            objet='12 panneaux', statut=statut, created_by=self.demandeur)

    def test_c_approuver_notifie_le_demandeur(self):
        da = self._da()
        api = _auth(self.approbateur)
        res = api.post(
            f'/api/django/installations/demandes-achat/{da.pk}/approuver/')
        self.assertEqual(res.status_code, 200, res.content)
        notifs = Notification.objects.filter(
            recipient=self.demandeur, event_type=EventType.DA_DECIDEE)
        self.assertEqual(notifs.count(), 1)
        self.assertIn('approuvée', notifs.first().body)

    def test_c_refuser_notifie_avec_motif(self):
        da = self._da()
        api = _auth(self.approbateur)
        res = api.post(
            f'/api/django/installations/demandes-achat/{da.pk}/refuser/',
            {'motif_refus': 'Budget dépassé'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        notif = Notification.objects.get(
            recipient=self.demandeur, event_type=EventType.DA_DECIDEE)
        self.assertIn('refusée', notif.body)
        self.assertIn('Budget dépassé', notif.body)

    def test_c_corps_sans_montant_client_safe(self):
        """(c) le corps ne contient jamais de montant (jamais dérivé de
        prix_achat) — seulement référence + objet + décision."""
        da = self._da()
        api = _auth(self.approbateur)
        api.post(
            f'/api/django/installations/demandes-achat/{da.pk}/approuver/')
        notif = Notification.objects.get(event_type=EventType.DA_DECIDEE)
        # Aucun symbole/mot de montant ne doit fuiter.
        for token in ('MAD', 'DH', 'montant', 'prix'):
            self.assertNotIn(token, notif.body)


class TestDaSoumiseStaleSweep(TestCase):
    def setUp(self):
        self.company = _company('vx213-sla', 'VX213 SLA')
        self.mgr = User.objects.create_user(
            username='vx213_mgr', password='x', role_legacy='responsable',
            company=self.company)
        self.demandeur = User.objects.create_user(
            username='vx213_sla_dem', password='x', role_legacy='normal',
            company=self.company)

    def _da_soumise_ancienne(self, jours):
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{MONTH}-0002',
            objet='câbles', statut=DemandeAchat.Statut.SOUMISE,
            created_by=self.demandeur)
        # Antidater date_modification (auto_now) sous le seuil.
        vieux = timezone.now() - timedelta(days=jours)
        DemandeAchat.objects.filter(pk=da.pk).update(date_modification=vieux)
        return da

    def test_d_da_soumise_stale_relance_les_managers(self):
        from apps.notifications.sweeps import _sweep_da_soumise_stale
        self._da_soumise_ancienne(5)
        posted = _sweep_da_soumise_stale(self.company)
        self.assertGreaterEqual(posted, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.mgr,
                event_type=EventType.DA_SOUMISE_STALE).exists())

    def test_d_da_recente_non_relancee(self):
        from apps.notifications.sweeps import _sweep_da_soumise_stale
        self._da_soumise_ancienne(1)  # sous le seuil de 3 j
        posted = _sweep_da_soumise_stale(self.company)
        self.assertEqual(posted, 0)

    def test_d_idempotent_une_relance_par_jour(self):
        from apps.notifications.sweeps import _sweep_da_soumise_stale
        self._da_soumise_ancienne(5)
        _sweep_da_soumise_stale(self.company)
        # 2e passage le même jour : dédup par link → aucune nouvelle.
        posted2 = _sweep_da_soumise_stale(self.company)
        self.assertEqual(posted2, 0)
