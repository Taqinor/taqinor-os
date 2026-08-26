"""Tests WIR243 — RubriqueEmploye enfin branchée à ``calculer_bulletin``.

Avant ce correctif, une rubrique récurrente rattachée à un profil (PAIE9 :
prime de transport, indemnité de panier…) n'avait AUCUN effet sur le
bulletin — la brique existait (modèle + CRUD) mais n'était jamais lue par le
moteur de calcul. Couvre :

* ``rubriques_employe_actives`` — fenêtre ``date_debut``/``date_fin``
  (facultatives), garde ``actif``, exclusion explicite du code catalogue
  ``ANCIENNETE`` (déjà recalculée par ``calculer_prime_anciennete`` — une
  ``RubriqueEmploye`` de ce code, posée par une ``StructurePaie``, ne doit
  JAMAIS être re-sommée sous peine de compter la prime deux fois).
* ``montant_rubrique_employe`` — ordre de priorité : surcharge montant >
  surcharge taux (assiette salaire de base) > montant_fixe catalogue > taux
  catalogue > 0 (rubrique à saisie manuelle sans aucune surcharge/défaut).
* ``calculer_bulletin`` — intégration bout en bout (le scénario « Done » du
  plan) : une prime de transport 500 MAD rattachée ajoute +500 au brut du
  bulletin régénéré ; désactivation ou fenêtre expirée la retire ; une
  RETENUE rattachée ne touche jamais le brut, seulement le net à payer.
* ``ensure_structures_standard``/``appliquer_structure_a_profil`` restent
  idempotents et n'introduisent jamais de double comptage de la prime
  d'ancienneté ni d'argent inventé (une ligne de structure sans montant
  configuré ne vaut jamais un montant par défaut arbitraire).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.paie.models import Rubrique, RubriqueEmploye, StructurePaie
from apps.paie.services import (
    appliquer_structure_a_profil,
    calculer_bulletin,
    ensure_defaults,
    ensure_rubriques_standard,
    ensure_structures_standard,
    generer_bulletin,
    montant_rubrique_employe,
    rubriques_employe_actives,
)
from apps.paie.tests.test_avantages import (
    make_company,
    make_dossier,
    make_periode,
    make_profil,
    make_rubrique,
)


# ── rubriques_employe_actives — fenêtre de dates + garde actif ─────────────

class RubriquesEmployeActivesTests(TestCase):
    def setUp(self):
        self.co = make_company('wir243-fenetre')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'W1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)
        self.rub = make_rubrique(self.co, 'TRANSPORT', imposable=False)

    def _rattacher(self, **kwargs):
        return RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.rub, **kwargs)

    def test_active_sans_fenetre(self):
        re_ = self._rattacher(montant=Decimal('500'))
        self.assertIn(re_, rubriques_employe_actives(self.profil, self.periode))

    def test_inactive_exclue(self):
        re_ = self._rattacher(montant=Decimal('500'), actif=False)
        self.assertNotIn(
            re_, rubriques_employe_actives(self.profil, self.periode))

    def test_date_debut_apres_la_periode_exclue(self):
        re_ = self._rattacher(
            montant=Decimal('500'), date_debut=date(2026, 7, 1))
        self.assertNotIn(
            re_, rubriques_employe_actives(self.profil, self.periode))

    def test_date_fin_avant_la_periode_exclue(self):
        re_ = self._rattacher(
            montant=Decimal('500'), date_fin=date(2026, 5, 31))
        self.assertNotIn(
            re_, rubriques_employe_actives(self.profil, self.periode))

    def test_fenetre_couvrant_le_mois_incluse(self):
        re_ = self._rattacher(
            montant=Decimal('500'),
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))
        self.assertIn(re_, rubriques_employe_actives(self.profil, self.periode))

    def test_fenetre_debordant_le_mois_incluse(self):
        """Une fenêtre qui couvre PARTIELLEMENT le mois reste active ce mois-ci."""
        re_ = self._rattacher(
            montant=Decimal('500'),
            date_debut=date(2026, 6, 15), date_fin=date(2026, 8, 31))
        self.assertIn(re_, rubriques_employe_actives(self.profil, self.periode))

    def test_anciennete_toujours_exclue(self):
        """Jamais re-sommée : déjà couverte par calculer_prime_anciennete."""
        rub_anciennete = make_rubrique(self.co, 'ANCIENNETE', imposable=True)
        re_ = RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub_anciennete)
        self.assertNotIn(
            re_, rubriques_employe_actives(self.profil, self.periode))


# ── montant_rubrique_employe — ordre de priorité des surcharges ───────────

class MontantRubriqueEmployeTests(TestCase):
    def setUp(self):
        self.co = make_company('wir243-montant')
        self.rub = make_rubrique(self.co, 'PRIME_X', imposable=False)

    def test_surcharge_montant_prioritaire_sur_taux(self):
        re_ = RubriqueEmploye(
            rubrique=self.rub, montant=Decimal('500'), taux=Decimal('10'))
        self.assertEqual(
            montant_rubrique_employe(re_, Decimal('10000')), Decimal('500.00'))

    def test_surcharge_taux_appliquee_au_salaire_de_base(self):
        re_ = RubriqueEmploye(rubrique=self.rub, montant=None, taux=Decimal('5'))
        self.assertEqual(
            montant_rubrique_employe(re_, Decimal('10000')), Decimal('500.00'))

    def test_defaut_catalogue_montant_fixe(self):
        self.rub.montant_fixe = Decimal('300')
        self.rub.save()
        re_ = RubriqueEmploye(rubrique=self.rub, montant=None, taux=None)
        self.assertEqual(
            montant_rubrique_employe(re_, Decimal('10000')), Decimal('300.00'))

    def test_defaut_catalogue_taux_meme_assiette(self):
        self.rub.taux = Decimal('2')
        self.rub.save()
        re_ = RubriqueEmploye(rubrique=self.rub, montant=None, taux=None)
        self.assertEqual(
            montant_rubrique_employe(re_, Decimal('10000')), Decimal('200.00'))

    def test_rien_renseigne_zero(self):
        re_ = RubriqueEmploye(rubrique=self.rub, montant=None, taux=None)
        self.assertEqual(
            montant_rubrique_employe(re_, Decimal('10000')), Decimal('0.00'))


# ── calculer_bulletin — scénario « Done » du plan (WIR243) ─────────────────

class CalculerBulletinRubriqueEmployeTests(TestCase):
    """Prime transport 500 MAD rattachée -> +500 au brut ; retirable."""

    def setUp(self):
        self.co = make_company('wir243-bulletin')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'W2')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)
        self.rub_transport = make_rubrique(
            self.co, 'TRANSPORT', imposable=False, plafond=Decimal('500'))

    def test_prime_rattachee_ajoute_500_au_brut(self):
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.rub_transport,
            montant=Decimal('500'))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('10500.00'))
        # Sous le plafond d'exonération (500) -> jamais dans le brut imposable.
        self.assertEqual(res['brut_imposable'], Decimal('10000.00'))
        self.assertTrue(
            any(ligne['code'] == 'TRANSPORT'
                and ligne['montant'] == Decimal('500.00')
                for ligne in res['lignes']))

    def test_desactivation_retire_la_prime(self):
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.rub_transport,
            montant=Decimal('500'), actif=False)
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('10000.00'))

    def test_fenetre_expiree_retire_la_prime(self):
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.rub_transport,
            montant=Decimal('500'), date_fin=date(2026, 5, 31))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('10000.00'))

    def test_bulletin_regenere_reprend_le_nouveau_brut(self):
        """Le bulletin RÉGÉNÉRÉ (generer_bulletin) reflète la rubrique rattachée."""
        bulletin = generer_bulletin(self.profil, self.periode)
        self.assertEqual(bulletin.brut, Decimal('10000.00'))
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.rub_transport,
            montant=Decimal('500'))
        bulletin2 = generer_bulletin(self.profil, self.periode)
        self.assertEqual(bulletin2.brut, Decimal('10500.00'))
        self.assertTrue(bulletin2.lignes.filter(code='TRANSPORT').exists())

    def test_retenue_rattachee_ne_touche_pas_le_brut_diminue_le_net(self):
        rub_retenue = Rubrique.objects.create(
            company=self.co, code='COTIS_X', libelle='Cotisation X',
            type=Rubrique.TYPE_RETENUE, ordre=99)
        res_avant = calculer_bulletin(self.profil, self.periode)
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub_retenue,
            montant=Decimal('100'))
        res_apres = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res_apres['brut'], res_avant['brut'])
        self.assertEqual(
            res_avant['net_a_payer'] - res_apres['net_a_payer'], Decimal('100.00'))


# ── Structures de paie — idempotence, jamais d'argent inventé ─────────────

class StructureAncienneteEtIdempotenceTests(TestCase):
    """appliquer_structure_a_profil rattache ANCIENNETE + TRANSPORT en
    RubriqueEmploye, mais calculer_bulletin ne doit ni compter ANCIENNETE
    deux fois (déjà couverte par la formule dédiée), ni inventer un montant
    pour TRANSPORT tant qu'aucune surcharge/valeur catalogue n'est fixée."""

    def setUp(self):
        self.co = make_company('wir243-structure')
        ensure_defaults(self.co)
        self.dossier = make_dossier(
            self.co, 'W3', date_embauche=date(2015, 1, 1))
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)
        ensure_rubriques_standard(self.co)
        ensure_structures_standard(self.co)
        self.structure = StructurePaie.objects.get(company=self.co, code='EMPLOYE')

    def test_appliquer_structure_ne_change_pas_le_bulletin_sans_surcharge(self):
        res_avant = calculer_bulletin(self.profil, self.periode)
        nb = appliquer_structure_a_profil(self.profil, self.structure)
        self.assertEqual(nb, 2)  # ANCIENNETE + TRANSPORT (catalogue EMPLOYE)
        res_apres = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res_apres['brut'], res_avant['brut'])
        self.assertEqual(res_apres['net_a_payer'], res_avant['net_a_payer'])

    def test_reapplication_idempotente(self):
        appliquer_structure_a_profil(self.profil, self.structure)
        nb2 = appliquer_structure_a_profil(self.profil, self.structure)
        self.assertEqual(nb2, 0)
        self.assertEqual(
            RubriqueEmploye.objects.filter(profil=self.profil).count(), 2)

    def test_structure_avec_montant_configure_ajoute_au_brut(self):
        """Un montant CONFIGURÉ sur la ligne de structure (geste explicite du
        fondateur) se répercute normalement, même mécanique que le
        rattachement manuel — jamais un défaut inventé."""
        ligne_transport = self.structure.rubriques_defaut.get(
            rubrique__code='TRANSPORT')
        ligne_transport.montant = Decimal('500')
        ligne_transport.save()
        res_avant = calculer_bulletin(self.profil, self.periode)
        appliquer_structure_a_profil(self.profil, self.structure)
        res_apres = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res_apres['brut'] - res_avant['brut'], Decimal('500.00'))
