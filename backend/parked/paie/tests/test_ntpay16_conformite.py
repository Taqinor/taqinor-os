"""Tests NTPAY16 — Cockpit de conformité paie.

Couvre SIGNAL PAR SIGNAL : échéance BDS dépassée sans dépôt, preuve de dépôt
manquante (un dépôt REJETÉ ne prouve rien), barème non validé par le
fondateur, période ouverte en retard de clôture (ZPAI12), avertissements
pré-run (ZPAI2) — puis la société à jour qui affiche « conforme », l'endpoint
et l'isolation société.

``today`` est injecté partout : aucun test ne dépend de l'heure réelle.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    BaremeIR, DepotDeclaratif, EcheanceDeclarative, ParametrePaie,
    PeriodePaie, ProfilPaie,
)
from apps.paie.selectors import cockpit_conformite_paie
from apps.paie.services import (
    enregistrer_depot_declaratif,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class ConformitePaieTests(TestCase):
    """Chaque test part d'une société SANS aucun signal, puis en allume UN."""

    def setUp(self):
        self.co = make_company('ntpay16')
        # La société de référence est « à jour » : jeu légal VALIDÉ par le
        # fondateur, aucune période, aucune échéance.
        ensure_defaults(self.co)
        ParametrePaie.objects.filter(company=self.co).update(
            valide_par_fondateur=True)
        BaremeIR.objects.filter(company=self.co).update(
            valide_par_fondateur=True)
        self.today = date(2026, 7, 15)

    def _cockpit(self):
        return cockpit_conformite_paie(self.co, today=self.today)

    def _periode(self, annee=2026, mois=6, statut=PeriodePaie.STATUT_CLOTUREE):
        return PeriodePaie.objects.create(
            company=self.co, annee=annee, mois=mois, statut=statut)

    def _echeance(self, periode, date_limite,
                  statut=EcheanceDeclarative.STATUT_GENEREE):
        return EcheanceDeclarative.objects.create(
            company=self.co, periode=periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS,
            date_limite=date_limite, statut=statut)

    # ── Référence : société à jour ─────────────────────────────────────────

    def test_societe_a_jour_est_conforme(self):
        etat = self._cockpit()
        self.assertTrue(etat['conforme'])
        self.assertEqual(etat['echeances_en_retard'], [])
        self.assertEqual(etat['depots_manquants'], [])
        self.assertEqual(etat['baremes_non_valides'], [])
        self.assertEqual(etat['periodes_en_retard'], [])
        self.assertEqual(etat['alertes_pre_run'], [])

    # ── Signal 1 — échéance BDS dépassée ───────────────────────────────────

    def test_echeance_bds_depassee_sans_depot(self):
        periode = self._periode()
        self._echeance(periode, self.today - timedelta(days=5))
        etat = self._cockpit()
        self.assertFalse(etat['conforme'])
        self.assertEqual(len(etat['echeances_en_retard']), 1)
        ligne = etat['echeances_en_retard'][0]
        self.assertEqual(ligne['type'], EcheanceDeclarative.TYPE_BDS)
        self.assertEqual(ligne['jours'], -5)
        self.assertEqual(ligne['annee'], 2026)
        self.assertEqual(ligne['mois'], 6)

    def test_echeance_deposee_n_est_pas_en_retard(self):
        periode = self._periode()
        self._echeance(periode, self.today - timedelta(days=5),
                       statut=EcheanceDeclarative.STATUT_DEPOSEE)
        etat = self._cockpit()
        self.assertEqual(etat['echeances_en_retard'], [])
        self.assertTrue(etat['conforme'])

    def test_echeance_a_venir_dans_la_fenetre(self):
        periode = self._periode()
        self._echeance(periode, self.today + timedelta(days=10))
        etat = self._cockpit()
        self.assertEqual(len(etat['echeances_a_venir']), 1)
        self.assertEqual(etat['echeances_a_venir'][0]['jours'], 10)
        # Une échéance à venir ne rend PAS la société non conforme.
        self.assertTrue(etat['conforme'])

    def test_echeance_hors_fenetre_n_est_pas_listee(self):
        periode = self._periode()
        self._echeance(periode, self.today + timedelta(days=90))
        self.assertEqual(self._cockpit()['echeances_a_venir'], [])

    # ── Signal 2 — preuve de dépôt manquante ───────────────────────────────

    def test_preuve_de_depot_manquante_puis_fournie(self):
        periode = self._periode()
        echeance = self._echeance(periode, self.today - timedelta(days=2))
        self.assertEqual(len(self._cockpit()['depots_manquants']), 1)

        enregistrer_depot_declaratif(
            echeance, date_depot=self.today - timedelta(days=1),
            reference_depot='DAM-2026-06')
        etat = self._cockpit()
        self.assertEqual(etat['depots_manquants'], [])
        self.assertEqual(etat['echeances_en_retard'], [])

    def test_depot_rejete_ne_prouve_rien(self):
        periode = self._periode()
        echeance = self._echeance(periode, self.today - timedelta(days=2))
        enregistrer_depot_declaratif(
            echeance, date_depot=self.today - timedelta(days=1),
            statut=DepotDeclaratif.STATUT_REJETE,
            motif_rejet='Fichier illisible')
        etat = self._cockpit()
        self.assertEqual(len(etat['depots_manquants']), 1)
        self.assertEqual(len(etat['echeances_en_retard']), 1)

    # ── Signal 3 — barème non validé ───────────────────────────────────────

    def test_bareme_non_valide_remonte(self):
        BaremeIR.objects.filter(company=self.co).update(
            valide_par_fondateur=False)
        etat = self._cockpit()
        self.assertFalse(etat['conforme'])
        objets = {b['objet'] for b in etat['baremes_non_valides']}
        self.assertIn('bareme_ir', objets)

    def test_parametres_non_valides_remontent_aussi(self):
        ParametrePaie.objects.filter(company=self.co).update(
            valide_par_fondateur=False)
        objets = {b['objet'] for b in self._cockpit()['baremes_non_valides']}
        self.assertIn('parametre_paie', objets)

    # ── Signal 4 — période ouverte en retard (ZPAI12) ──────────────────────

    def test_periode_ouverte_en_retard(self):
        # Le mois M+1 d'une période de 2026-01 est largement entamé au
        # 15/07/2026 → elle est en retard. ``periodes_cloture_en_retard``
        # lit la date système : on ne fige donc QUE la sémantique (le mois
        # est loin dans le passé, quelle que soit l'heure du test).
        self._periode(annee=2020, mois=1,
                      statut=PeriodePaie.STATUT_BROUILLON)
        etat = self._cockpit()
        self.assertFalse(etat['conforme'])
        self.assertEqual(len(etat['periodes_en_retard']), 1)
        self.assertEqual(etat['periodes_en_retard'][0]['annee'], 2020)

    def test_periode_cloturee_n_est_jamais_en_retard(self):
        self._periode(annee=2020, mois=1,
                      statut=PeriodePaie.STATUT_CLOTUREE)
        self.assertEqual(self._cockpit()['periodes_en_retard'], [])

    # ── Signal 5 — avertissements pré-run (ZPAI2) ──────────────────────────

    def test_alertes_pre_run_sur_periode_ouverte(self):
        periode = self._periode(annee=2026, mois=7,
                                statut=PeriodePaie.STATUT_BROUILLON)
        # Un employé ACTIF sans profil de paie → avertissement BLOQUANT.
        DossierEmploye.objects.create(
            company=self.co, matricule='X1', nom='Sans', prenom='Profil')
        etat = self._cockpit()
        self.assertFalse(etat['conforme'])
        self.assertEqual(len(etat['alertes_pre_run']), 1)
        self.assertEqual(etat['alertes_pre_run'][0]['periode_id'], periode.id)
        self.assertGreaterEqual(etat['alertes_pre_run'][0]['bloquants'], 1)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay16-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6,
            statut=PeriodePaie.STATUT_CLOTUREE)
        EcheanceDeclarative.objects.create(
            company=autre, periode=periode_autre,
            type_echeance=EcheanceDeclarative.TYPE_BDS,
            date_limite=self.today - timedelta(days=30))
        # Rien de l'autre société ne fuit dans le cockpit de la nôtre.
        etat = self._cockpit()
        self.assertTrue(etat['conforme'])
        # …et l'autre société voit bien SES signaux (dont son jeu non validé).
        etat_autre = cockpit_conformite_paie(autre, today=self.today)
        self.assertFalse(etat_autre['conforme'])
        self.assertEqual(len(etat_autre['echeances_en_retard']), 1)


class ConformitePaieApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay16-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay16-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_endpoint_conformite(self):
        rep = self.api.get('/api/django/paie/periodes/conformite/')
        self.assertEqual(rep.status_code, 200)
        for cle in ('conforme', 'echeances_en_retard', 'echeances_a_venir',
                    'depots_manquants', 'baremes_non_valides',
                    'periodes_en_retard', 'alertes_pre_run'):
            self.assertIn(cle, rep.data)
        # ``ensure_defaults`` sème un jeu NON validé : la société ne peut pas
        # être conforme tant que le fondateur ne l'a pas confirmé.
        self.assertFalse(rep.data['conforme'])
        self.assertTrue(rep.data['baremes_non_valides'])

    def test_endpoint_ne_montre_pas_les_bulletins(self):
        """Le cockpit est un état de CONFORMITÉ, jamais un canal de salaires."""
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='B1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12345.67'), affilie_cnss=True,
            affilie_amo=True, numero_cnss='123456789')
        valider_bulletin(generer_bulletin(profil, periode))
        rep = self.api.get('/api/django/paie/periodes/conformite/')
        self.assertNotIn('12345.67', str(rep.data))
