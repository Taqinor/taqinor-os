"""Tests NTPAY14 — Simulateur de coût d'embauche (loaded cost, sans profil).

Couvre : les 3 cas demandés (SMIG, cadre au net cible, stagiaire exonéré), la
cohérence AU CENTIME avec le moteur réel (``calculer_bulletin``), l'absence
TOTALE d'écriture en base, la composition du coût employeur (brut + charges
patronales + provisions), l'API (paramètres, 400/403) et l'isolation société.

Aucun taux n'est écrit ici : tout vient des paramètres RÉELLEMENT semés par
``ensure_defaults`` (lus en base dans les tests) ou du moteur lui-même.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import (
    BulletinPaie, ElementVariable, ParametrePaie, PeriodePaie, ProfilPaie,
    RegimeMutuelle,
)
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    parametre_en_vigueur,
    simuler_cout_embauche,
)
from apps.rh.models import DossierEmploye
from apps.roles.models import Role


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class SimulationEmbaucheTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay14')
        ensure_defaults(self.co)
        self.jour = date(2026, 6, 1)
        self.parametre = parametre_en_vigueur(self.co, self.jour)

    # ── Cas 1 — SMIG ───────────────────────────────────────────────────────

    def test_cas_smig(self):
        smig = Decimal(self.parametre.smig)
        sim = simuler_cout_embauche(self.co, brut=smig, le_jour=self.jour)
        self.assertEqual(sim['brut'], smig.quantize(Decimal('0.01')))
        # Cotisations salariales réellement prélevées au SMIG (affilié par
        # défaut), donc un net strictement inférieur au brut.
        self.assertGreater(sim['cnss_salariale'], 0)
        self.assertGreater(sim['amo_salariale'], 0)
        self.assertLess(sim['net_a_payer'], sim['brut'])
        # Le coût employeur est la SOMME EXACTE de ses composantes.
        self.assertEqual(
            sim['cout_total_employeur'],
            sim['brut'] + sim['charges_patronales']
            + sim['provisions']['total'])

    # ── Cas 2 — cadre, net cible ───────────────────────────────────────────

    def test_cas_cadre_net_cible_converge_au_centime(self):
        cible = Decimal('8000')
        sim = simuler_cout_embauche(
            self.co, net_cible=cible, le_jour=self.jour,
            affilie_cnss=True, affilie_amo=True)
        self.assertLessEqual(abs(sim['net_a_payer'] - cible), Decimal('0.01'))
        self.assertGreater(sim['brut'], cible)
        self.assertGreater(sim['ir'], 0)
        self.assertGreater(sim['cout_total_employeur'], sim['brut'])
        # Re-simuler AU BRUT trouvé redonne le même net (aucune formule
        # parallèle entre les deux sens de calcul).
        direct = simuler_cout_embauche(
            self.co, brut=sim['brut'], le_jour=self.jour)
        self.assertEqual(direct['net_a_payer'], sim['net_a_payer'])
        self.assertEqual(direct['ir'], sim['ir'])

    # ── Cas 3 — stagiaire exonéré ──────────────────────────────────────────

    def test_cas_stagiaire_exonere_paie_moins_d_ir(self):
        brut = Decimal('8000')
        normal = simuler_cout_embauche(self.co, brut=brut, le_jour=self.jour)
        # Plafond mensuel exonéré = le défaut du modèle ``ProfilPaie`` (jamais
        # un chiffre inventé ici).
        plafond = Decimal(
            ProfilPaie._meta.get_field('regime_plafond_mensuel').default)
        stagiaire = simuler_cout_embauche(
            self.co, brut=brut, le_jour=self.jour,
            regime_plafond_mensuel=plafond)
        self.assertGreater(normal['ir'], 0)
        self.assertLess(stagiaire['ir'], normal['ir'])
        self.assertGreater(stagiaire['montant_exonere_regime'], 0)
        self.assertGreater(stagiaire['net_a_payer'], normal['net_a_payer'])

    # ── Cohérence avec le moteur réel ──────────────────────────────────────

    def test_simulation_egale_le_moteur_au_centime(self):
        salaire = Decimal('12500')
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        reel = calculer_bulletin(profil, periode)
        sim = simuler_cout_embauche(self.co, brut=salaire, le_jour=self.jour)
        for champ in ('brut', 'cnss_salariale', 'amo_salariale',
                      'frais_professionnels', 'net_imposable', 'ir',
                      'net_a_payer'):
            self.assertEqual(reel[champ], sim[champ], champ)
        self.assertEqual(reel['charges_patronales'],
                         sim['charges_patronales'])

    def test_mutuelle_pesee_des_deux_cotes(self):
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Groupe', mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('1'), part_patronale=Decimal('2'))
        sans = simuler_cout_embauche(
            self.co, brut=Decimal('10000'), le_jour=self.jour)
        avec = simuler_cout_embauche(
            self.co, brut=Decimal('10000'), le_jour=self.jour,
            regime_mutuelle=regime)
        self.assertGreater(avec['mutuelle_salariale'], 0)
        self.assertGreater(avec['mutuelle_patronale'], 0)
        self.assertLess(avec['net_a_payer'], sans['net_a_payer'])
        self.assertGreater(avec['charges_patronales'],
                           sans['charges_patronales'])

    # ── Provisions ─────────────────────────────────────────────────────────

    def test_ifc_nulle_a_l_embauche_et_non_nulle_avec_anciennete(self):
        brut = Decimal('10000')
        neuf = simuler_cout_embauche(self.co, brut=brut, le_jour=self.jour)
        self.assertEqual(neuf['provisions']['ifc'], Decimal('0.00'))
        ancien = simuler_cout_embauche(
            self.co, brut=brut, le_jour=self.jour,
            anciennete_annees=Decimal('8'))
        self.assertGreater(ancien['provisions']['ifc'], 0)
        self.assertGreater(ancien['cout_total_employeur'],
                           neuf['cout_total_employeur'])

    # ── Zéro persistance ───────────────────────────────────────────────────

    def test_aucune_ecriture_en_base(self):
        avant = (ProfilPaie.objects.count(), BulletinPaie.objects.count(),
                 ElementVariable.objects.count(), ParametrePaie.objects.count())
        simuler_cout_embauche(
            self.co, net_cible=Decimal('9000'), le_jour=self.jour)
        simuler_cout_embauche(
            self.co, brut=Decimal('9000'), le_jour=self.jour)
        apres = (ProfilPaie.objects.count(), BulletinPaie.objects.count(),
                 ElementVariable.objects.count(), ParametrePaie.objects.count())
        self.assertEqual(avant, apres)

    def test_brut_et_net_cible_sont_exclusifs(self):
        with self.assertRaises(ValueError):
            simuler_cout_embauche(self.co, le_jour=self.jour)
        with self.assertRaises(ValueError):
            simuler_cout_embauche(
                self.co, brut=Decimal('1'), net_cible=Decimal('1'),
                le_jour=self.jour)

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe_bareme_propre(self):
        autre = make_company('ntpay14-autre')  # AUCUN ensure_defaults
        sim = simuler_cout_embauche(
            autre, brut=Decimal('10000'), le_jour=self.jour)
        # Sans jeu en vigueur : rien n'est inventé — 0 partout + avertissement.
        self.assertEqual(sim['cnss_salariale'], Decimal('0.00'))
        self.assertEqual(sim['ir'], Decimal('0.00'))
        self.assertEqual(sim['net_a_payer'], Decimal('10000.00'))
        self.assertTrue(sim['avertissements'])


class SimulationEmbaucheApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay14-api')
        ensure_defaults(self.co)
        self.api = self._client(
            ['paie_voir', 'paie_gerer', 'salaires_voir'], 'ntpay14-paye')
        self.url = '/api/django/paie/profils/simulation-embauche/'

    def _client(self, permissions, username):
        role = Role.objects.create(
            company=self.co, nom=f'Role {username}', permissions=permissions)
        user = User.objects.create_user(
            username=username, password='x', company=self.co, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_sans_salaires_voir_est_403(self):
        """AUD716 — le rôle Responsable livré n'a PAS ``salaires_voir``."""
        api = self._client(['paie_voir', 'paie_gerer'], 'ntpay14-sans')
        rep = api.get(f'{self.url}?brut=10000')
        self.assertEqual(rep.status_code, 403)

    def test_endpoint_net_cible(self):
        rep = self.api.get(f'{self.url}?net_cible=8000&date=2026-06-01')
        self.assertEqual(rep.status_code, 200)
        self.assertLessEqual(
            abs(Decimal(str(rep.data['net_a_payer'])) - Decimal('8000')),
            Decimal('0.01'))
        self.assertGreater(
            Decimal(str(rep.data['cout_total_employeur'])),
            Decimal(str(rep.data['brut'])))
        self.assertTrue(rep.data['lignes'])
        self.assertEqual(rep.data['devise'], 'MAD')

    def test_endpoint_sans_parametre_est_400(self):
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 400)

    def test_endpoint_pays_inconnu_est_404(self):
        rep = self.api.get(f'{self.url}?brut=10000&pays=999999')
        self.assertEqual(rep.status_code, 404)
