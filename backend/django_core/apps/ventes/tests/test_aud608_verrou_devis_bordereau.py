"""AUD608 — « Créer le devis » depuis un bordereau AO est SÉRIALISÉ.

La lecture du brouillon existant et la création du devis vivaient hors
transaction : deux clics simultanés sur « Créer le devis » lisaient tous les
deux « aucun brouillon » et le MÊME bordereau produisait DEUX devis — deux
références DEV consommées (``core.numbering``, jamais réattribuées) et deux
documents à envoyer au client.

Le bordereau est la clé d'idempotence : c'est SA ligne qui est verrouillée (elle
existe toujours, contrairement au devis qu'on s'apprête à créer).

Run :
    python manage.py test apps.ventes.tests.test_aud608_verrou_devis_bordereau -v2
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.ao.models import (
    AppelOffre, BordereauPrix, LigneBordereau, SectionBordereau,
)
from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.ventes.services import creer_devis_depuis_bordereau
from authentication.models import Company

CLAUSE = ('Marché à prix unitaires : les quantités portées au présent '
          'bordereau sont prévisionnelles.')


class TestVerrouDuBordereau(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD608 Devis',
                                              slug='aud608-devis')
        self.lead = Lead.objects.create(
            company=self.company, nom='Commune urbaine de Rabat',
            email='marches@rabat.ma')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-608-D', objet='Centrale PV',
            lead_id=self.lead.pk)
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao, clause_reserve=CLAUSE)
        section = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=1,
            libelle='Bâtiment A')
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, section=section,
            numero=1, designation='Modules 625 Wc', unite='U',
            quantite=Decimal('100.000'), prix_unitaire=Decimal('1200.00'))

    def test_la_ligne_de_bordereau_est_verrouillee(self):
        with CaptureQueriesContext(connection) as capture:
            creer_devis_depuis_bordereau(self.bordereau, company=self.company)
        verrous = [q['sql'] for q in capture.captured_queries
                   if 'FOR UPDATE' in q['sql'].upper()
                   and 'bordereau' in q['sql'].lower()]
        self.assertTrue(
            verrous,
            "Aucun SELECT ... FOR UPDATE sur le bordereau : le double-clic "
            'reste une course qui consomme deux références DEV.')

    def test_l_idempotence_est_preservee(self):
        premier, rapport1 = creer_devis_depuis_bordereau(
            self.bordereau, company=self.company)
        self.assertTrue(rapport1['cree'])
        second, rapport2 = creer_devis_depuis_bordereau(
            self.bordereau, company=self.company)
        self.assertFalse(rapport2['cree'])
        self.assertEqual(second.pk, premier.pk)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 1)

    def test_le_devis_cree_porte_bien_ses_lignes(self):
        """Non-régression : la création vit désormais dans un `with`."""
        devis, rapport = creer_devis_depuis_bordereau(
            self.bordereau, company=self.company)
        self.assertTrue(rapport['cree'])
        self.assertTrue(devis.lignes.exists())
        self.assertTrue(devis.reference.startswith('DEV'))
