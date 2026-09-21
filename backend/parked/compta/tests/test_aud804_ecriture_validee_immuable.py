"""AUD804 — `EcritureComptable.statut` librement modifiable en PATCH : la
séparation des tâches COMPTA40 devenait contournable avec `compta_saisir` seul.

Constat d'origine : `statut` figurait dans `Meta.fields` mais était ABSENT de
`read_only_fields` (contrairement à `NoteFraisSerializer` /
`ExerciceComptableSerializer`, protégés dans le MÊME fichier), et `update()`
faisait un `setattr` + `save()` sans contrôle de transition.
`partial_update` n'est gardé que par `compta_saisir` (l'action `valider` est
volontairement hors d'`ACTIONS_SAISIE`). Deux contournements, donc :

1. `PATCH {"statut":"validee"}` → 200, écriture VALIDÉE sans jamais passer par
   `services.valider_ecriture` — donc sans le contrôle à quatre yeux, et avec
   `valide_par`/`date_validation` restés NULL ;
2. plus grave — `update()` fait `lignes.all().delete()` puis recrée : un
   porteur de `compta_saisir` SEUL pouvait RÉÉCRIRE LES LIGNES (montants,
   comptes) d'une écriture déjà validée SANS toucher au statut. Le grand livre
   changeait sous une validation posée.

Après correctif : `statut` en `read_only_fields`, refus EN ENTIER de
`update`/`partial_update` sur une écriture VALIDÉE (400), garde miroir côté
modèle (`_verifier_non_validee`) pour les chemins ORM. Seule l'action `valider`
produit la transition ; l'extourne reste le seul chemin de correction.

Non couvert par AUD170 (DELETE seul) ni AUD515 (garde CI générique).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta import services
from apps.compta.models import EcritureComptable, Journal, LigneEcriture
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/compta/ecritures/'


def _ecriture(company, jour, libelle, montant, created_by=None):
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, created_by=created_by)


class Aud804EcritureValideeImmuableTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud804-co', defaults={'nom': 'AUD804 Co'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        # Rôle qui porte UNIQUEMENT la saisie (pas `compta_valider`).
        self.role_saisie = Role.objects.create(
            company=self.co, nom='AUD804 saisie',
            permissions=['compta_saisir'])
        self.saisisseur = User.objects.create_user(
            username='aud804_saisi', password='x', company=self.co,
            role=self.role_saisie)
        self.valideur = User.objects.create_user(
            username='aud804_valid', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.saisisseur)}')

    # ── 1. Le PATCH de statut ne valide plus ──────────────────────────────
    def test_patch_statut_validee_ne_valide_pas(self):
        ec = _ecriture(self.co, date(2026, 3, 2), 'Vente', '1000',
                       created_by=self.saisisseur)
        res = self.api.patch(f'{URL}{ec.id}/', {'statut': 'validee'},
                             format='json')
        ec.refresh_from_db()
        # Le champ est en lecture seule : il est IGNORÉ, jamais appliqué.
        self.assertEqual(ec.statut, EcritureComptable.Statut.BROUILLON)
        self.assertIsNone(ec.valide_par_id)
        self.assertIsNone(ec.date_validation)
        self.assertIn(res.status_code, (200, 400))

    def test_statut_est_en_lecture_seule_au_serialiseur(self):
        from apps.compta.serializers import EcritureComptableSerializer
        self.assertTrue(
            EcritureComptableSerializer().fields['statut'].read_only)

    # ── 2. Une écriture VALIDÉE ne se réécrit plus ────────────────────────
    def _ecriture_validee(self):
        ec = _ecriture(self.co, date(2026, 3, 3), 'Vente validée', '500',
                       created_by=self.saisisseur)
        services.valider_ecriture(ec, user=self.valideur)
        ec.refresh_from_db()
        self.assertEqual(ec.statut, EcritureComptable.Statut.VALIDEE)
        return ec

    def test_patch_du_libelle_sur_ecriture_validee_refuse(self):
        ec = self._ecriture_validee()
        res = self.api.patch(f'{URL}{ec.id}/', {'libelle': 'Détournée'},
                             format='json')
        self.assertEqual(res.status_code, 400)
        ec.refresh_from_db()
        self.assertEqual(ec.libelle, 'Vente validée')

    def test_reecriture_des_lignes_d_une_ecriture_validee_refuse(self):
        """Le contournement le plus grave : changer montants/comptes SANS
        toucher au statut (l'`update()` supprimait puis recréait les lignes)."""
        ec = self._ecriture_validee()
        corps = {
            'journal': ec.journal_id,
            'date_ecriture': '2026-03-03',
            'libelle': 'Vente validée',
            'lignes': [
                {'compte': services.get_compte(self.co, '5141').id,
                 'debit': '99999.00', 'credit': '0.00'},
                {'compte': services.get_compte(self.co, '7121').id,
                 'debit': '0.00', 'credit': '99999.00'},
            ],
        }
        res = self.api.put(f'{URL}{ec.id}/', corps, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            LigneEcriture.objects.filter(ecriture=ec).count(), 2)
        self.assertEqual(ec.total_debit, Decimal('500'))

    def test_garde_modele_sur_le_chemin_orm(self):
        """Même verrou hors API : un `save()` direct est refusé."""
        ec = self._ecriture_validee()
        ec.libelle = 'Réécrit par l\'ORM'
        with self.assertRaises(ValidationError) as ctx:
            ec.save()
        self.assertIn('extourne', str(ctx.exception).lower())

    # ── 3. Les chemins légitimes restent ouverts ──────────────────────────
    def test_la_transition_ne_passe_que_par_l_action_valider(self):
        ec = _ecriture(self.co, date(2026, 3, 4), 'À valider', '250',
                       created_by=self.saisisseur)
        api_valideur = APIClient()
        api_valideur.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.valideur)}')
        res = api_valideur.post(f'{URL}{ec.id}/valider/')
        self.assertEqual(res.status_code, 200)
        ec.refresh_from_db()
        self.assertEqual(ec.statut, EcritureComptable.Statut.VALIDEE)
        self.assertEqual(ec.valide_par_id, self.valideur.id)
        self.assertIsNotNone(ec.date_validation)

    def test_une_ecriture_brouillon_reste_modifiable(self):
        ec = _ecriture(self.co, date(2026, 3, 5), 'Brouillon', '100',
                       created_by=self.saisisseur)
        res = self.api.patch(f'{URL}{ec.id}/', {'libelle': 'Corrigé'},
                             format='json')
        self.assertEqual(res.status_code, 200)
        ec.refresh_from_db()
        self.assertEqual(ec.libelle, 'Corrigé')

    def test_l_extourne_reste_le_chemin_de_correction(self):
        ec = self._ecriture_validee()
        extourne = services.extourner_ecriture(ec, user=self.valideur)
        self.assertNotEqual(extourne.pk, ec.pk)
        self.assertEqual(extourne.source_type, 'extourne')
        ec.refresh_from_db()
        self.assertEqual(ec.statut, EcritureComptable.Statut.VALIDEE)
