"""AUD185 — verrous d'admin sur la comptabilité (F4, F8, F9, F10, F11).

Quatre défauts prouvés par l'audit L3, tous sur `apps/compta/admin.py` :

* **F4** — `LigneEcritureInline`/`EcritureComptableAdmin` laissaient
  DÉSÉQUILIBRER une écriture validée : `EcritureComptable.clean()`
  (apps/compta/models.py:304-323) s'exécute sur le formulaire PARENT, AVANT que
  le formset enfant ne sauvegarde — il relit donc les lignes telles qu'elles
  étaient en base — et `LigneEcriture.clean()` (:420-433) ne contrôle qu'UNE
  ligne. Le chemin le plus court n'était même pas la suppression, mais la
  simple MODIFICATION d'un montant (1000 → 900).
* **F8** — `statut`, `valide_par` et `date_validation` étaient en écriture
  libre, contournant la séparation des tâches COMPTA40 que seul
  `services.valider_ecriture` (apps/compta/services.py:364-389) applique.
* **F9** — `verrouillee`, `verrouillee_par` et `date_verrouillage` d'une
  `PeriodeComptable` étaient en écriture libre, contournant le garde
  « exercice clôturé » de `rouvrir_periode`.
* **F10** — aucun `get_queryset` scopé société nulle part, et `rib`/`iban`
  exposés en `search_fields` de `CompteTresorerieAdmin`.
* **F11** — `LigneEcritureInline.fields` omettait le FK NOT NULL `company`
  (apps/compta/models.py:357-362) : ajouter une ligne levait une
  `IntegrityError` brute.
"""
import json
from datetime import date, datetime
from decimal import Decimal

from django.contrib import admin as django_admin
from django.core.exceptions import PermissionDenied
from django.test import Client as HttpClient
from django.test import RequestFactory, TestCase
from django.urls import reverse

from authentication.models import Company

from apps.compta import services
from apps.compta.admin import SUPPRESSION_ECRITURE_VALIDEE_INTERDITE
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, Journal, LigneEcriture,
    PeriodeComptable,
)
from testkit.factories import UserFactory


def payload_depuis_form(model_admin, request, obj):
    """POST reconstruit depuis le formulaire d'admin lui-même (cf. AUD185
    côté ventes) : aucun champ obligatoire oublié, et un champ passé en
    `readonly` disparaît AUTOMATIQUEMENT — comme dans le navigateur."""
    form_class = model_admin.get_form(request, obj, change=obj is not None)
    form = form_class(instance=obj)
    data = {}
    for nom, champ in form.fields.items():
        brut = form.initial.get(nom, champ.initial)
        if brut is None or brut == '':
            data[nom] = ''
        elif isinstance(brut, bool):
            if brut:
                data[nom] = 'on'
        elif isinstance(brut, (dict, list, tuple)):
            data[nom] = json.dumps(brut)
        elif isinstance(brut, datetime):
            data[nom] = brut.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(brut, date):
            data[nom] = brut.strftime('%Y-%m-%d')
        elif hasattr(brut, 'pk'):
            data[nom] = str(brut.pk)
        else:
            data[nom] = str(brut)
    return data


class EcritureAdminVerrousTests(TestCase):
    def setUp(self):
        super().setUp()
        self.societe_a, _ = Company.objects.get_or_create(
            slug='aud185-compta-a', defaults={'nom': 'AUD185 Compta A'})
        self.societe_b, _ = Company.objects.get_or_create(
            slug='aud185-compta-b', defaults={'nom': 'AUD185 Compta B'})
        for societe in (self.societe_a, self.societe_b):
            services.seed_plan_comptable(societe)
            services.seed_journaux(societe)
        self.journal = Journal.objects.get(company=self.societe_a, code='VTE')
        self.clients = services.get_compte(self.societe_a, '3421')
        self.ventes = services.get_compte(self.societe_a, '7121')

        self.ecriture = services.creer_ecriture(
            self.societe_a, self.journal, date(2026, 1, 10),
            'AUD185 écriture témoin',
            [
                {'compte': self.clients, 'debit': Decimal('1000'),
                 'credit': Decimal('0')},
                {'compte': self.ventes, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ])
        self.ligne_debit = self.ecriture.lignes.order_by('id').first()
        self.ligne_credit = self.ecriture.lignes.order_by('id').last()

        self.saisisseur = UserFactory(
            company=self.societe_a, username='aud185-saisie')
        self.superuser = UserFactory(
            company=self.societe_a, username='aud185-root-compta',
            is_staff=True, is_superuser=True)
        self.http = HttpClient()
        self.http.force_login(self.superuser)
        self.ecr_admin = django_admin.site._registry[EcritureComptable]
        self.periode_admin = django_admin.site._registry[PeriodeComptable]
        self.tresorerie_admin = django_admin.site._registry[CompteTresorerie]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request

    def _prefix_lignes(self):
        inline = self.ecr_admin.inlines[0](
            EcritureComptable, django_admin.site)
        formset_class = inline.get_formset(self._request(), self.ecriture)
        return formset_class.get_default_prefix()

    def _post_ecriture(self, lignes, **surcharges):
        """POST du formulaire de changement + son formset de lignes.

        ``lignes`` = liste de dicts (``id``/``compte``/``debit``/``credit``…),
        ``id`` vide pour une NOUVELLE ligne.
        """
        prefix = self._prefix_lignes()
        data = payload_depuis_form(
            self.ecr_admin, self._request(), self.ecriture)
        initiales = sum(1 for lig in lignes if lig.get('id'))
        data.update({
            f'{prefix}-TOTAL_FORMS': str(len(lignes)),
            f'{prefix}-INITIAL_FORMS': str(initiales),
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
        })
        for index, ligne in enumerate(lignes):
            data[f'{prefix}-{index}-id'] = str(ligne.get('id') or '')
            data[f'{prefix}-{index}-ecriture'] = str(self.ecriture.pk)
            data[f'{prefix}-{index}-compte'] = str(ligne['compte'])
            data[f'{prefix}-{index}-libelle'] = ligne.get('libelle', '')
            data[f'{prefix}-{index}-debit'] = str(ligne.get('debit', '0'))
            data[f'{prefix}-{index}-credit'] = str(ligne.get('credit', '0'))
            data[f'{prefix}-{index}-lettrage'] = ligne.get('lettrage', '')
        data.update(surcharges)
        url = reverse('admin:compta_ecriturecomptable_change',
                      args=[self.ecriture.pk])
        return self.http.post(url, data)

    def _lignes_equilibrees(self):
        return [
            {'id': self.ligne_debit.pk, 'compte': self.clients.pk,
             'debit': '1000', 'credit': '0'},
            {'id': self.ligne_credit.pk, 'compte': self.ventes.pk,
             'debit': '0', 'credit': '1000'},
        ]

    # ── (2) F4 — déséquilibrer une écriture validée ────────────────────────
    def test_desequilibrer_une_ecriture_validee_est_refuse(self):
        services.valider_ecriture(self.ecriture, user=self.superuser)
        self.ecriture.refresh_from_db()
        self.assertEqual(self.ecriture.statut,
                         EcritureComptable.Statut.VALIDEE)

        lignes = self._lignes_equilibrees()
        lignes[0]['debit'] = '900'          # 1000 → 900 : le chemin court
        reponse = self._post_ecriture(lignes)

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Écriture déséquilibrée')
        self.ligne_debit.refresh_from_db()
        self.assertEqual(self.ligne_debit.debit, Decimal('1000.00'))
        self.ecriture.refresh_from_db()
        self.assertTrue(self.ecriture.est_equilibree)

    # ── (3) F8 — statut / valide_par / date_validation en lecture seule ────
    def test_statut_et_validation_sont_en_lecture_seule(self):
        readonly = self.ecr_admin.get_readonly_fields(
            self._request(), self.ecriture)
        for champ in ('statut', 'valide_par', 'date_validation'):
            self.assertIn(champ, readonly, f'{champ} encore modifiable')

        reponse = self._post_ecriture(
            self._lignes_equilibrees(),
            statut=EcritureComptable.Statut.VALIDEE,
            valide_par=str(self.saisisseur.pk))
        self.assertEqual(reponse.status_code, 302)
        self.ecriture.refresh_from_db()
        self.assertEqual(self.ecriture.statut,
                         EcritureComptable.Statut.BROUILLON)
        self.assertIsNone(self.ecriture.valide_par_id)
        self.assertIsNone(self.ecriture.date_validation)

    # ── (6) F11 — ajouter une ligne par l'inline ───────────────────────────
    def test_ajout_de_lignes_par_l_inline_ne_leve_plus_d_integrityerror(self):
        lignes = self._lignes_equilibrees() + [
            {'id': '', 'compte': self.clients.pk,
             'debit': '50', 'credit': '0'},
            {'id': '', 'compte': self.ventes.pk,
             'debit': '0', 'credit': '50'},
        ]
        reponse = self._post_ecriture(lignes)
        self.assertEqual(reponse.status_code, 302)

        toutes = LigneEcriture.objects.filter(ecriture=self.ecriture)
        self.assertEqual(toutes.count(), 4)
        # `company` pré-rempli depuis l'écriture parente — jamais NULL.
        self.assertEqual(
            toutes.filter(company=self.societe_a).count(), 4)

    # ── (4) suppression d'une pièce validée ────────────────────────────────
    def test_suppression_ecriture_validee_refusee(self):
        services.valider_ecriture(self.ecriture, user=self.superuser)
        self.ecriture.refresh_from_db()

        url = reverse('admin:compta_ecriturecomptable_delete',
                      args=[self.ecriture.pk])
        self.assertEqual(self.http.get(url).status_code, 403)
        self.assertEqual(self.http.post(url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(
            EcritureComptable.objects.filter(pk=self.ecriture.pk).exists())

        self.assertFalse(self.ecr_admin.has_delete_permission(
            self._request(), self.ecriture))
        with self.assertRaises(PermissionDenied):
            self.ecr_admin.delete_model(self._request(), self.ecriture)
        with self.assertRaises(PermissionDenied):
            self.ecr_admin.delete_queryset(
                self._request(),
                EcritureComptable.objects.filter(pk=self.ecriture.pk))
        self.assertIn('extourne', SUPPRESSION_ECRITURE_VALIDEE_INTERDITE)

    def test_suppression_ecriture_brouillon_reste_possible(self):
        self.assertTrue(self.ecr_admin.has_delete_permission(
            self._request(), self.ecriture))

    # ── (3) F9 — verrous de période en lecture seule ───────────────────────
    def test_verrou_de_periode_en_lecture_seule(self):
        periode = PeriodeComptable.objects.create(
            company=self.societe_a, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), libelle='AUD185 janvier')
        readonly = self.periode_admin.get_readonly_fields(
            self._request(), periode)
        for champ in ('verrouillee', 'date_verrouillage', 'verrouillee_par'):
            self.assertIn(champ, readonly, f'{champ} encore modifiable')

        data = payload_depuis_form(
            self.periode_admin, self._request(), periode)
        data['verrouillee'] = 'on'
        reponse = self.http.post(
            reverse('admin:compta_periodecomptable_change',
                    args=[periode.pk]), data)
        self.assertEqual(reponse.status_code, 302)
        periode.refresh_from_db()
        self.assertFalse(periode.verrouillee)

    # ── (5) F10 — scope société + coordonnées bancaires hors recherche ─────
    def test_liste_des_ecritures_scopee_par_societe(self):
        journal_b = Journal.objects.get(company=self.societe_b, code='VTE')
        etrangere = services.creer_ecriture(
            self.societe_b, journal_b, date(2026, 1, 10),
            'AUD185 écriture société B',
            [
                {'compte': services.get_compte(self.societe_b, '3421'),
                 'debit': Decimal('10'), 'credit': Decimal('0')},
                {'compte': services.get_compte(self.societe_b, '7121'),
                 'debit': Decimal('0'), 'credit': Decimal('10')},
            ])
        queryset = self.ecr_admin.get_queryset(self._request())
        self.assertIn(self.ecriture, queryset)
        self.assertNotIn(etrangere, queryset)

        reponse = self.http.get(
            reverse('admin:compta_ecriturecomptable_changelist'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'AUD185 écriture témoin')
        self.assertNotContains(reponse, 'AUD185 écriture société B')

    def test_liste_des_comptes_de_tresorerie_scopee_par_societe(self):
        mien = CompteTresorerie.objects.create(
            company=self.societe_a, libelle='AUD185 banque A',
            rib='011780000012345678901234',
            compte_comptable=services.get_compte(self.societe_a, '5141'))
        autre = CompteTresorerie.objects.create(
            company=self.societe_b, libelle='AUD185 banque B',
            rib='011780000098765432109876',
            compte_comptable=services.get_compte(self.societe_b, '5141'))
        queryset = self.tresorerie_admin.get_queryset(self._request())
        self.assertIn(mien, queryset)
        self.assertNotIn(autre, queryset)

    def test_rib_et_iban_hors_de_la_recherche_admin(self):
        champs = tuple(self.tresorerie_admin.search_fields)
        self.assertNotIn('rib', champs)
        self.assertNotIn('iban', champs)
