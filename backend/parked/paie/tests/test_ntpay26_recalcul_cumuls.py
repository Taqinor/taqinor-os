"""Tests NTPAY26 — Recalcul nocturne des cumuls annuels en dérive.

Couvre : un cumul volontairement DÉSYNCHRONISÉ est corrigé au run suivant avec
une ligne d'ajustement horodatée ET motivée (chatter ``records``), un cumul
déjà COHÉRENT n'est pas touché du tout (ni montants, ni ``date_calcul``, ni
trace), le cas « aucun cumul » (rien à corriger), l'année filtrante et
l'isolation société.
"""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import CumulAnnuel, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    recalculer_cumul_annuel,
    valider_bulletin,
)
from apps.paie.tasks import (
    CHAMP_AJUSTEMENT_CUMUL,
    _ecarts_cumul,
    recalculer_cumuls_annuels_company,
)
from apps.records.models import Activity
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class RecalculCumulsTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay26')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.profil = self._profil('A1')
        valider_bulletin(generer_bulletin(self.profil, self.periode))
        self.cumul = recalculer_cumul_annuel(self.profil, 2026)

    def _profil(self, matricule, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _traces(self, cumul):
        ct = ContentType.objects.get_for_model(CumulAnnuel)
        return list(
            Activity.objects.filter(
                content_type=ct, object_id=cumul.pk,
                field=CHAMP_AJUSTEMENT_CUMUL))

    # ── Cumul cohérent : on n'y touche pas ─────────────────────────────────

    def test_cumul_coherent_n_est_pas_touche(self):
        self.assertEqual(_ecarts_cumul(self.profil, 2026)[1], {})
        avant = self.cumul.date_calcul
        corriges = recalculer_cumuls_annuels_company(self.co, annee=2026)
        self.assertEqual(corriges, [])
        self.cumul.refresh_from_db()
        self.assertEqual(self.cumul.date_calcul, avant)
        self.assertEqual(self._traces(self.cumul), [])

    # ── Cumul désynchronisé : corrigé + tracé ──────────────────────────────

    def test_cumul_desynchronise_est_corrige_et_trace(self):
        brut_reel = self.cumul.brut
        # Désynchronisation VOLONTAIRE (simule un bulletin validé après coup).
        CumulAnnuel.objects.filter(pk=self.cumul.pk).update(
            brut=Decimal('1.00'), nombre_bulletins=0)

        cumul, ecarts = _ecarts_cumul(self.profil, 2026)
        self.assertIn('brut', ecarts)
        self.assertEqual(ecarts['brut'], (Decimal('1.00'), brut_reel))

        corriges = recalculer_cumuls_annuels_company(self.co, annee=2026)
        self.assertEqual(len(corriges), 1)

        self.cumul.refresh_from_db()
        self.assertEqual(self.cumul.brut, brut_reel)
        self.assertEqual(self.cumul.nombre_bulletins, 1)

        traces = self._traces(self.cumul)
        self.assertEqual(len(traces), 1)
        trace = traces[0]
        self.assertIn('brut', trace.old_value)
        self.assertIn(str(brut_reel), trace.old_value)
        self.assertIn('2026', trace.body)
        self.assertIn('désynchronisé', trace.body)
        # Horodatée : l'entrée de chatter porte sa date de création.
        self.assertIsNotNone(trace.created_at)

    def test_apres_correction_le_run_suivant_ne_retrace_rien(self):
        CumulAnnuel.objects.filter(pk=self.cumul.pk).update(
            brut=Decimal('1.00'))
        self.assertEqual(
            len(recalculer_cumuls_annuels_company(self.co, annee=2026)), 1)
        self.assertEqual(
            recalculer_cumuls_annuels_company(self.co, annee=2026), [])
        self.assertEqual(len(self._traces(self.cumul)), 1)

    # ── Cas limites ────────────────────────────────────────────────────────

    def test_sans_cumul_rien_a_corriger(self):
        profil = self._profil('B1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        cumul, ecarts = _ecarts_cumul(profil, 2026)
        self.assertIsNone(cumul)
        self.assertEqual(ecarts, {})

    def test_annee_filtrante(self):
        CumulAnnuel.objects.filter(pk=self.cumul.pk).update(
            brut=Decimal('1.00'))
        # L'année 2025 n'a aucun cumul : le balayage n'y touche à rien.
        self.assertEqual(
            recalculer_cumuls_annuels_company(self.co, annee=2025), [])
        self.cumul.refresh_from_db()
        self.assertEqual(self.cumul.brut, Decimal('1.00'))

    def test_profil_inactif_ignore(self):
        CumulAnnuel.objects.filter(pk=self.cumul.pk).update(
            brut=Decimal('1.00'))
        self.profil.actif = False
        self.profil.save()
        self.assertEqual(
            recalculer_cumuls_annuels_company(self.co, annee=2026), [])

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay26-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil_autre = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil_autre, periode_autre))
        cumul_autre = recalculer_cumul_annuel(profil_autre, 2026)
        CumulAnnuel.objects.filter(pk=cumul_autre.pk).update(
            brut=Decimal('2.00'))

        # Le balayage de NOTRE société ne corrige jamais celui de l'autre.
        self.assertEqual(
            recalculer_cumuls_annuels_company(self.co, annee=2026), [])
        cumul_autre.refresh_from_db()
        self.assertEqual(cumul_autre.brut, Decimal('2.00'))
        self.assertEqual(self._traces(cumul_autre), [])
