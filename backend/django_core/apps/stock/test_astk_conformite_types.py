"""ASTK188 (C-ASTK-043, volet FOUR-16) — « pièce de conformité manquante » =
TYPES requis (ARF, CNSS, RC, assurance) comparés aux pièces présentes et
valides : un fournisseur sans aucune pièce n'est plus « conformité OK ».

Sonde FOUR-16 : conformite_ok=True, manquants=0 pour un fournisseur neuf.

Source réelle : DocumentConformiteFournisseur.Type,
services.fournisseur_conformite_manquante, vue-360 — aucun mock.

Note : `test_vue360_conforme_contrat` (contrat fournisseur_conformite.json,
ASTK166) n'est pas ici — le contrat n'est pas encore sur la branche ; la clé
est affirmée par sa forme (liste de codes de types) ci-dessous.

Run :
    python manage.py test apps.stock.test_astk_conformite_types -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AchatsParametres, DocumentConformiteFournisseur, Fournisseur,
)
from apps.stock.services import (
    bcf_warning_conformite, check_paiement_conformite_gate,
    fournisseur_conformite_manquante,
)
from authentication.models import Company

User = get_user_model()

TOUS = {'arf', 'cnss', 'rc', 'assurance'}


class ConformiteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK188', slug='astk188-co')
        self.user = User.objects.create_user(
            username='astk188-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK188')

    def _piece(self, type_doc, jours=90, sans_date=False):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=type_doc,
            date_expiration=(None if sans_date else
                             timezone.now().date() + timedelta(days=jours)))

    def _types(self):
        return {p['type_document']
                for p in fournisseur_conformite_manquante(self.fournisseur)}

    def _vue360(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        rep = api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/vue-360/')
        self.assertEqual(rep.status_code, 200, rep.data)
        return rep.data

    def test_sans_piece_non_conforme(self):
        self.assertEqual(self._types(), TOUS)
        data = self._vue360()
        self.assertFalse(data['conformite_ok'])
        self.assertEqual(set(data['conformite_documents_manquants']), TOUS)
        # Même fonction lue par le warning BCF et la garde paiement.
        self.assertIsNotNone(bcf_warning_conformite(self.fournisseur))
        AchatsParametres.objects.create(
            company=self.company, bloquer_paiement_conformite_expiree=True)
        with self.assertRaises(ValueError):
            check_paiement_conformite_gate(self.company, self.fournisseur)

    def test_types_manquants_listes(self):
        self._piece('arf')
        self._piece('cnss')
        self.assertEqual(self._types(), {'rc', 'assurance'})
        data = self._vue360()
        self.assertFalse(data['conformite_ok'])
        self.assertEqual(set(data['conformite_documents_manquants']),
                         {'rc', 'assurance'})

    def test_piece_sans_date_a_completer(self):
        for t in ('arf', 'cnss', 'assurance'):
            self._piece(t)
        self._piece('rc', sans_date=True)
        problemes = fournisseur_conformite_manquante(self.fournisseur)
        self.assertEqual(len(problemes), 1)
        self.assertEqual(problemes[0]['type_document'], 'rc')
        self.assertEqual(problemes[0]['motif'], 'sans date')

    def test_piece_expiree_et_en_regle(self):
        for t in ('arf', 'cnss', 'rc'):
            self._piece(t)
        self._piece('assurance', jours=-1)
        problemes = fournisseur_conformite_manquante(self.fournisseur)
        self.assertEqual([(p['type_document'], p['motif'])
                          for p in problemes], [('assurance', 'expiré')])
        self._piece('assurance')
        self.assertEqual(self._types(), set())
        data = self._vue360()
        self.assertTrue(data['conformite_ok'])
        self.assertEqual(data['conformite_documents_manquants'], [])
