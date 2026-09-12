"""NTP2P20 — Renouvellement automatique des alertes documents fournisseur
expirants (NTP2P7).

Couvre : le sélecteur pur ``documents_fournisseur_expirant`` (fenêtre
``within_days``, tri par échéance), la notification in-app immédiate au
responsable/admin (``notify_expiring_documents_fournisseur``), la tâche
planifiée idempotente PAR SOCIÉTÉ (jamais de doublon le même jour, et jamais
de collision avec le sweep XPUR1 qui partage le même EventType), et
l'endpoint ``fournisseurs/documents-expirants/?within=N``.

Run:
    python manage.py test apps.stock.test_ntp2p20_documents_fournisseur_expirants -v 2
"""
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import selectors as stock_selectors
from apps.stock.models import DocumentFournisseur, DossierOnboardingFournisseur, Fournisseur
from apps.stock.services import notify_expiring_documents_fournisseur
from apps.stock.tasks import notifier_documents_fournisseur_expirants_task

User = get_user_model()
_seq = itertools.count(1)


def _company():
    from authentication.models import Company
    n = next(_seq)
    return Company.objects.create(nom=f'NTP2P20 Co {n}', slug=f'ntp2p20-{n}')


def _user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p20-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _dossier(company, fournisseur):
    return DossierOnboardingFournisseur.objects.create(
        company=company, fournisseur=fournisseur)


def _piece(company, dossier, *, expiration):
    return DocumentFournisseur.objects.create(
        company=company, dossier=dossier,
        type_document=DocumentFournisseur.Type.ASSURANCE,
        file_key=f'attachments/{company.id}/{next(_seq)}.pdf',
        filename='piece.pdf', mime='application/pdf', taille=1024,
        date_expiration=expiration)


class TestSelecteurPur(TestCase):
    def test_dans_la_fenetre_apparait_hors_fenetre_non(self):
        company = _company()
        fournisseur = Fournisseur.objects.create(company=company, nom='F1')
        dossier = _dossier(company, fournisseur)
        today = timezone.localdate()
        _piece(company, dossier, expiration=today + timedelta(days=15))
        _piece(company, dossier, expiration=today + timedelta(days=90))

        resultat = stock_selectors.documents_fournisseur_expirant(
            company, within_days=30, today=today)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['jours_restants'], 15)
        self.assertEqual(resultat[0]['fournisseur_id'], fournisseur.id)

    def test_document_deja_expire_est_inclus(self):
        company = _company()
        fournisseur = Fournisseur.objects.create(company=company, nom='F2')
        dossier = _dossier(company, fournisseur)
        today = timezone.localdate()
        _piece(company, dossier, expiration=today - timedelta(days=5))

        resultat = stock_selectors.documents_fournisseur_expirant(
            company, within_days=30, today=today)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['jours_restants'], -5)

    def test_document_sans_expiration_jamais_liste(self):
        company = _company()
        fournisseur = Fournisseur.objects.create(company=company, nom='F3')
        dossier = _dossier(company, fournisseur)
        _piece(company, dossier, expiration=None)
        resultat = stock_selectors.documents_fournisseur_expirant(
            company, within_days=30)
        self.assertEqual(resultat, [])


class TestNotification(TestCase):
    def test_notifie_le_responsable_configure(self):
        from apps.notifications.models import Notification, EventType

        company = _company()
        responsable = _user(company, role='responsable')
        fournisseur = Fournisseur.objects.create(company=company, nom='F4')
        dossier = _dossier(company, fournisseur)
        _piece(company, dossier,
               expiration=timezone.localdate() + timedelta(days=15))

        nb = notify_expiring_documents_fournisseur(company, jours=30)
        self.assertEqual(nb, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=responsable,
            event_type=EventType.SUPPLIER_DOC_EXPIRING).exists())


class TestTachePlanifiee(TestCase):
    def test_idempotent_une_seule_fois_par_jour(self):
        company = _company()
        _user(company, role='responsable')
        fournisseur = Fournisseur.objects.create(company=company, nom='F5')
        dossier = _dossier(company, fournisseur)
        _piece(company, dossier,
               expiration=timezone.localdate() + timedelta(days=15))

        resultat_1 = notifier_documents_fournisseur_expirants_task()
        self.assertEqual(resultat_1.get(company.id), 1)
        resultat_2 = notifier_documents_fournisseur_expirants_task()
        self.assertEqual(resultat_2.get(company.id), 0)

    def test_ne_collisionne_pas_avec_le_sweep_xpur1(self):
        """XPUR1 (notifier_documents_conformite_expirants_task) et NTP2P20
        partagent le même EventType.SUPPLIER_DOC_EXPIRING mais visent des
        modèles DIFFÉRENTS : l'un ne doit jamais « consommer » le guard
        idempotent de l'autre pour la journée."""
        from apps.stock.tasks import notifier_documents_conformite_expirants_task
        from apps.stock.models import DocumentConformiteFournisseur

        company = _company()
        _user(company, role='responsable')
        fournisseur = Fournisseur.objects.create(company=company, nom='F6')
        DocumentConformiteFournisseur.objects.create(
            company=company, fournisseur=fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.localdate() + timedelta(days=10))
        dossier = _dossier(company, fournisseur)
        _piece(company, dossier,
               expiration=timezone.localdate() + timedelta(days=15))

        # XPUR1 tourne EN PREMIER (même EventType, guard par société).
        resultat_xpur1 = notifier_documents_conformite_expirants_task()
        self.assertEqual(resultat_xpur1.get(company.id), 1)
        # NTP2P20 doit quand même notifier (lien distinct).
        resultat_ntp2p20 = notifier_documents_fournisseur_expirants_task()
        self.assertEqual(resultat_ntp2p20.get(company.id), 1)


class TestEndpoint(TestCase):
    def test_endpoint_liste_les_documents_expirants(self):
        company = _company()
        user = _user(company, role='responsable')
        api = _api(user)
        fournisseur = Fournisseur.objects.create(company=company, nom='F7')
        dossier = _dossier(company, fournisseur)
        _piece(company, dossier,
               expiration=timezone.localdate() + timedelta(days=10))

        resp = api.get(
            '/api/django/stock/fournisseurs/documents-expirants/?within=30')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['fournisseur_id'], fournisseur.id)
