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
    assiette_taux_catalogue_non_calculable,
    calculer_bulletin,
    ensure_defaults,
    ensure_rubriques_standard,
    ensure_structures_standard,
    generer_bulletin,
    montant_rubrique_employe,
    rubriques_employe_actives,
)
from apps.paie.tests.test_avances import auth, make_user
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
        # Garde d'assiette (revue Fable 2026-08-26) : un taux CATALOGUE dont la
        # base déclarée (défaut « brut ») n'est pas calculable à ce stade doit
        # échouer FORT — jamais s'appliquer en silence au salaire de base.
        self.rub.taux = Decimal('2')
        self.rub.save()
        re_ = RubriqueEmploye(rubrique=self.rub, montant=None, taux=None)
        with self.assertRaises(ValueError):
            montant_rubrique_employe(re_, Decimal('10000'))

    def test_catalogue_taux_assiette_autre_calculable(self):
        # base='autre' = l'assiette documentée (salaire de base prorata) : seul
        # cas où le taux catalogue s'applique sans surcharge.
        self.rub.taux = Decimal('2')
        self.rub.base = 'autre'
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


# ── assiette_taux_catalogue_non_calculable — fonction pure (Fable review) ──

class AssietteTauxCatalogueNonCalculableTests(TestCase):
    def setUp(self):
        self.co = make_company('wir243-assiette-pure')

    def test_montant_fixe_present_jamais_incalculable(self):
        rub = Rubrique.objects.create(
            company=self.co, code='MF1', libelle='MF1', type=Rubrique.TYPE_GAIN,
            base=Rubrique.BASE_BRUT, taux=Decimal('2'), montant_fixe=Decimal('300'))
        self.assertFalse(assiette_taux_catalogue_non_calculable(rub))

    def test_sans_taux_catalogue_jamais_incalculable(self):
        rub = Rubrique.objects.create(
            company=self.co, code='NT1', libelle='NT1', type=Rubrique.TYPE_GAIN,
            base=Rubrique.BASE_BRUT)
        self.assertFalse(assiette_taux_catalogue_non_calculable(rub))

    def test_assiette_autre_jamais_incalculable(self):
        rub = Rubrique.objects.create(
            company=self.co, code='AU1', libelle='AU1', type=Rubrique.TYPE_GAIN,
            base=Rubrique.BASE_AUTRE, taux=Decimal('2'))
        self.assertFalse(assiette_taux_catalogue_non_calculable(rub))

    def test_brut_brut_imposable_net_imposable_plafonnee_cnss_incalculables(self):
        bases = (
            Rubrique.BASE_BRUT, Rubrique.BASE_BRUT_IMPOSABLE,
            Rubrique.BASE_NET_IMPOSABLE, Rubrique.BASE_PLAFONNEE_CNSS,
        )
        for i, base in enumerate(bases):
            rub = Rubrique.objects.create(
                company=self.co, code=f'INC{i}', libelle='Incalculable',
                type=Rubrique.TYPE_GAIN, base=base, taux=Decimal('2'))
            self.assertTrue(
                assiette_taux_catalogue_non_calculable(rub), msg=base)


# ── Garde moteur (WIR243, Fable review) : échec bruyant, jamais silencieux ─

class AssietteTauxCatalogueGuardMoteurTests(TestCase):
    """Un enregistrement créé HORS API (Django admin, ou une StructurePaie
    appliquée avant ce correctif) échoue BRUYAMMENT au calcul plutôt que de
    sous-payer en silence."""

    def setUp(self):
        self.co = make_company('wir243-guard-moteur')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'WG1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)

    def test_taux_catalogue_sur_brut_leve_value_error_au_calcul(self):
        rub = Rubrique.objects.create(
            company=self.co, code='LEGACY_BRUT', libelle='Legacy % du brut',
            type=Rubrique.TYPE_GAIN, base=Rubrique.BASE_BRUT, taux=Decimal('2'))
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub)
        with self.assertRaises(ValueError):
            calculer_bulletin(self.profil, self.periode)

    def test_taux_catalogue_sur_assiette_autre_ne_leve_rien(self):
        rub = Rubrique.objects.create(
            company=self.co, code='LEGACY_AUTRE', libelle='Legacy taux autre',
            type=Rubrique.TYPE_GAIN, base=Rubrique.BASE_AUTRE, taux=Decimal('5'))
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub)
        res = calculer_bulletin(self.profil, self.periode)
        # 5 % de 10 000 (salaire de base) = 500 -> brut = 10 500.
        self.assertEqual(res['brut'], Decimal('10500.00'))


# ── API : refus au rattachement (WIR243, Fable review) ─────────────────────

class RubriqueEmployeAttachabiliteApiTests(TestCase):
    """ANCIENNETE et COTISATION ne peuvent JAMAIS être rattachées comme
    rubrique récurrente — double comptage / calculée séparément par le
    moteur. Le message est un ValidationError DRF clair, en français."""
    BASE = '/api/django/paie/rubriques-employe/'

    def setUp(self):
        self.co = make_company('wir243-attach-api')
        ensure_defaults(self.co)
        self.user = make_user(self.co, 'wir243-attach-user')
        self.dossier = make_dossier(self.co, 'WA1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))

    def test_refuse_anciennete(self):
        rub = make_rubrique(self.co, 'ANCIENNETE', imposable=True)
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id, 'montant': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('rubrique', resp.data)
        self.assertIn('ancienneté', str(resp.data['rubrique']).lower())
        self.assertFalse(
            RubriqueEmploye.objects.filter(profil=self.profil).exists())

    def test_refuse_cotisation(self):
        rub = Rubrique.objects.create(
            company=self.co, code='CNSS', libelle='Cotisation CNSS',
            type=Rubrique.TYPE_COTISATION)
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id, 'montant': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('rubrique', resp.data)
        self.assertIn('cotisation', str(resp.data['rubrique']).lower())
        self.assertFalse(
            RubriqueEmploye.objects.filter(profil=self.profil).exists())

    def test_gain_normal_toujours_autorise(self):
        rub = make_rubrique(self.co, 'TRANSPORT', imposable=False)
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id, 'montant': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


# ── API : refus taux catalogue sur assiette non calculable ─────────────────

class RubriqueEmployeAssietteTauxApiTests(TestCase):
    BASE = '/api/django/paie/rubriques-employe/'

    def setUp(self):
        self.co = make_company('wir243-assiette-api')
        ensure_defaults(self.co)
        self.user = make_user(self.co, 'wir243-assiette-user')
        self.dossier = make_dossier(self.co, 'WA2')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))

    def test_refuse_taux_catalogue_sur_brut_sans_surcharge(self):
        rub = Rubrique.objects.create(
            company=self.co, code='PRIME_BRUT', libelle='Prime % du brut',
            type=Rubrique.TYPE_GAIN, base=Rubrique.BASE_BRUT, taux=Decimal('2'))
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('rubrique', resp.data)
        self.assertFalse(
            RubriqueEmploye.objects.filter(profil=self.profil).exists())

    def test_montant_override_exempte_le_refus(self):
        rub = Rubrique.objects.create(
            company=self.co, code='PRIME_BRUT2', libelle='Prime % du brut',
            type=Rubrique.TYPE_GAIN, base=Rubrique.BASE_BRUT, taux=Decimal('2'))
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id, 'montant': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_taux_catalogue_sur_assiette_autre_autorise(self):
        rub = Rubrique.objects.create(
            company=self.co, code='PRIME_AUTRE', libelle='Prime taux autre',
            type=Rubrique.TYPE_GAIN, base=Rubrique.BASE_AUTRE, taux=Decimal('2'))
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id, 'rubrique': rub.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
