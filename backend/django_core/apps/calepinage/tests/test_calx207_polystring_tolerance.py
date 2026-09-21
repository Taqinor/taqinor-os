# -*- coding: utf-8 -*-
"""CALX207 — l'écart de puissance d'un groupe polystring, et SON seuil société.

Quatre garanties :

1. **sans seuil saisi**, l'écart est PUBLIÉ et le verdict vaut ``omis`` en
   nommant les deux clés à régler — jamais un barème supposé (D-CALX 7) ;
2. **avec seuils saisis**, trois cas : sous l'acceptable (``ok``), entre les
   deux (``alerte``), au-dessus du bloquant (``bloquant``) ;
3. **un seuil saisi sans ``source``** est REFUSÉ en nommant le champ ;
4. les chiffres PV*SOL (« up to 4 % », « exceeding 10 % ») ne sont qu'une
   RÉFÉRENCE citée : aucune valeur n'est préremplie par le module.

Le verdict se lit par son CODE (CALX215), jamais par sa position.

``SimpleTestCase`` : aucune base.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx207_polystring_tolerance -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    CLE_POLYSTRING, evaluation_electrique, resultat_calepinage,
)
from apps.calepinage.services.parametres_cles import (
    SECTION_ELECTRIQUE_SOCIETE, registre,
)
from apps.calepinage.services.polystring import (
    CLE_TOLERANCE_ACCEPTABLE, CLE_TOLERANCE_BLOQUANTE,
    CODE_VERDICT_TOLERANCE, MOTIF_SANS_SEUIL, REFERENCE_TOLERANCE_PVSOL,
    STATUT_ALERTE, STATUT_BLOQUANT, STATUT_OK, STATUT_OMIS,
    PolystringRefuse, ecart_de_groupe,
)

from .test_calx206_polystring import (  # noqa: F401 — fixtures partagées
    GROUPE_EST_OUEST, _Calepinage, _materiel,
)


def _groupe(*puissances):
    """Un groupe de branches, une par puissance crête publiée."""
    return {'mppt': 1, 'pans': ['P%d' % i for i in range(len(puissances))],
            'branches': [{'pan': 'P%d' % rang, 'puissance_kwc': valeur,
                          'modules': 10, 'azimut_deg': 90.0 + 180.0 * rang,
                          'inclinaison_deg': 20.0}
                         for rang, valeur in enumerate(puissances)]}


def _seuils(acceptable=None, bloquante=None, source='societe'):
    reglages = {}
    if acceptable is not None:
        reglages[CLE_TOLERANCE_ACCEPTABLE] = {'valeur': acceptable,
                                              'source': source}
    if bloquante is not None:
        reglages[CLE_TOLERANCE_BLOQUANTE] = {'valeur': bloquante,
                                             'source': source}
    return reglages


class EcartMesureTest(SimpleTestCase):
    """L'écart porte sur la puissance CRÊTE, orientation publiée à côté."""

    def test_l_ecart_est_celui_de_la_branche_la_plus_faible(self):
        # 10 kWc contre 9 kWc → 10 % d'écart sur la branche la plus haute.
        rendu = ecart_de_groupe(_groupe(10.0, 9.0))

        self.assertAlmostEqual(rendu['ecart_pct'], 10.0, places=3)
        self.assertIn('10.0 kWc', rendu['base'])

    def test_chaque_branche_publie_son_orientation(self):
        rendu = ecart_de_groupe(_groupe(10.0, 9.0))

        azimuts = [mesure['azimut_deg'] for mesure in rendu['detail']]
        self.assertEqual(azimuts, [90.0, 270.0])

    def test_une_seule_branche_ne_mesure_aucun_ecart(self):
        rendu = ecart_de_groupe(_groupe(10.0))

        self.assertIsNone(rendu['ecart_pct'])
        self.assertIn('au moins DEUX branches', rendu['base'])
        self.assertEqual(rendu['verdict']['statut'], STATUT_OMIS)


class SansSeuilLeVerdictEstOmisTest(SimpleTestCase):
    """Aucun seuil saisi : l'écart se lit, le verdict se tait — et le dit."""

    def test_le_verdict_est_omis_et_nomme_les_deux_cles(self):
        rendu = ecart_de_groupe(_groupe(10.0, 9.0))
        verdict = rendu['verdict']

        self.assertEqual(verdict['code'], CODE_VERDICT_TOLERANCE)
        self.assertEqual(verdict['statut'], STATUT_OMIS)
        self.assertEqual(verdict['detail'], MOTIF_SANS_SEUIL)
        self.assertIn(CLE_TOLERANCE_ACCEPTABLE, verdict['detail'])
        self.assertIn(CLE_TOLERANCE_BLOQUANTE, verdict['detail'])
        self.assertIsNone(verdict['source'])
        self.assertIsNone(verdict['borne'])

    def test_l_ecart_reste_publie_malgre_l_omission(self):
        rendu = ecart_de_groupe(_groupe(10.0, 9.0))

        self.assertAlmostEqual(rendu['ecart_pct'], 10.0, places=3)
        self.assertAlmostEqual(rendu['verdict']['valeur'], 10.0, places=3)

    def test_les_chiffres_pvsol_restent_une_reference_citee(self):
        rendu = ecart_de_groupe(_groupe(10.0, 9.0))

        self.assertEqual(rendu['verdict']['reference'],
                         REFERENCE_TOLERANCE_PVSOL)
        self.assertIn('help.valentin-software.com',
                      REFERENCE_TOLERANCE_PVSOL)


class TroisCasAvecSeuilsTest(SimpleTestCase):
    """Sous l'acceptable, entre les deux, au-dessus du bloquant."""

    def test_sous_le_seuil_acceptable(self):
        # 10 kWc contre 9,8 kWc → 2 % d'écart, sous les 4 % saisis.
        rendu = ecart_de_groupe(_groupe(10.0, 9.8),
                                reglages=_seuils(4.0, 10.0))

        self.assertEqual(rendu['verdict']['statut'], STATUT_OK)
        self.assertEqual(rendu['verdict']['borne'], 4.0)
        self.assertIn(CLE_TOLERANCE_ACCEPTABLE, rendu['verdict']['source'])

    def test_entre_les_deux_seuils(self):
        # 10 contre 9,3 → 7 % : au-dessus de 4 %, sous 10 %.
        rendu = ecart_de_groupe(_groupe(10.0, 9.3),
                                reglages=_seuils(4.0, 10.0))

        self.assertEqual(rendu['verdict']['statut'], STATUT_ALERTE)
        self.assertIn('seuil bloquant', rendu['verdict']['detail'])

    def test_au_dessus_du_seuil_bloquant(self):
        # 10 contre 8 → 20 % : au-dessus des 10 % saisis.
        rendu = ecart_de_groupe(_groupe(10.0, 8.0),
                                reglages=_seuils(4.0, 10.0))

        self.assertEqual(rendu['verdict']['statut'], STATUT_BLOQUANT)
        self.assertEqual(rendu['verdict']['borne'], 10.0)
        self.assertIn(CLE_TOLERANCE_BLOQUANTE, rendu['verdict']['source'])

    def test_la_source_saisie_voyage_avec_le_verdict(self):
        rendu = ecart_de_groupe(_groupe(10.0, 8.0),
                                reglages=_seuils(4.0, 10.0, source='texte'))

        self.assertIn('texte', rendu['verdict']['source'])


class SeuilSansSourceRefuseTest(SimpleTestCase):
    """Un seuil sans provenance ne peut fonder aucun refus."""

    def test_le_refus_nomme_le_champ(self):
        with self.assertRaises(PolystringRefuse) as capture:
            ecart_de_groupe(_groupe(10.0, 8.0), reglages={
                CLE_TOLERANCE_BLOQUANTE: {'valeur': 10.0}})

        self.assertEqual(capture.exception.champ,
                         '%s.source' % CLE_TOLERANCE_BLOQUANTE)
        self.assertIn('sans source', str(capture.exception))

    def test_un_seuil_non_numerique_est_refuse(self):
        with self.assertRaises(PolystringRefuse) as capture:
            ecart_de_groupe(_groupe(10.0, 8.0), reglages={
                CLE_TOLERANCE_ACCEPTABLE: {'valeur': 'quatre',
                                           'source': 'societe'}})

        self.assertEqual(capture.exception.champ, CLE_TOLERANCE_ACCEPTABLE)


class LesDeuxClesSontAuRegistreTest(SimpleTestCase):
    """Aucune clé neuve : CALX145 les a déjà déclarées, avec leur référence."""

    def test_les_deux_cles_figurent_a_la_section_electrique_societe(self):
        connues = registre(SECTION_ELECTRIQUE_SOCIETE)

        self.assertIn(CLE_TOLERANCE_ACCEPTABLE, connues)
        self.assertIn(CLE_TOLERANCE_BLOQUANTE, connues)
        for cle in (CLE_TOLERANCE_ACCEPTABLE, CLE_TOLERANCE_BLOQUANTE):
            _libelle, unite, reference = connues[cle]
            self.assertEqual(unite, '%')
            self.assertIn('PV*SOL', reference)


class BranchementApplicatifTest(SimpleTestCase):
    """L'écart voyage avec le groupe publié, et son bloquant bloque."""

    def test_le_groupe_publie_porte_son_ecart(self):
        resultat = resultat_calepinage(
            _Calepinage({CLE_POLYSTRING: GROUPE_EST_OUEST}),
            materiel=_materiel())

        ecart = resultat['electrique'][CLE_POLYSTRING]['groupes'][0]['ecart']
        # Les deux versants portent 8 modules chacun : écart nul, et aucun
        # seuil n'étant saisi sur ce calepinage, le verdict reste omis.
        self.assertEqual(ecart['ecart_pct'], 0.0)
        self.assertEqual(ecart['verdict']['statut'], STATUT_OMIS)

    def test_aucune_alerte_de_tolerance_sans_seuil_saisi(self):
        evaluation = evaluation_electrique(
            _Calepinage({CLE_POLYSTRING: GROUPE_EST_OUEST}),
            materiel=_materiel())

        self.assertFalse(any(CODE_VERDICT_TOLERANCE in message
                             for message in evaluation['alertes']))
