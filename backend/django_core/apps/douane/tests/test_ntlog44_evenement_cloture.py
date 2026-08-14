"""NTLOG44 (volet douane) — émission de l'événement ``core.events.
dossier_export_cloture`` à la clôture d'un ``DossierExport``.

Le volet ``apps/transport`` (``ordre_transport_livre``/
``litige_transport_ouvert``) est HORS PÉRIMÈTRE de ce test (lane
concurrente, voir ``docs/plans/PLAN_SUPPLY.md`` NTLOG44). Le volet
``dossier_import_cloture`` reste BLOCKED (NTLOG10 — voir
``apps/douane/apps.py``) : ``dossier_export_cloture`` couvre le volet EXPORT
réellement construit dans cette app.

Run :
    python manage.py test apps.douane.tests.test_ntlog44_evenement_cloture -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.douane.models import DossierExport
from apps.douane.services import cloturer_dossier_export
from core.events import dossier_export_cloture

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog44-co-{n}', defaults={'nom': f'NTLOG44 Co {n}'})
    return company


def make_user(company):
    return User.objects.create_user(
        username=f'ntlog44-{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


class TestEvenementClotureDossierExport(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG44-1',
            statut=DossierExport.Statut.LEVE)

    def test_cloture_emet_l_evenement_avec_les_bons_arguments(self):
        recus = []

        def _recepteur(sender, **kwargs):
            recus.append(kwargs)

        dossier_export_cloture.connect(_recepteur)
        self.addCleanup(dossier_export_cloture.disconnect, _recepteur)

        cloturer_dossier_export(self.dossier, user=self.user)

        self.assertEqual(len(recus), 1, recus)
        kwargs = recus[0]
        self.assertEqual(kwargs['dossier'].pk, self.dossier.pk)
        self.assertEqual(kwargs['company'], self.company)
        self.assertEqual(kwargs['user'], self.user)
        self.assertEqual(kwargs['ancien_statut'], DossierExport.Statut.LEVE)

    def test_cloture_met_a_jour_le_statut(self):
        cloturer_dossier_export(self.dossier, user=self.user)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, DossierExport.Statut.CLOTURE)

    def test_cloture_idempotente_ne_reemet_pas(self):
        cloturer_dossier_export(self.dossier, user=self.user)

        recus = []

        def _recepteur(sender, **kwargs):
            recus.append(kwargs)

        dossier_export_cloture.connect(_recepteur)
        self.addCleanup(dossier_export_cloture.disconnect, _recepteur)

        cloturer_dossier_export(self.dossier, user=self.user)
        self.assertEqual(recus, [])

    def test_dossier_deja_clos_a_la_creation_ne_reemet_rien(self):
        dossier_clos = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG44-2',
            statut=DossierExport.Statut.CLOTURE)

        recus = []

        def _recepteur(sender, **kwargs):
            recus.append(kwargs)

        dossier_export_cloture.connect(_recepteur)
        self.addCleanup(dossier_export_cloture.disconnect, _recepteur)

        cloturer_dossier_export(dossier_clos, user=self.user)
        self.assertEqual(recus, [])
