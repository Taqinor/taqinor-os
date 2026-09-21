"""Tests FG175 — moteur d'échéances RH unifié + alertes d'expiration.

Couvre :
* ``selectors.echeances_rh`` : union habilitations (FG173) + certifications
  (FG174) + documents employé (FG159) qui expirent dans la fenêtre, échéances
  déjà dépassées incluses, lignes sans échéance / inactives / hors fenêtre
  exclues.
* ``jours_restants`` : positif (à venir), 0 (aujourd'hui), négatif (expiré),
  calculé sur la date ``today`` passée (sélecteur pur, déterministe).
* Tri par échéance la plus proche d'abord.
* Isolation multi-société : B ne voit pas les échéances de A.
* Endpoint ``GET /api/django/rh/echeances/?within=N`` (scopé société, permission).
* Commande ``alertes_expiration_rh`` : ``notify`` appelé une fois par échéance et
  par destinataire (mocké), best-effort cross-app via le service notifications.
"""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh import selectors
from apps.rh.models import (
    Certification, DocumentEmploye, DossierEmploye, Habilitation,
)

User = get_user_model()

ECHE = '/api/django/rh/echeances/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Test', prenom='E'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def make_attachment(company, employe):
    ct = ContentType.objects.get_for_model(DossierEmploye)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=employe.id,
        file_key=f'attachments/{Attachment.objects.count()}.pdf',
        filename='f.pdf', size=1, mime='application/pdf')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EcheancesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('eche-a', 'A')
        self.emp = make_employe(self.co, 'E001')
        self.today = date(2026, 6, 1)

    def test_union_des_trois_familles_dans_la_fenetre(self):
        # Une habilitation, une certification et un document expirant sous 30 j.
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=self.today + timedelta(days=10))
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='travail_hauteur',
            date_validite=self.today + timedelta(days=20))
        DocumentEmploye.objects.create(
            company=self.co, employe=self.emp,
            attachment=make_attachment(self.co, self.emp),
            type_document='contrat',
            date_expiration=self.today + timedelta(days=5))

        rows = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        self.assertEqual(len(rows), 3)
        types = {r['type'] for r in rows}
        self.assertEqual(
            types, {'habilitation', 'certification', 'document'})
        # Toutes les lignes portent les champs normalisés attendus.
        for r in rows:
            self.assertIn('employe_id', r)
            self.assertIn('employe', r)
            self.assertIn('libelle', r)
            self.assertIn('date_validite', r)
            self.assertIn('jours_restants', r)
            self.assertEqual(r['employe_id'], self.emp.id)

    def test_tri_par_echeance_la_plus_proche(self):
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='harnais',
            date_validite=self.today + timedelta(days=25))
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='br',
            date_validite=self.today + timedelta(days=3))
        rows = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        dates = [r['date_validite'] for r in rows]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(rows[0]['type'], 'habilitation')

    def test_jours_restants_a_venir_aujourdhui_et_expire(self):
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=self.today + timedelta(days=7))
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='secourisme_sst',
            date_validite=self.today)            # expire aujourd'hui
        DocumentEmploye.objects.create(
            company=self.co, employe=self.emp,
            attachment=make_attachment(self.co, self.emp),
            type_document='cin',
            date_expiration=self.today - timedelta(days=4))  # déjà expiré
        rows = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        by_type = {r['type']: r for r in rows}
        self.assertEqual(by_type['habilitation']['jours_restants'], 7)
        self.assertEqual(by_type['certification']['jours_restants'], 0)
        self.assertEqual(by_type['document']['jours_restants'], -4)
        # Échéance déjà passée INCLUSE (ce qui doit alerter).
        self.assertEqual(len(rows), 3)

    def test_exclut_hors_fenetre_sans_echeance_et_inactifs(self):
        # Hors fenêtre (au-delà de within_days) → exclu.
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=self.today + timedelta(days=60))
        # Sans échéance → exclu.
        Certification.objects.create(
            company=self.co, employe=self.emp, type_certification='conduite',
            date_validite=None)
        # Inactif (même dans la fenêtre) → exclu pour les titres.
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='br',
            date_validite=self.today + timedelta(days=5), actif=False)
        # Document sans échéance → exclu.
        DocumentEmploye.objects.create(
            company=self.co, employe=self.emp,
            attachment=make_attachment(self.co, self.emp),
            type_document='diplome', date_expiration=None)
        rows = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        self.assertEqual(rows, [])

    def test_scope_societe(self):
        co_b = make_company('eche-b', 'B')
        emp_b = make_employe(co_b, 'B001')
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=self.today + timedelta(days=5))
        Habilitation.objects.create(
            company=co_b, employe=emp_b, type_habilitation='b1v',
            date_validite=self.today + timedelta(days=5))
        rows_a = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        rows_b = selectors.echeances_rh(co_b, within_days=30, today=self.today)
        self.assertEqual(len(rows_a), 1)
        self.assertEqual(len(rows_b), 1)
        self.assertEqual(rows_a[0]['employe_id'], self.emp.id)
        self.assertEqual(rows_b[0]['employe_id'], emp_b.id)

    def test_company_absente_renvoie_liste_vide(self):
        self.assertEqual(selectors.echeances_rh(None), [])


class EcheancesEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('eche-ep', 'A')
        self.emp = make_employe(self.co, 'E001')
        self.user = make_user(self.co, 'eche-resp')
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=timezone.localdate() + timedelta(days=5))

    def test_endpoint_liste_les_echeances(self):
        resp = auth(self.user).get(ECHE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['type'], 'habilitation')

    def test_within_restreint_la_fenetre(self):
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='harnais',
            date_validite=timezone.localdate() + timedelta(days=40))
        # within=10 → seule l'habilitation à 5 j ressort.
        resp = auth(self.user).get(ECHE, {'within': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        # within=60 → les deux.
        resp = auth(self.user).get(ECHE, {'within': 60})
        self.assertEqual(len(resp.data), 2)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'eche-normal', role='normal')
        resp = auth(normal).get(ECHE)
        self.assertEqual(resp.status_code, 403)


class AlertesExpirationCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('eche-cmd', 'A')
        self.emp = make_employe(self.co, 'E001')
        self.resp_user = make_user(self.co, 'cmd-resp', role='responsable')
        # Deux échéances dans la fenêtre par défaut (30 j).
        Habilitation.objects.create(
            company=self.co, employe=self.emp, type_habilitation='b1v',
            date_validite=timezone.localdate() + timedelta(days=5))
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='travail_hauteur',
            date_validite=timezone.localdate() + timedelta(days=10))

    def test_dispatch_une_notif_par_echeance(self):
        with mock.patch(
                'apps.notifications.services.notify') as notify:
            call_command(
                'alertes_expiration_rh', '--within', '30', stdout=StringIO())
        # Deux échéances × un destinataire responsable = 2 appels.
        self.assertEqual(notify.call_count, 2)
        # Type d'événement valide passé au service.
        for call in notify.call_args_list:
            self.assertEqual(call.args[1], 'warranty_expiring')
            self.assertEqual(call.kwargs.get('company'), self.co)

    def test_dry_run_n_emet_rien(self):
        with mock.patch(
                'apps.notifications.services.notify') as notify:
            call_command(
                'alertes_expiration_rh', '--dry-run', stdout=StringIO())
        notify.assert_not_called()

    def test_scope_company_option(self):
        co_b = make_company('eche-cmd-b', 'B')
        emp_b = make_employe(co_b, 'B001')
        make_user(co_b, 'cmd-resp-b', role='responsable')
        Habilitation.objects.create(
            company=co_b, employe=emp_b, type_habilitation='b1v',
            date_validite=timezone.localdate() + timedelta(days=5))
        with mock.patch(
                'apps.notifications.services.notify') as notify:
            call_command(
                'alertes_expiration_rh', '--company', str(self.co.id),
                stdout=StringIO())
        # Seules les 2 échéances de la société A → 2 appels (B non touché).
        self.assertEqual(notify.call_count, 2)
        for call in notify.call_args_list:
            self.assertEqual(call.kwargs.get('company'), self.co)
