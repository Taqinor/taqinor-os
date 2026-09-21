"""Tests NTPAY21 — Wizard « Publication de barème » guidé.

Couvre le PARCOURS COMPLET : aperçu d'impact (NTPAY17) + périodes déjà figées
(NTPAY1) → jeton → publication avec la case fondateur → option rappel
rétroactif. Et les refus : publier sans être passé par l'aperçu (400), sans
cocher la validation (400), avec un jeton d'un AUTRE barème (400), rappel
demandé sans période cible (400). Plus l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    BaremeIR, BulletinPaie, PeriodePaie, ProfilPaie, TrancheIR,
)
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class WizardPublicationBaremeTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay21')
        ensure_defaults(self.co)
        self.ancien = BaremeIR.objects.get(company=self.co)
        self.user = User.objects.create_user(
            username='ntpay21-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.profil = self._profil('A1', Decimal('14000'))
        # Une période VALIDÉE de mars, qu'un barème daté de février périme.
        self.periode_passee = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=3,
            statut=PeriodePaie.STATUT_VALIDEE)
        valider_bulletin(generer_bulletin(self.profil, self.periode_passee))
        self.periode_courante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

        # Barème RÉTROACTIF (effet février) — jeu de test, aucun taux officiel
        # n'est affirmé : seul l'ÉCART qu'il produit est observé.
        self.nouveau = BaremeIR.objects.create(
            company=self.co, libelle='Barème de test rétroactif',
            date_effet=date(2026, 2, 1))
        TrancheIR.objects.create(
            company=self.co, bareme=self.nouveau, borne_min=Decimal('0'),
            borne_max=None, taux=Decimal('38'),
            somme_a_deduire=Decimal('0'), ordre=1)

    def _profil(self, matricule, salaire):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _url(self, bareme):
        return f'/api/django/paie/baremes/{bareme.id}/wizard-publication/'

    def _apercu(self, bareme=None):
        rep = self.api.post(
            self._url(bareme or self.nouveau), {'etape': 'apercu'},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        return rep.data

    # ── Étape 1 — aperçu ───────────────────────────────────────────────────

    def test_apercu_montre_impact_et_periodes_figees(self):
        data = self._apercu()
        self.assertEqual(data['etape'], 'apercu')
        self.assertTrue(data['jeton_apercu'])
        self.assertIsNotNone(data['impact'])
        self.assertGreater(data['impact']['nombre_profils'], 0)
        self.assertGreater(
            Decimal(str(data['impact']['totaux']['ecart_ir'])), 0)
        ids = [p['id'] for p in data['periodes_impactees']]
        self.assertIn(self.periode_passee.id, ids)
        # L'aperçu ne publie RIEN.
        self.nouveau.refresh_from_db()
        self.assertFalse(self.nouveau.valide_par_fondateur)

    def test_etape_inconnue_est_400(self):
        rep = self.api.post(
            self._url(self.nouveau), {'etape': 'lune'}, format='json')
        self.assertEqual(rep.status_code, 400)

    # ── Refus de publication ───────────────────────────────────────────────

    def test_publier_sans_apercu_est_bloque(self):
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'valide_par_fondateur': True,
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('jeton_apercu', rep.data)
        self.nouveau.refresh_from_db()
        self.assertFalse(self.nouveau.valide_par_fondateur)

    def test_publier_sans_validation_fondateur_est_bloque(self):
        jeton = self._apercu()['jeton_apercu']
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'jeton_apercu': jeton,
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('valide_par_fondateur', rep.data)
        self.nouveau.refresh_from_db()
        self.assertFalse(self.nouveau.valide_par_fondateur)

    def test_jeton_d_un_autre_bareme_est_refuse(self):
        jeton_autre = self._apercu(self.ancien)['jeton_apercu']
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'jeton_apercu': jeton_autre,
            'valide_par_fondateur': True,
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('jeton_apercu', rep.data)

    def test_rappel_sans_periode_cible_est_400(self):
        jeton = self._apercu()['jeton_apercu']
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'jeton_apercu': jeton,
            'valide_par_fondateur': True, 'declencher_rappel': True,
        }, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('periode_cible', rep.data)

    # ── Parcours complet ───────────────────────────────────────────────────

    def test_parcours_complet_publie_le_bareme(self):
        jeton = self._apercu()['jeton_apercu']
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'jeton_apercu': jeton,
            'valide_par_fondateur': True,
        }, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(rep.data['etape'], 'publication')
        self.assertTrue(rep.data['bareme']['valide_par_fondateur'])
        self.assertIsNone(rep.data['rappel'])
        self.nouveau.refresh_from_db()
        self.assertTrue(self.nouveau.valide_par_fondateur)

    def test_parcours_complet_avec_rappel_retroactif(self):
        jeton = self._apercu()['jeton_apercu']
        avant = BulletinPaie.objects.filter(
            company=self.co, type_bulletin=BulletinPaie.TYPE_RAPPEL).count()
        rep = self.api.post(self._url(self.nouveau), {
            'etape': 'publication', 'jeton_apercu': jeton,
            'valide_par_fondateur': True, 'declencher_rappel': True,
            'periode_cible': self.periode_courante.id,
            'motif': 'Barème IR rétroactif',
        }, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertIsNotNone(rep.data['rappel'])
        self.assertEqual(
            rep.data['rappel']['periode_cible'], self.periode_courante.id)
        self.assertGreaterEqual(rep.data['rappel']['nombre_salaries'], 1)
        apres = BulletinPaie.objects.filter(
            company=self.co, type_bulletin=BulletinPaie.TYPE_RAPPEL).count()
        self.assertGreater(apres, avant)
        # Le bulletin d'origine reste FIGÉ (NTPAY1).
        origine = BulletinPaie.objects.get(
            company=self.co, periode=self.periode_passee, profil=self.profil)
        self.assertEqual(origine.statut, BulletinPaie.STATUT_VALIDE)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_bareme_d_une_autre_societe_invisible(self):
        autre = make_company('ntpay21-autre')
        ensure_defaults(autre)
        bareme_autre = BaremeIR.objects.get(company=autre)
        rep = self.api.post(
            self._url(bareme_autre), {'etape': 'apercu'}, format='json')
        self.assertEqual(rep.status_code, 404)
