"""Tests PAIE22 — Calcul IR (barème progressif + charges de famille), couverture
complète du barème ET de son intégration dans ``calculer_bulletin``.

Le calcul IR (helpers ``ir_bareme`` / ``deduction_charges_famille`` /
``compute_ir``) et son câblage dans le moteur de bulletin sont déjà présents
(PAIE5/PAIE12). Ce module AJOUTE la couverture comportementale manquante,
en prouvant :

  * **chaque tranche du barème progressif 2026** — y compris les tranches 30 %
    et 34 % non couvertes par ``test_ir.py`` — et les BORNES exactes de chaque
    tranche (``borne_min``/``borne_max``) ;
  * la **déduction pour charges de famille** par personne à charge ET son
    **plafonnement** au nombre légal, appliquée DANS le calcul de l'IR ;
  * l'IR appliqué à la **base réduite (net imposable)** de bout en bout via
    ``calculer_bulletin`` — l'IR du bulletin = ``compute_ir(net_imposable, …)``,
    et ``personnes_a_charge`` fait BAISSER l'IR sans toucher le brut ;
  * la propagation de ``personnes_a_charge`` jusqu'au snapshot persisté
    (``generer_bulletin`` → ``BulletinPaie.personnes_a_charge``) ;
  * le cas **zéro personne à charge** (IR = barème pur) ;
  * l'**isolation multi-société** : chaque société a son propre ``BaremeIR``,
    l'éditer chez l'une ne change pas l'IR de l'autre.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    BaremeIR,
    ParametrePaie,
    PeriodePaie,
    ProfilPaie,
    TrancheIR,
)
from apps.paie.services import (
    calculer_bulletin,
    compute_ir,
    ensure_defaults,
    generer_bulletin,
    ir_bareme,
)
from apps.rh.models import DossierEmploye


# ── Helpers ────────────────────────────────────────────────────────────────

def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_profil(company, salaire_base=Decimal('10000'), matricule='IR1'):
    dossier = DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='IR')
    return ProfilPaie.objects.create(
        company=company,
        employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=salaire_base,
        affilie_cnss=True,
        affilie_amo=True,
    )


# ── Barème progressif : chaque tranche + bornes exactes ─────────────────────

class BaremeProgressifTranchesTests(TestCase):
    """``ir_bareme`` applique la formule de CHAQUE tranche + ses bornes.

    Valeurs attendues recalculées à la main d'après ``TRANCHES_IR_2026`` :
    ``base × taux% − somme_a_deduire`` de la tranche couvrante, jamais < 0.
    """

    def setUp(self):
        self.co = make_company('paie-ir22-bareme')
        ensure_defaults(self.co)
        self.bareme = BaremeIR.objects.get(company=self.co)

    def test_tranche_0_pct(self):
        # 2000 dans la tranche 0–2500 @ 0 % : IR nul.
        self.assertEqual(ir_bareme(self.bareme, Decimal('2000')),
                         Decimal('0.00'))

    def test_tranche_10_pct(self):
        # 3000 @ 10 % − 250 = 50.
        self.assertEqual(ir_bareme(self.bareme, Decimal('3000')),
                         Decimal('50.00'))

    def test_tranche_20_pct(self):
        # 4500 @ 20 % − 666.67 = 233.33.
        self.assertEqual(ir_bareme(self.bareme, Decimal('4500')),
                         Decimal('233.33'))

    def test_tranche_30_pct(self):
        # 6000 @ 30 % − 1166.67 = 633.33 (tranche absente de test_ir.py).
        self.assertEqual(ir_bareme(self.bareme, Decimal('6000')),
                         Decimal('633.33'))

    def test_tranche_34_pct(self):
        # 10000 @ 34 % − 1433.33 = 1966.67 (tranche absente de test_ir.py).
        self.assertEqual(ir_bareme(self.bareme, Decimal('10000')),
                         Decimal('1966.67'))

    def test_tranche_38_pct_marginale(self):
        # 20000 @ 38 % − 2033.33 = 5566.67 (dernière tranche, sans plafond).
        self.assertEqual(ir_bareme(self.bareme, Decimal('20000')),
                         Decimal('5566.67'))

    def test_borne_haute_exoneree(self):
        # Borne max de la 1ʳᵉ tranche (2500) : encore exonérée.
        self.assertEqual(ir_bareme(self.bareme, Decimal('2500')),
                         Decimal('0.00'))

    def test_borne_basse_tranche_30(self):
        # 5000.01 = borne_min de la tranche 30 % : 5000.01 × 30 % − 1166.67.
        self.assertEqual(ir_bareme(self.bareme, Decimal('5000.01')),
                         Decimal('333.33'))

    def test_borne_haute_tranche_30(self):
        # 6666.67 = borne_max de la tranche 30 % : 6666.67 × 30 % − 1166.67.
        self.assertEqual(ir_bareme(self.bareme, Decimal('6666.67')),
                         Decimal('833.33'))

    def test_borne_basse_tranche_38(self):
        # 15000.01 = borne_min de la dernière tranche : 15000.01 × 38 % − 2033.33.
        self.assertEqual(ir_bareme(self.bareme, Decimal('15000.01')),
                         Decimal('3666.67'))

    def test_tres_haut_revenu(self):
        # 30000 capté par la dernière tranche : 30000 × 38 % − 2033.33 = 9366.67.
        self.assertEqual(ir_bareme(self.bareme, Decimal('30000')),
                         Decimal('9366.67'))

    def test_monotone_croissant(self):
        # L'IR du barème progressif croît avec la base imposable.
        bases = [Decimal(b) for b in
                 ('2000', '3000', '4500', '6000', '10000', '20000', '30000')]
        valeurs = [ir_bareme(self.bareme, b) for b in bases]
        for precedent, suivant in zip(valeurs, valeurs[1:]):
            self.assertLessEqual(precedent, suivant)


# ── Déduction charges de famille appliquée DANS l'IR ────────────────────────

class IRChargesFamilleTests(TestCase):
    """``compute_ir`` retranche la déduction familiale par personne, plafonnée."""

    def setUp(self):
        self.co = make_company('paie-ir22-famille')
        ensure_defaults(self.co)
        self.bareme = BaremeIR.objects.get(company=self.co)
        self.param = ParametrePaie.objects.get(company=self.co)

    def test_zero_charge_egale_bareme(self):
        base = Decimal('10000')
        self.assertEqual(
            compute_ir(base, self.bareme, self.param, 0),
            ir_bareme(self.bareme, base))

    def test_une_charge_retire_un_montant(self):
        # 1 personne → −30 sur l'IR brut.
        base = Decimal('10000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 1)
        self.assertEqual(brut - net, Decimal('30.00'))

    def test_cinq_charges_lineaire(self):
        # 5 personnes (< plafond 6) → −150.
        base = Decimal('10000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 5)
        self.assertEqual(brut - net, Decimal('150.00'))
        self.assertEqual(net, Decimal('1816.67'))

    def test_au_plafond_exact(self):
        # 6 personnes = plafond → −180.
        base = Decimal('10000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 6)
        self.assertEqual(brut - net, Decimal('180.00'))

    def test_au_dela_du_plafond_cape(self):
        # 9 personnes mais plafond 6 → réduction CAPÉE à 180, pas 270.
        base = Decimal('10000')
        brut = ir_bareme(self.bareme, base)
        net = compute_ir(base, self.bareme, self.param, 9)
        self.assertEqual(brut - net, Decimal('180.00'))

    def test_ir_plancher_zero(self):
        # IR brut faible, beaucoup de charges → IR net plancher à 0, jamais < 0.
        base = Decimal('3000')                 # IR brut 50.00
        net = compute_ir(base, self.bareme, self.param, 6)  # déduction 180
        self.assertEqual(net, Decimal('0.00'))

    def test_base_exoneree_reste_nulle(self):
        # Base exonérée : l'IR net reste nul quel que soit le nb de charges.
        self.assertEqual(
            compute_ir(Decimal('2000'), self.bareme, self.param, 4),
            Decimal('0.00'))


# ── Intégration : IR appliqué au NET IMPOSABLE via calculer_bulletin ────────

class IRBulletinIntegrationTests(TestCase):
    """L'IR du bulletin = ``compute_ir`` sur le NET IMPOSABLE (base réduite)."""

    def setUp(self):
        self.co = make_company('paie-ir22-bulletin')
        ensure_defaults(self.co)
        self.bareme = BaremeIR.objects.get(company=self.co)
        self.param = ParametrePaie.objects.get(company=self.co)
        self.profil = make_profil(self.co, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_ir_calcule_sur_net_imposable_pas_brut(self):
        # L'IR doit porter sur le net imposable (≈ 7005.20), PAS sur le brut
        # 10000 : c'est ce qui distingue le calcul correct d'un calcul naïf.
        res = calculer_bulletin(self.profil, self.periode, 0)
        ni = res['net_imposable']
        self.assertEqual(res['ir'], ir_bareme(self.bareme, ni))
        # Le net imposable est strictement inférieur au brut.
        self.assertLess(ni, res['brut'])
        # Donc l'IR < IR qu'on aurait sur le brut → preuve qu'on réduit la base.
        self.assertLess(res['ir'], ir_bareme(self.bareme, res['brut']))

    def test_ir_bulletin_egale_compute_ir(self):
        # Le bulletin câble bien compute_ir avec personnes_a_charge.
        res = calculer_bulletin(self.profil, self.periode, 2)
        ni = res['net_imposable']
        self.assertEqual(
            res['ir'], compute_ir(ni, self.bareme, self.param, 2))

    def test_charges_famille_reduisent_ir_du_bulletin(self):
        # 0 vs 2 charges sur le MÊME profil : IR baisse de 2 × 30 = 60.
        sans = calculer_bulletin(self.profil, self.periode, 0)
        avec = calculer_bulletin(self.profil, self.periode, 2)
        self.assertEqual(sans['ir'] - avec['ir'], Decimal('60.00'))
        # Le brut reste identique — seul l'IR change.
        self.assertEqual(sans['brut'], avec['brut'])

    def test_charges_famille_capees_dans_le_bulletin(self):
        # 12 charges mais plafond 6 → réduction de l'IR capée à 180.
        sans = calculer_bulletin(self.profil, self.periode, 0)
        avec = calculer_bulletin(self.profil, self.periode, 12)
        self.assertEqual(sans['ir'] - avec['ir'], Decimal('180.00'))

    def test_personnes_a_charge_persistees_dans_snapshot(self):
        # generer_bulletin matérialise personnes_a_charge dans le snapshot.
        bulletin = generer_bulletin(self.profil, self.periode, 3)
        self.assertEqual(bulletin.personnes_a_charge, 3)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.personnes_a_charge, 3)
        # Et l'IR persisté correspond au calcul avec 3 charges.
        attendu = calculer_bulletin(self.profil, self.periode, 3)['ir']
        self.assertEqual(bulletin.ir, attendu)

    def test_snapshot_par_defaut_zero_charge(self):
        # Sans argument, le bulletin est généré avec 0 personne à charge.
        bulletin = generer_bulletin(self.profil, self.periode)
        self.assertEqual(bulletin.personnes_a_charge, 0)
        self.assertEqual(
            bulletin.ir, calculer_bulletin(self.profil, self.periode, 0)['ir'])

    def test_ir_present_en_ligne_bulletin(self):
        # L'IR figure dans le détail (ligne retenue 'ir' du dict de calcul).
        res = calculer_bulletin(self.profil, self.periode, 0)
        self.assertGreater(res['ir'], Decimal('0'))


# ── Isolation multi-société du barème ──────────────────────────────────────

class IRScopingTests(TestCase):
    """Chaque société a son propre ``BaremeIR`` ; l'éditer n'affecte pas l'autre."""

    def setUp(self):
        self.co_a = make_company('paie-ir22-a')
        self.co_b = make_company('paie-ir22-b')
        ensure_defaults(self.co_a)
        ensure_defaults(self.co_b)

    def test_baremes_distincts_par_societe(self):
        bareme_a = BaremeIR.objects.get(company=self.co_a)
        bareme_b = BaremeIR.objects.get(company=self.co_b)
        self.assertNotEqual(bareme_a.pk, bareme_b.pk)
        # Les tranches sont aussi scopées par société.
        for tr in TrancheIR.objects.filter(bareme=bareme_a):
            self.assertEqual(tr.company, self.co_a)

    def test_editer_un_bareme_n_affecte_pas_l_autre(self):
        # On gonfle le taux de la tranche marginale de A.
        bareme_a = BaremeIR.objects.get(company=self.co_a)
        bareme_b = BaremeIR.objects.get(company=self.co_b)
        marginale_a = bareme_a.tranches.order_by('ordre').last()
        marginale_a.taux = Decimal('50')
        marginale_a.save()
        base = Decimal('20000')
        ir_a = ir_bareme(bareme_a, base)
        ir_b = ir_bareme(bareme_b, base)
        # B garde le barème officiel (38 % → 5566.67) ; A a changé.
        self.assertEqual(ir_b, Decimal('5566.67'))
        self.assertNotEqual(ir_a, ir_b)

    def test_deduction_familiale_scopee_par_societe(self):
        # Éditer le plafond/montant familial de A ne touche pas B.
        param_a = ParametrePaie.objects.get(company=self.co_a)
        param_b = ParametrePaie.objects.get(company=self.co_b)
        bareme_b = BaremeIR.objects.get(company=self.co_b)
        param_a.deduction_par_personne_a_charge = Decimal('100')
        param_a.plafond_personnes_a_charge = 2
        param_a.save()
        base = Decimal('10000')
        # B reste sur 30 MAD / 6 personnes.
        brut_b = ir_bareme(bareme_b, base)
        net_b = compute_ir(base, bareme_b, param_b, 6)
        self.assertEqual(brut_b - net_b, Decimal('180.00'))
