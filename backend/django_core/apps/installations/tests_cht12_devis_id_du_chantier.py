"""CHT12 — navigation devis↔chantier scopée société.

Couvre :
  * ``installations.selectors.devis_id_du_chantier`` (nouveau) — scopé société ;
  * ``installations.selectors.installation_for_devis`` gagne un paramètre
    ``company=None`` OPTIONNEL — ``None`` (défaut) préserve le comportement
    d'origine, une société fournie scope la lecture (jamais de fuite
    cross-tenant).

Run :
    python manage.py test apps.installations.tests_cht12_devis_id_du_chantier -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.selectors import (
    devis_id_du_chantier, installation_for_devis,
)
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht12-inst-co-{n}',
        defaults={'nom': nom or f'CHT12 Inst Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT12',
        email=f'cht12-inst-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CHT12INST-{n}', client=client,
        taux_tva=Decimal('20'))


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CHT12INST-{n}', client=client,
        devis=devis)


class TestDevisIdDuChantier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.chantier = make_installation(
            self.company, self.client_obj, self.devis)

    def test_renvoie_le_devis_id_scope_societe(self):
        self.assertEqual(
            devis_id_du_chantier(self.company, self.chantier.id), self.devis.id)

    def test_chantier_d_une_autre_societe_renvoie_none(self):
        autre = make_company()
        self.assertIsNone(devis_id_du_chantier(autre, self.chantier.id))

    def test_chantier_sans_devis_renvoie_none(self):
        chantier_sans_devis = make_installation(self.company, self.client_obj)
        self.assertIsNone(
            devis_id_du_chantier(self.company, chantier_sans_devis.id))

    def test_chantier_inconnu_renvoie_none(self):
        self.assertIsNone(devis_id_du_chantier(self.company, 999999))

    def test_sans_chantier_id_renvoie_none(self):
        self.assertIsNone(devis_id_du_chantier(self.company, None))


class TestInstallationForDevisNonRegression(TestCase):
    """Les 3 appelants existants (ventes/serializers.py, ventes/selectors.py,
    ventes/connection_declaration_view.py) appellent tous
    ``installation_for_devis(devis)`` SANS ``company`` — comportement
    inchangé exigé."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.chantier = make_installation(
            self.company, self.client_obj, self.devis)

    def test_appel_sans_company_est_inchange(self):
        inst = installation_for_devis(self.devis)
        self.assertEqual(inst.id, self.chantier.id)

    def test_appel_avec_company_scope_la_lecture(self):
        autre = make_company()
        self.assertIsNone(installation_for_devis(self.devis, company=autre))
        self.assertEqual(
            installation_for_devis(self.devis, company=self.company).id,
            self.chantier.id)

    def test_sans_chantier_renvoie_none_avec_ou_sans_company(self):
        devis_orphelin = make_devis(self.company, self.client_obj)
        self.assertIsNone(installation_for_devis(devis_orphelin))
        self.assertIsNone(
            installation_for_devis(devis_orphelin, company=self.company))
