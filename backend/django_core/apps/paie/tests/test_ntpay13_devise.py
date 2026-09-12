"""Tests NTPAY13 — Multi-devise du bulletin & de l'ordre de virement.

Couvre : la NON-RÉGRESSION marocaine (période, bulletin et ordre de virement
restent en MAD au centime près), la dérivation de la devise depuis le pays du
profil, son impression sur le PDF/HTML du bulletin, sa propagation à l'ordre
de virement, et le REFUS explicite (en français) d'un ordre de virement à deux
devises.

NOTE — les packs pays FR/SN/CI sont GATÉS fondateur (NTPAY9/10/11 : aucun
barème officiel fourni, zéro chiffre inventé). Ces tests n'exercent donc QUE
la plomberie DEVISE : le pays « FR » de test pointe explicitement sa clé de
moteur sur les règles marocaines (``moteur='MA'``) et n'a AUCUN barème propre
— aucun taux français n'est inventé nulle part.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company
from apps.paie.builders import bulletin_context, render_bulletin_html
from apps.paie.models import (
    OrdreVirement, PaysPaie, PeriodePaie, ProfilPaie,
)
from apps.paie.services import (
    devise_du_profil,
    devise_virement_periode,
    ensure_defaults,
    ensure_pays_paie_standard,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class DeviseBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay13')
        ensure_defaults(self.co)
        ensure_pays_paie_standard(self.co)
        self.pays_ma = PaysPaie.objects.get(
            company=self.co, code_iso=PaysPaie.CODE_MA)
        # Pays de TEST : devise EUR, règles de calcul MAROCAINES (le pack FR
        # est gaté fondateur — on n'invente aucun barème français ici).
        self.pays_eur = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_FR, libelle='France',
            devise='EUR', moteur='MA')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, pays=None, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier, pays=pays,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, rib='011780000000000000000001',
            affilie_cnss=True, affilie_amo=True)

    # ── Non-régression marocaine ───────────────────────────────────────────

    def test_periode_et_bulletin_sont_en_mad_par_defaut(self):
        self.assertEqual(self.periode.devise, 'MAD')
        bulletin = generer_bulletin(self._profil('A1'), self.periode)
        self.assertEqual(bulletin.devise, 'MAD')

    def test_profil_pays_ma_reste_en_mad_au_centime_pres(self):
        sans_pays = generer_bulletin(self._profil('B1'), self.periode)
        avec_ma = generer_bulletin(
            self._profil('B2', self.pays_ma), self.periode)
        self.assertEqual(sans_pays.devise, 'MAD')
        self.assertEqual(avec_ma.devise, 'MAD')
        # Aucun centime ne bouge entre les deux (la devise est un libellé,
        # jamais une conversion).
        self.assertEqual(sans_pays.net_a_payer, avec_ma.net_a_payer)
        self.assertEqual(sans_pays.ir, avec_ma.ir)

    # ── Dérivation depuis le pays ──────────────────────────────────────────

    def test_devise_du_profil_derive_du_pays_puis_de_la_periode(self):
        profil_eur = self._profil('C1', self.pays_eur)
        self.assertEqual(devise_du_profil(profil_eur), 'EUR')
        profil_nu = self._profil('C2')
        self.assertEqual(devise_du_profil(profil_nu), 'MAD')
        # Sans pays, la période prime sur le défaut.
        periode_eur = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7, devise='EUR')
        self.assertEqual(
            devise_du_profil(profil_nu, periode=periode_eur), 'EUR')

    def test_bulletin_d_un_profil_etranger_est_dans_sa_devise(self):
        bulletin = generer_bulletin(
            self._profil('D1', self.pays_eur), self.periode)
        self.assertEqual(bulletin.devise, 'EUR')

    # ── Rendu PDF/HTML ─────────────────────────────────────────────────────

    def test_le_bulletin_imprime_sa_devise(self):
        bulletin = generer_bulletin(
            self._profil('E1', self.pays_eur), self.periode)
        contexte = bulletin_context(bulletin)
        self.assertEqual(contexte['devise'], 'EUR')
        html = render_bulletin_html(bulletin)
        self.assertIn('Net à payer :', html)
        self.assertIn('EUR', html)
        self.assertNotIn('MAD', html)

    def test_le_bulletin_marocain_imprime_toujours_mad(self):
        bulletin = generer_bulletin(self._profil('E2'), self.periode)
        html = render_bulletin_html(bulletin)
        self.assertIn('MAD', html)
        self.assertNotIn('EUR', html)

    # ── Ordre de virement ──────────────────────────────────────────────────

    def test_ordre_de_virement_marocain_reste_en_mad(self):
        valider_bulletin(generer_bulletin(self._profil('F1'), self.periode))
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.devise, 'MAD')
        self.assertEqual(ordre.nombre_lignes, 1)

    def test_ordre_de_virement_herite_de_la_devise_des_bulletins(self):
        valider_bulletin(generer_bulletin(
            self._profil('G1', self.pays_eur), self.periode))
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.devise, 'EUR')
        self.assertEqual(
            OrdreVirement.objects.get(pk=ordre.pk).devise, 'EUR')

    def test_deux_devises_dans_un_meme_run_sont_refusees_en_francais(self):
        valider_bulletin(generer_bulletin(self._profil('H1'), self.periode))
        valider_bulletin(generer_bulletin(
            self._profil('H2', self.pays_eur), self.periode))
        with self.assertRaises(ValidationError) as ctx:
            devise_virement_periode(self.periode)
        message = str(ctx.exception)
        self.assertIn('plusieurs', message)
        self.assertIn('EUR', message)
        self.assertIn('MAD', message)

    def test_periode_sans_bulletin_retombe_sur_la_devise_du_run(self):
        self.assertEqual(devise_virement_periode(self.periode), 'MAD')

    # ── Isolation société ──────────────────────────────────────────────────

    def test_isolation_societe(self):
        autre = make_company('ntpay13-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), rib='0117800000000000000000ZZ',
            affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, periode_autre))

        # Le bulletin EUR de l'autre société ne contamine jamais ce run-ci.
        valider_bulletin(generer_bulletin(
            self._profil('I1', self.pays_eur), self.periode))
        self.assertEqual(devise_virement_periode(periode_autre), 'MAD')
        self.assertEqual(devise_virement_periode(self.periode), 'EUR')
