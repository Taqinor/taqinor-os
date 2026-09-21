"""CALX243 — l'équilibrage des phases, et le seuil qui n'est pas dans le code.

CE QUE CE FICHIER GARDE
-----------------------
1. **Rien d'imposé ⇒ TOURNIQUET.** Trois onduleurs monophasés identiques se
   posent sur L1, L2, L3 — plus jamais trois sur la même phase sans un mot.
2. **Quatre onduleurs DÉSÉQUILIBRENT, et le chiffre le dit** : le
   déséquilibre est publié en pourcentage de la phase la plus chargée.
3. **Une attribution SAISIE est respectée** et se voit dans `source`.
4. **Réseau monophasé ⇒ aucun calcul**, et le motif dit pourquoi.
5. **Aucun seuil en dur** : le verdict n'existe que si
   `seuil_desequilibre_pct` est réglé AVEC sa source (registre CALX145) —
   sinon le chiffre est publié et le verdict est omis en nommant la clé.

Ce fichier ÉPINGLE aussi le contrat CALX205
(`contract_samples/calepinage_raccordement.json`) clé pour clé : les cinq
codes de verdict, les motifs d'omission publiés, et les deux refus.

Aucune base de données : des dicts et le registre des réglages.

Run :
    python manage.py test \\
        apps.calepinage.tests.test_calx243_equilibrage_phases
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.parametres_cles import CLES_ELECTRIQUE_SOCIETE
from apps.calepinage.services.raccordement import (
    CLE_SEUIL_DESEQUILIBRE, CODE_DESEQUILIBRE, CODE_ELEVATION,
    CODE_PUISSANCE_SOUSCRITE, CODE_REGIME_PHASES, CODE_TENSION_NOMINALE,
    LIBELLES, MOTIF_SANS_LIMITE, MOTIF_SANS_PHASES,
    MOTIF_SANS_PUISSANCE_SOUSCRITE, MOTIF_SANS_SEUIL_DESEQUILIBRE,
    MOTIF_SANS_TENSION_NOMINALE, REFUS_COS_PHI_SANS_SOURCE,
    REFUS_LIMITE_SANS_SOURCE, repartition_des_phases,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
RACCORDEMENT = json.loads(
    (ECHANTILLONS / 'calepinage_raccordement.json').read_text(
        encoding='utf-8'))


# Un parc d'onduleurs monophasés de MÊME puissance : le cas où seul le
# nombre décide du déséquilibre.
def _parc(nombre, **ajouts):
    return [dict({'repere': 'ONDU%d' % rang, 'puissance_kva': 5.0,
                  'phases': 1}, **ajouts)
            for rang in range(1, nombre + 1)]


# Un seuil RÉGLÉ avec sa source — la valeur est celle du cas de test, elle
# n'est posée par aucun code du dépôt.
def _reglages(seuil):
    return {CLE_SEUIL_DESEQUILIBRE: {
        'valeur': seuil,
        'source': "réglage société d'essai (valeur du cas de test)"}}


class TourniquetTest(SimpleTestCase):
    """Trois onduleurs identiques s'équilibrent tout seuls."""

    def test_trois_onduleurs_equilibres(self):
        bloc = repartition_des_phases(_parc(3), 3)

        self.assertEqual([ligne['phase'] for ligne in bloc['affectation']],
                         [1, 2, 3])
        self.assertEqual(bloc['par_phase'], {1: 5.0, 2: 5.0, 3: 5.0})
        self.assertEqual(bloc['desequilibre_pct'], 0.0)

    def test_le_tourniquet_se_declare(self):
        for ligne in repartition_des_phases(_parc(3), 3)['affectation']:
            self.assertIn('tourniquet', ligne['source'])

    def test_quatre_onduleurs_desequilibrent_et_le_chiffre_le_dit(self):
        bloc = repartition_des_phases(_parc(4), 3)

        self.assertEqual(bloc['par_phase'], {1: 10.0, 2: 5.0, 3: 5.0})
        # (10 − 5) / 10 : le déséquilibre se lit EN POURCENTAGE DE LA PHASE
        # LA PLUS CHARGÉE.
        self.assertEqual(bloc['desequilibre_pct'], 50.0)

    def test_un_onduleur_triphase_charge_les_trois_phases(self):
        bloc = repartition_des_phases(
            [{'repere': 'ONDU1', 'puissance_kva': 9.0, 'phases': 3}], 3)

        self.assertEqual(bloc['par_phase'], {1: 3.0, 2: 3.0, 3: 3.0})
        self.assertIsNone(bloc['affectation'][0]['phase'])
        self.assertEqual(bloc['desequilibre_pct'], 0.0)


class AttributionSaisieTest(SimpleTestCase):
    """La saisie l'emporte sur le tourniquet, et elle se voit."""

    def test_l_attribution_saisie_est_respectee(self):
        parc = _parc(3)
        parc[0]['phase_imposee'] = 3
        parc[1]['phase_imposee'] = 3
        bloc = repartition_des_phases(parc, 3)

        self.assertEqual([ligne['phase'] for ligne in bloc['affectation']],
                         [3, 3, 1])
        self.assertEqual(bloc['par_phase'], {1: 5.0, 2: 0.0, 3: 10.0})

    def test_la_source_nomme_la_saisie(self):
        parc = _parc(1)
        parc[0]['phase_imposee'] = 'L2'
        bloc = repartition_des_phases(parc, 3)

        self.assertEqual(bloc['affectation'][0]['phase'], 2)
        self.assertIn('phase_imposee', bloc['affectation'][0]['source'])


class OmissionsTest(SimpleTestCase):
    """Monophasé, régime absent, puissance absente : rien n'est supposé."""

    def test_reseau_monophase_aucun_calcul_et_motif_dit(self):
        bloc = repartition_des_phases(_parc(3), 1)

        self.assertIsNone(bloc['desequilibre_pct'])
        self.assertEqual(bloc['affectation'], [])
        self.assertTrue(any('monophasé' in motif
                            for motif in bloc['omissions']))

    def test_regime_non_saisi_nomme_le_champ(self):
        bloc = repartition_des_phases(_parc(3), None)

        self.assertIsNone(bloc['desequilibre_pct'])
        self.assertTrue(any('phases' in motif for motif in bloc['omissions']))

    def test_sans_puissance_aucune_repartition(self):
        bloc = repartition_des_phases(
            [{'repere': 'ONDU1', 'phases': 1}], 3)

        self.assertIsNone(bloc['desequilibre_pct'])
        self.assertTrue(any('ONDU1' in motif for motif in bloc['omissions']))

    def test_un_parc_qui_melange_les_unites_est_omis(self):
        bloc = repartition_des_phases(
            [{'repere': 'ONDU1', 'puissance_kva': 5.0, 'phases': 1},
             {'repere': 'ONDU2', 'ac_kw': 5.0, 'phases': 1}], 3)

        self.assertIsNone(bloc['desequilibre_pct'])
        self.assertTrue(any('MÊME nature' in motif
                            for motif in bloc['omissions']))


class SeuilTest(SimpleTestCase):
    """Aucun seuil en dur : le verdict n'existe qu'avec le réglage société."""

    def test_la_cle_du_seuil_existe_au_registre(self):
        self.assertIn(CLE_SEUIL_DESEQUILIBRE,
                      [cle for cle, _l, _u, _r in CLES_ELECTRIQUE_SOCIETE])

    def test_sans_seuil_le_chiffre_est_publie_et_le_verdict_omis(self):
        bloc = repartition_des_phases(_parc(4), 3)

        self.assertEqual(bloc['desequilibre_pct'], 50.0)
        self.assertEqual(bloc['verdict'].statut, 'non_verifiable')
        self.assertIsNone(bloc['verdict'].borne)
        self.assertIn(CLE_SEUIL_DESEQUILIBRE, bloc['verdict'].libelle)

    def test_un_seuil_sans_source_ne_fonde_aucun_verdict(self):
        bloc = repartition_des_phases(
            _parc(4), 3,
            reglages={CLE_SEUIL_DESEQUILIBRE: {'valeur': 10.0,
                                               'source': ''}})

        self.assertEqual(bloc['verdict'].statut, 'non_verifiable')
        self.assertIsNone(bloc['seuil_pct'])

    def test_seuil_respecte(self):
        bloc = repartition_des_phases(_parc(3), 3, reglages=_reglages(10.0))

        self.assertEqual(bloc['verdict'].statut, 'ok')
        self.assertEqual(bloc['verdict'].borne, 10.0)
        self.assertIn('source', bloc['verdict'].source)

    def test_seuil_franchi_alerte(self):
        bloc = repartition_des_phases(_parc(4), 3, reglages=_reglages(10.0))

        self.assertEqual(bloc['verdict'].statut, 'alerte')
        self.assertEqual(bloc['verdict'].valeur, 50.0)
        self.assertIn('phase_imposee', bloc['verdict'].libelle)


class ContratCalx205Test(SimpleTestCase):
    """Le contrat CALX205 est ÉPINGLÉ clé pour clé sur ce module."""

    def test_les_cinq_codes_sont_ceux_du_contrat(self):
        attendus = [verdict['code']
                    for verdict in RACCORDEMENT['exemple']['verdicts']]

        self.assertEqual(
            [CODE_ELEVATION, CODE_PUISSANCE_SOUSCRITE, CODE_REGIME_PHASES,
             CODE_TENSION_NOMINALE, CODE_DESEQUILIBRE], attendus)

    def test_les_intitules_sont_ceux_du_contrat(self):
        for verdict in RACCORDEMENT['exemple']['verdicts']:
            self.assertEqual(LIBELLES[verdict['code']], verdict['libelle'],
                             verdict['code'])

    def test_les_motifs_d_omission_sont_ceux_du_contrat(self):
        publies = {verdict['code']: verdict['detail']
                   for verdict in RACCORDEMENT['exemple_vide']['verdicts']}

        self.assertEqual(publies[CODE_ELEVATION], MOTIF_SANS_LIMITE)
        self.assertEqual(publies[CODE_PUISSANCE_SOUSCRITE],
                         MOTIF_SANS_PUISSANCE_SOUSCRITE)
        self.assertEqual(publies[CODE_REGIME_PHASES], MOTIF_SANS_PHASES)
        self.assertEqual(publies[CODE_TENSION_NOMINALE],
                         MOTIF_SANS_TENSION_NOMINALE)
        self.assertEqual(publies[CODE_DESEQUILIBRE],
                         MOTIF_SANS_SEUIL_DESEQUILIBRE)

    def test_les_deux_refus_sont_ceux_du_contrat(self):
        self.assertEqual(
            RACCORDEMENT['refus_limite_sans_source']['source_limite'],
            REFUS_LIMITE_SANS_SOURCE)
        self.assertEqual(
            RACCORDEMENT['refus_cos_phi_sans_source']['source_cos_phi'],
            REFUS_COS_PHI_SANS_SOURCE)

    def test_la_cle_du_desequilibre_est_sans_accent(self):
        # Une seule graphie pour une même grandeur — c'est exactement ce que
        # le dossier de contrats existe pour empêcher.
        self.assertIn('desequilibre_pct', RACCORDEMENT['exemple']['calcul'])
        self.assertNotIn('deséquilibre_pct',
                         RACCORDEMENT['exemple']['calcul'])
