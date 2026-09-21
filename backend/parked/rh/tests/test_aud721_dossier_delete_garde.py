"""AUD721 — le DELETE d'un `DossierEmploye` n'efface plus les pièces légales.

DÉFAUT (rouge avant ce correctif) : `DossierEmployeViewSet` n'avait aucun
`destroy()`/`perform_destroy()`. Le DELETE HTTP standard effaçait EN CASCADE
(au moins 38 FK `employe→DossierEmploye` en `on_delete=CASCADE`) les bulletins
de paie déposés, les ACCIDENTS DU TRAVAIL (déclaration CNSS obligatoire par la
loi), les visites médicales, les sanctions et les documents du coffre — le
chemin métier prévu (`services.sortir_employe`, qui PRÉSERVE le dossier) était
entièrement contourné par une seule requête.

Après correctif : la suppression est refusée dès qu'une de ces pièces existe et
renvoie vers la sortie d'employé ; un dossier vraiment vierge reste supprimable
et laisse une note au chatter.
"""
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh.models import (
    AccidentTravail,
    DocumentEmploye,
    DossierEmploye,
    Sanction,
    VisiteMedicale,
)

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SuppressionDossierEmployeTests(TestCase):
    def setUp(self):
        self.co = make_company('aud721-rh', 'A')
        self.rh = make_user(self.co, 'aud721-rh-user')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='Tazi', prenom='Reda',
            date_embauche=date(2024, 1, 1))

    def _attachment(self):
        from django.contrib.contenttypes.models import ContentType
        return Attachment.objects.create(
            company=self.co,
            content_type=ContentType.objects.get_for_model(DossierEmploye),
            object_id=self.emp.id,
            file_key=f'attachments/{self.co.id}/aud721.pdf',
            filename='contrat.pdf', size=10, mime='application/pdf')

    def test_accident_du_travail_bloque_la_suppression(self):
        """La déclaration CNSS est une obligation légale : elle ne s'efface pas
        par ricochet."""
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-AUD721-1',
            date_accident=date(2026, 3, 2))
        resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('accidents_travail', resp.data['detail'])
        self.assertIn('sortir', resp.data['detail'])
        self.assertTrue(DossierEmploye.objects.filter(pk=self.emp.pk).exists())
        self.assertEqual(AccidentTravail.objects.count(), 1)

    def test_document_du_coffre_bloque_la_suppression(self):
        DocumentEmploye.objects.create(
            company=self.co, employe=self.emp, attachment=self._attachment(),
            type_document=DocumentEmploye.TypeDocument.CONTRAT)
        resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(DocumentEmploye.objects.exists())

    def test_visite_medicale_bloque_la_suppression(self):
        VisiteMedicale.objects.create(company=self.co, employe=self.emp)
        resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(VisiteMedicale.objects.exists())

    def test_sanction_bloque_la_suppression(self):
        Sanction.objects.create(
            company=self.co, employe=self.emp,
            type_sanction=Sanction.TypeSanction.AVERTISSEMENT,
            motif='Retards répétés')
        resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(Sanction.objects.exists())

    def test_dossier_vierge_reste_supprimable_et_trace(self):
        resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(DossierEmploye.objects.filter(pk=self.emp.pk).exists())

    def test_la_note_de_suppression_est_ecrite_avant_la_destruction(self):
        """La note est ÉCRITE avant le DELETE (elle part ensuite en cascade avec
        le dossier, comme toute son historique — mais elle prouve que le chemin
        journalisé est bien emprunté)."""
        with mock.patch('apps.rh.views.activity.log_note') as journal:
            resp = auth(self.rh).delete(f'{EMPLOYES}{self.emp.pk}/')
        self.assertEqual(resp.status_code, 204)
        journal.assert_called_once()
        message = journal.call_args[0][2]
        self.assertIn('SUPPRIMÉ', message)
        self.assertIn('E1', message)
