"""ADEV24 (C-ADEV-031) — tout devis créé porte la numérotation CONFIGURÉE de
la société (``create_numbered(Devis, company, 'devis', …)``), plus jamais le
littéral ``'DEV'``.

* garde de classe (AST du paquet ventes, hors tests) : aucun appel
  ``create_with_reference(Devis, '<littéral>', …)`` ;
* chemins réels : brouillon du pipeline, ticket SAV, OCR — préfixe ``DVX-``
  configuré ; sans préfixe, ``DEV-`` comme avant.

Test-du-test : remettre un seul ``'DEV'`` littéral ⇒ la garde AST échoue.
"""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead
from apps.parametres.models import CompanyProfile
from apps.ventes.domain.creation import (
    create_devis_pour_ticket, create_draft_devis_from_ocr,
)
from apps.ventes.domain.pipeline import _creer_brouillon
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

VENTES = Path(__file__).resolve().parents[1]


class GardeAucunLitteralTests(SimpleTestCase):
    def test_aucun_create_with_reference_devis_litteral(self):
        fautes = []
        for fichier in sorted(VENTES.rglob('*.py')):
            if 'tests' in fichier.parts or 'migrations' in fichier.parts:
                continue
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                fn = noeud.func
                nom = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
                if nom != 'create_with_reference' or len(noeud.args) < 2:
                    continue
                modele, prefixe = noeud.args[0], noeud.args[1]
                if (getattr(modele, 'id', None) == 'Devis'
                        and isinstance(prefixe, ast.Constant)):
                    fautes.append('%s:%s' % (fichier.relative_to(VENTES),
                                             noeud.lineno))
        self.assertEqual(fautes, [])


class NumerotationConfigureeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADEV24', slug='adev24-co')
        self.user = User.objects.create_user(
            username='adev24_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client ADEV24',
            email='adev24@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead ADEV24', telephone='0612345678',
            email='adev24@example.com')

    def _configurer(self, prefixe):
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'doc_prefixes': {'devis': prefixe}})

    def _chemins(self):
        return {
            'pipeline': lambda: _creer_brouillon(SimpleNamespace(
                company=self.company, client=self.client_obj, lead=None,
                taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                user=self.user, mode_installation='',
                etude_initiale=None, layout=None)),
            'ticket': lambda: create_devis_pour_ticket(
                company=self.company, user=self.user,
                client_id=self.client_obj.pk, lignes=[]),
            'ocr': lambda: create_draft_devis_from_ocr(
                company=self.company, user=self.user, lead=self.lead,
                fields={}),
        }

    def test_prefixe_configure_sur_chaque_chemin(self):
        self._configurer('DVX')
        for nom, creer in self._chemins().items():
            with self.subTest(chemin=nom):
                devis = creer()
                relu = Devis.objects.get(pk=devis.pk)
                self.assertTrue(relu.reference.startswith('DVX-'),
                                relu.reference)
        refs = list(Devis.objects.filter(company=self.company)
                    .values_list('reference', flat=True))
        self.assertEqual(len(refs), len(set(refs)))

    def test_sans_prefixe_dev_inchange(self):
        devis = self._chemins()['ticket']()
        self.assertTrue(devis.reference.startswith('DEV-'), devis.reference)
