"""ASTK190 (C-ASTK-043, volet FOUR-18) — `valider-dossier` exige un `valider`
booléen strict, un motif pour rejeter, et refuse de re-décider.

Constat (sonde FOUR-18) : `{"valider": "false"}` → 200 statut=valide
(`bool("false")` vaut True) ; `{}` → 200 statut=valide (défaut True).
Désormais : `{}` → 400 {valider: [...]} ; « false »/« 0 » → REJET (jamais
validation) mais 400 {motif_rejet: [...]} sans motif ; re-décider un dossier
validé ou rejeté → 409. `{"valider": true}` sur un dossier complet en
attente valide toujours (comportement de l'écran inchangé).

Run :
    python manage.py test apps.stock.test_astk_valider_dossier
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    DocumentFournisseur, DossierOnboardingFournisseur, Fournisseur,
)
from apps.stock.views.fournisseur import parse_bool_strict

User = get_user_model()
_seq = itertools.count(1)
STOCK = '/api/django/stock'


class ValiderDossierTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK190 Co', slug='astk190-co')
        self.admin = User.objects.create_user(
            username='astk190-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport ASTK190')
        self.dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        for type_document in DocumentFournisseur.TYPES_REQUIS:
            DocumentFournisseur.objects.create(
                company=self.company, dossier=self.dossier,
                type_document=type_document,
                file_key=f'attachments/{self.company.id}/{next(_seq)}.pdf',
                filename='piece.pdf', mime='application/pdf', taille=1024)

    def _decider(self, corps):
        return self.api.post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/', corps, format='json')

    def _inchange(self, statut=DossierOnboardingFournisseur.Statut.EN_ATTENTE,
                  valide_par=None, date_decision=None):
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, statut)
        self.assertEqual(self.dossier.valide_par_id, valide_par)
        self.assertEqual(self.dossier.date_decision, date_decision)

    def test_corps_vide_400(self):
        rep = self._decider({})
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertEqual(
            [str(m) for m in rep.data['valider']],
            ['Paramètre requis (true/false).'])
        self._inchange()

    def test_chaine_false_ne_valide_pas(self):
        for valeur in ('false', '0'):
            rep = self._decider({'valider': valeur})
            # Rejet (jamais validation) — mais sans motif : 400.
            self.assertEqual(rep.status_code, 400, (valeur, rep.data))
            self.assertIn('motif_rejet', rep.data)
            self._inchange()
        rep = self._decider(
            {'valider': 'false', 'motif_rejet': 'RC illisible'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(
            rep.data['statut'], DossierOnboardingFournisseur.Statut.REJETE)
        self.assertEqual(rep.data['motif_rejet'], 'RC illisible')

    def test_rejet_exige_motif(self):
        for corps in ({'valider': False}, {'valider': False,
                                           'motif_rejet': '   '}):
            rep = self._decider(corps)
            self.assertEqual(rep.status_code, 400, (corps, rep.data))
            self.assertEqual(
                [str(m) for m in rep.data['motif_rejet']],
                ['Le motif du rejet est obligatoire.'])
            self._inchange()

    def test_valider_true_sur_dossier_complet(self):
        rep = self._decider({'valider': True})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(
            rep.data['statut'], DossierOnboardingFournisseur.Statut.VALIDE)

    def test_redecision_409(self):
        rep = self._decider({'valider': True})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.dossier.refresh_from_db()
        valide_par = self.dossier.valide_par_id
        date_decision = self.dossier.date_decision
        for corps in ({'valider': True},
                      {'valider': False, 'motif_rejet': 'Revirement'}):
            rep = self._decider(corps)
            self.assertEqual(rep.status_code, 409, (corps, rep.data))
            self._inchange(DossierOnboardingFournisseur.Statut.VALIDE,
                           valide_par, date_decision)

    def test_redecision_d_un_rejet_409(self):
        rep = self._decider({'valider': False, 'motif_rejet': 'RC absent'})
        self.assertEqual(rep.status_code, 200, rep.data)
        rep = self._decider({'valider': True})
        self.assertEqual(rep.status_code, 409, rep.data)
        self.dossier.refresh_from_db()
        self.assertEqual(
            self.dossier.statut, DossierOnboardingFournisseur.Statut.REJETE)

    def test_parse_bool_strict(self):
        self.assertIsNone(parse_bool_strict(None))
        for vrai in (True, 'true', 'True', '1', 1, 'on'):
            self.assertIs(parse_bool_strict(vrai), True, vrai)
        for faux in (False, 'false', 'False', '0', 0, 'off', ''):
            self.assertIs(parse_bool_strict(faux), False, faux)
