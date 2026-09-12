"""Tests NTPAY22 — Wizard « Clôture de période » avec checklist de contrôle.

Couvre : les CINQ points de contrôle (avances retenues, saisies-arrêt
retenues, écarts M/M-1 sans anomalie, échéances déclaratives à jour, ordre de
virement généré), le BLOCAGE de la clôture tant qu'une anomalie n'est pas
acquittée par un motif, la clôture directe d'une période sans anomalie,
l'endpoint de checklist et l'isolation société.

``today`` est injecté : aucun test ne dépend de l'heure réelle.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    AvanceSalarie, EcheanceDeclarative, PeriodePaie, ProfilPaie, SaisieArret,
)
from apps.paie.services import (
    checklist_cloture,
    ensure_defaults,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
    verifier_cloture_autorisee,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class ChecklistClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay22')
        ensure_defaults(self.co)
        self.today = date(2026, 7, 15)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, rib='011780000000000000000001',
            affilie_cnss=True, affilie_amo=True)

    def _par_code(self, **kwargs):
        return {
            item['code']: item
            for item in checklist_cloture(self.periode, today=self.today,
                                          **kwargs)
        }

    # ── Période propre ─────────────────────────────────────────────────────

    def test_periode_sans_anomalie_est_toute_verte(self):
        profil = self._profil('A1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        generer_ordre_virement(self.periode)
        items = self._par_code()
        self.assertEqual(len(items), 5)
        for code, item in items.items():
            self.assertEqual(item['statut'], 'ok', code)
        # …et elle se clôture DIRECTEMENT, sans motif.
        self.assertEqual(
            verifier_cloture_autorisee(self.periode, today=self.today), [])

    def test_periode_vide_n_exige_pas_de_virement(self):
        """Rien à virer ⇒ « ordre de virement » reste vert (pas d'absurdité)."""
        items = self._par_code()
        self.assertEqual(items['virement_genere']['statut'], 'ok')
        self.assertIn('Aucun net à virer', items['virement_genere']['detail'])

    # ── Point 1 — avances ──────────────────────────────────────────────────

    def test_avance_non_retenue_leve_une_alerte(self):
        profil = self._profil('B1')
        AvanceSalarie.objects.create(
            company=self.co, profil=profil, libelle='Avance juin',
            montant_total=Decimal('3000'), montant_echeance=Decimal('1000'),
            date_debut=date(2026, 6, 1))
        # Aucun bulletin validé ⇒ la retenue n'a pas été jouée.
        items = self._par_code()
        self.assertEqual(items['avances_traitees']['statut'], 'alerte')
        self.assertEqual(len(items['avances_traitees']['items']), 1)

        valider_bulletin(generer_bulletin(profil, self.periode))
        self.assertEqual(
            self._par_code()['avances_traitees']['statut'], 'ok')

    # ── Point 2 — saisies-arrêt ────────────────────────────────────────────

    def test_saisie_non_retenue_leve_une_alerte(self):
        profil = self._profil('C1')
        SaisieArret.objects.create(
            company=self.co, profil=profil, creancier='Trésorerie',
            montant_total=Decimal('2000'), date_debut=date(2026, 6, 1))
        items = self._par_code()
        self.assertEqual(items['saisies_traitees']['statut'], 'alerte')

        valider_bulletin(generer_bulletin(profil, self.periode))
        self.assertEqual(
            self._par_code()['saisies_traitees']['statut'], 'ok')

    # ── Point 3 — écarts M/M-1 ─────────────────────────────────────────────

    def test_ecart_m_m1_leve_une_alerte(self):
        profil = self._profil('D1')
        precedente = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        valider_bulletin(generer_bulletin(profil, precedente))
        # Ce mois-ci : AUCUN bulletin pour ce salarié → « salarié manquant ».
        items = self._par_code()
        self.assertEqual(items['ecarts_acquittes']['statut'], 'alerte')

    # ── Point 4 — échéances déclaratives ───────────────────────────────────

    def test_echeance_en_retard_leve_une_alerte(self):
        EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS,
            date_limite=self.today - timedelta(days=3))
        items = self._par_code()
        self.assertEqual(items['echeances_a_jour']['statut'], 'alerte')

    def test_echeance_deposee_ne_leve_rien(self):
        EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS,
            date_limite=self.today - timedelta(days=3),
            statut=EcheanceDeclarative.STATUT_DEPOSEE)
        self.assertEqual(
            self._par_code()['echeances_a_jour']['statut'], 'ok')

    # ── Point 5 — ordre de virement ────────────────────────────────────────

    def test_virement_non_genere_leve_une_alerte(self):
        profil = self._profil('E1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        items = self._par_code()
        self.assertEqual(items['virement_genere']['statut'], 'alerte')
        generer_ordre_virement(self.periode)
        self.assertEqual(
            self._par_code()['virement_genere']['statut'], 'ok')

    # ── Garde de clôture ───────────────────────────────────────────────────

    def test_cloture_bloquee_sans_motif_puis_autorisee_avec(self):
        profil = self._profil('F1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        # Pas d'ordre de virement ⇒ un point en alerte.
        with self.assertRaises(ValidationError) as ctx:
            verifier_cloture_autorisee(self.periode, today=self.today)
        self.assertIn('motif_acquittement', ctx.exception.message_dict)
        message = ctx.exception.message_dict['motif_acquittement'][0]
        self.assertIn('Ordre de virement généré', message)

        alertes = verifier_cloture_autorisee(
            self.periode, motif_acquittement='Virement fait à la main',
            today=self.today)
        self.assertEqual(len(alertes), 1)

    def test_motif_vide_ne_compte_pas(self):
        profil = self._profil('G1')
        valider_bulletin(generer_bulletin(profil, self.periode))
        with self.assertRaises(ValidationError):
            verifier_cloture_autorisee(
                self.periode, motif_acquittement='   ', today=self.today)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay22-autre')
        ensure_defaults(autre)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil_autre = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        AvanceSalarie.objects.create(
            company=autre, profil=profil_autre, libelle='Avance autre',
            montant_total=Decimal('5000'), montant_echeance=Decimal('1000'),
            date_debut=date(2026, 6, 1))
        # L'avance de l'AUTRE société ne lève aucune alerte ici.
        self.assertEqual(
            self._par_code()['avances_traitees']['statut'], 'ok')


class ClotureApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay22-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay22-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='011780000000000000000001',
            affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(self.profil, self.periode))

    def _url(self, suffixe):
        return f'/api/django/paie/periodes/{self.periode.id}/{suffixe}'

    def test_endpoint_checklist(self):
        rep = self.api.get(self._url('checklist-cloture/'))
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data), 5)
        codes = {item['code'] for item in rep.data}
        self.assertEqual(codes, {
            'avances_traitees', 'saisies_traitees', 'ecarts_acquittes',
            'echeances_a_jour', 'virement_genere'})

    def test_cloture_bloquee_sans_motif(self):
        rep = self.api.post(self._url('cloturer/'), {}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('motif_acquittement', rep.data)
        self.periode.refresh_from_db()
        self.assertNotEqual(self.periode.statut, PeriodePaie.STATUT_CLOTUREE)

    def test_cloture_avec_motif_passe(self):
        rep = self.api.post(self._url('cloturer/'), {
            'motif_acquittement': 'Virement fait à la main',
        }, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.periode.refresh_from_db()
        self.assertEqual(self.periode.statut, PeriodePaie.STATUT_CLOTUREE)

    def test_cloture_directe_quand_tout_est_vert(self):
        generer_ordre_virement(self.periode)
        rep = self.api.post(self._url('cloturer/'), {}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.periode.refresh_from_db()
        self.assertEqual(self.periode.statut, PeriodePaie.STATUT_CLOTUREE)
