"""CALX242 — puissance de raccordement et régime mono/tri.

CE QUE CE FICHIER GARDE
-----------------------
1. **Puissance souscrite dépassée = ALERTE** — un dépassement se NÉGOCIE
   (abonnement, bridage), il n'arrête pas une conception ; et le libellé
   nomme « puissance_souscrite_kva », le champ à corriger.
2. **Onduleur TRIPHASÉ sur un branchement MONOPHASÉ = BLOQUANT** — ça ne se
   négocie pas. L'inverse (monophasé sur réseau triphasé) est NORMAL : c'est
   l'équilibrage des phases qui s'en occupe, jamais un refus.
3. **Tension saisie qui DIVERGE de celle du calcul = BLOQUANT** — sinon
   toutes les chutes déjà publiées portent sur une tension que personne n'a
   sur son compteur.
4. **Sans aucune saisie, les trois contrôles sont OMIS** en nommant leur
   champ : ni 230 V, ni 400 V, ni un régime ne sont supposés.

Un cos φ imposé sans sa source est REFUSÉ en nommant le champ (D-CALX 7).

Aucun seuil n'est écrit ici : les puissances comparées sont celles que les
cas SAISISSENT, et le régime est celui de la fiche onduleur.

Aucune base de données : le noyau pur et des dicts.

Run :
    python manage.py test \\
        apps.calepinage.tests.test_calx242_raccordement_verdicts
"""
import dataclasses

from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.raccordement import (
    CODE_PUISSANCE_SOUSCRITE, CODE_REGIME_PHASES, CODE_TENSION_NOMINALE,
    RaccordementInvalide, verdicts_raccordement,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}

#: Le cos φ IMPOSÉ du site, avec sa source — jamais un 1,0 supposé.
COS_PHI = {'cos_phi_impose': 0.9,
           'source_cos_phi': "contrat de raccordement du site (valeur d'essai)"}


def _conception(phases=3, s_max_kva=None):
    conception = concevoir_par_pan(
        LAYOUT, module_specs=MODULE,
        onduleur_specs=dict(ONDULEUR, phases=phases),
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}))
    if s_max_kva is None:
        return conception
    entree = conception.entree
    onduleur = dataclasses.replace(entree.onduleur, s_max_kva=s_max_kva)
    return dataclasses.replace(
        conception, entree=dataclasses.replace(entree, onduleur=onduleur))


def _par_code(bloc):
    return {verdict.code: verdict for verdict in bloc['verdicts']}


class PuissanceSouscriteTest(SimpleTestCase):
    """Le dépassement s'ALERTE, il ne bloque pas — et il nomme son champ."""

    def test_la_souscrite_couvre_l_injection(self):
        bloc = verdicts_raccordement(
            _conception(s_max_kva=11.0),
            dict(COS_PHI, puissance_souscrite_kva=12.0))
        verdict = _par_code(bloc)[CODE_PUISSANCE_SOUSCRITE]

        self.assertEqual(bloc['puissance_injectee_kva'], 11.0)
        self.assertEqual(verdict.statut, 'ok')
        self.assertEqual(verdict.borne, 12.0)

    def test_la_souscrite_depassee_alerte_en_nommant_le_champ(self):
        bloc = verdicts_raccordement(
            _conception(s_max_kva=11.0),
            dict(COS_PHI, puissance_souscrite_kva=9.0))
        verdict = _par_code(bloc)[CODE_PUISSANCE_SOUSCRITE]

        self.assertEqual(verdict.statut, 'alerte')
        self.assertIn('puissance_souscrite_kva', verdict.libelle)
        self.assertEqual(verdict.valeur, 11.0)

    def test_la_fiche_prime_sur_le_cos_phi_saisi(self):
        # `s_max_kva` est la puissance APPARENTE garantie par le
        # constructeur : elle n'a pas à être reconstruite d'un cos φ.
        bloc = verdicts_raccordement(_conception(s_max_kva=11.0),
                                     dict(COS_PHI))

        self.assertIn('s_max_kva', bloc['source_puissance'])

    def test_sans_fiche_le_cos_phi_impose_sert_et_se_voit(self):
        bloc = verdicts_raccordement(_conception(), dict(COS_PHI))

        self.assertIn('cos_phi_impose', bloc['source_puissance'])
        self.assertIn('contrat de raccordement', bloc['source_puissance'])
        self.assertGreater(bloc['puissance_injectee_kva'], 10.0)

    def test_sans_s_max_ni_cos_phi_aucune_puissance_apparente_n_est_supposee(
            self):
        bloc = verdicts_raccordement(_conception(),
                                     {'puissance_souscrite_kva': 12.0})
        verdict = _par_code(bloc)[CODE_PUISSANCE_SOUSCRITE]

        self.assertIsNone(bloc['puissance_injectee_kva'])
        self.assertEqual(verdict.statut, 'non_verifiable')
        self.assertIn('s_max_kva', verdict.libelle)
        self.assertIn('cos_phi_impose', verdict.libelle)

    def test_cos_phi_sans_source_refuse_en_nommant_le_champ(self):
        with self.assertRaises(RaccordementInvalide) as refus:
            verdicts_raccordement(_conception(), {'cos_phi_impose': 0.9})

        self.assertEqual(refus.exception.champ,
                         'raccordement.source_cos_phi')


class RegimePhasesTest(SimpleTestCase):
    """Le seul refus est l'onduleur triphasé sur un branchement monophasé."""

    def test_triphase_sur_branchement_monophase_bloque(self):
        bloc = verdicts_raccordement(_conception(phases=3),
                                     dict(COS_PHI, phases=1))
        verdict = _par_code(bloc)[CODE_REGIME_PHASES]

        self.assertEqual(verdict.statut, 'bloquant')
        self.assertIn('phases', verdict.libelle)
        self.assertEqual(bloc['phases_onduleur'], 3)

    def test_les_deux_regimes_concordent(self):
        verdict = _par_code(verdicts_raccordement(
            _conception(phases=3), dict(COS_PHI, phases=3)))[
                CODE_REGIME_PHASES]

        self.assertEqual(verdict.statut, 'ok')
        self.assertIn('concordent', verdict.libelle)

    def test_monophase_sur_reseau_triphase_est_admis(self):
        verdict = _par_code(verdicts_raccordement(
            _conception(phases=1), dict(COS_PHI, phases=3)))[
                CODE_REGIME_PHASES]

        self.assertEqual(verdict.statut, 'ok')
        self.assertIn('déséquilibre', verdict.libelle)


class TensionNominaleTest(SimpleTestCase):
    """La tension du calcul est CONFRONTÉE à celle du branchement."""

    def test_tensions_identiques(self):
        bloc = verdicts_raccordement(
            _conception(phases=3),
            dict(COS_PHI, phases=3, tension_nominale_v=400.0))
        verdict = _par_code(bloc)[CODE_TENSION_NOMINALE]

        self.assertEqual(bloc['tension_employee_v'], 400.0)
        self.assertEqual(verdict.statut, 'ok')

    def test_divergence_bloquante_en_nommant_le_champ(self):
        verdict = _par_code(verdicts_raccordement(
            _conception(phases=3),
            dict(COS_PHI, phases=3, tension_nominale_v=230.0)))[
                CODE_TENSION_NOMINALE]

        self.assertEqual(verdict.statut, 'bloquant')
        self.assertIn('tension_nominale_v', verdict.libelle)
        self.assertEqual(verdict.borne, 230.0)
        self.assertEqual(verdict.valeur, 400.0)


class SansAucuneSaisieTest(SimpleTestCase):
    """Les trois contrôles sont OMIS, et aucune valeur n'est supposée."""

    def test_les_trois_controles_sont_omis(self):
        verdicts = _par_code(verdicts_raccordement(_conception(), {}))

        for code in (CODE_PUISSANCE_SOUSCRITE, CODE_REGIME_PHASES,
                     CODE_TENSION_NOMINALE):
            self.assertEqual(verdicts[code].statut, 'non_verifiable', code)
            self.assertIsNone(verdicts[code].borne, code)

    def test_aucun_230_ni_400_n_est_suppose(self):
        verdict = _par_code(verdicts_raccordement(_conception(), {}))[
            CODE_TENSION_NOMINALE]

        self.assertIn('230 V', verdict.libelle)
        self.assertIn('400 V', verdict.libelle)
        self.assertIn('supposés', verdict.libelle)

    def test_chaque_motif_nomme_son_champ(self):
        verdicts = _par_code(verdicts_raccordement(_conception(), {}))

        self.assertIn('puissance_souscrite_kva',
                      verdicts[CODE_PUISSANCE_SOUSCRITE].libelle)
        self.assertIn('phases', verdicts[CODE_REGIME_PHASES].libelle)
        self.assertIn('tension_nominale_v',
                      verdicts[CODE_TENSION_NOMINALE].libelle)

    def test_sans_conception_rien_n_est_invente(self):
        bloc = verdicts_raccordement(None, {'phases': 3,
                                            'tension_nominale_v': 400.0})

        self.assertIsNone(bloc['puissance_injectee_kva'])
        self.assertIsNone(bloc['tension_employee_v'])
        for verdict in bloc['verdicts']:
            self.assertEqual(verdict.statut, 'non_verifiable', verdict.code)
