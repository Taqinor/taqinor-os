"""CALX348 — exiger l'approbation avant de retenir une variante (réglage).

Ce qui est prouvé ici :

* ÉQUIVALENCE (D12) : réglage absent ⇒ ``verifier_avant_retenue`` ne lit
  même pas la décision d'approbation, et retenir une variante marche comme
  aujourd'hui sur un calepinage jamais approuvé ;
* la clé ``approbation_exigee`` de la section ``presets`` est VALIDÉE
  booléenne à l'écriture (``services/presets.py``), refus nommant le champ ;
  toutes les autres clés de la section traversent inchangées ;
* réglage actif et calepinage non approuvé ⇒ ``ValidationError`` sur le
  champ ``approbation``, donc 400 par l'enveloppe d'erreur globale — sans
  toucher à ``views/calepinages.py`` ; le message NOMME qui doit approuver
  (les rôles de la société qui portent le droit, lus en base) ;
* réglage actif et calepinage approuvé ⇒ la variante est retenue ;
* la vérification vit au MÊME point d'entrée que le feu vert (CAL206).

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx348_approbation_exigee -v2
"""
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.calepinage.services import feu_vert
from apps.calepinage.services.parametres import (
    ReglageInvalide, _normaliseurs,
)
from apps.calepinage.services.presets import (
    CLE_APPROBATION_EXIGEE, SECTION, normaliser_section_presets,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT_PARAMETRES = json.loads(
    (RACINE_APP / 'contract_samples' / 'parametres_calepinage.json')
    .read_text(encoding='utf-8'))


def faux_calepinage(approbation=None):
    return SimpleNamespace(company=object(), approbation=approbation,
                           lead_id=None, devis=None)


class NormalisationPresetsTest(SimpleTestCase):
    """La clé est validée booléenne ; le reste de la section est intouché."""

    def test_la_cle_est_celle_du_service_approbation(self):
        from apps.calepinage.services.approbation import CLE_EXIGEE

        self.assertEqual(CLE_APPROBATION_EXIGEE, CLE_EXIGEE)
        self.assertEqual(CLE_APPROBATION_EXIGEE, 'approbation_exigee')

    def test_normaliseur_enregistre_sur_la_section(self):
        self.assertEqual(SECTION, 'presets')
        self.assertIs(_normaliseurs()[SECTION], normaliser_section_presets)

    def test_booleens_et_absence_traversent(self):
        for valeur in ({}, {'approbation_exigee': True},
                       {'approbation_exigee': False},
                       {'approbation_exigee': None}):
            with self.subTest(valeur=valeur):
                self.assertEqual(normaliser_section_presets(dict(valeur)),
                                 valeur)

    def test_autres_cles_intouchees(self):
        section = {'jeux': [{'id': 'j1', 'nom': 'Villa'}],
                   'kits': [{'id': 3}], 'feu_vert_bureau_etudes': True,
                   'villa_standard': {'panneau_w': 580},
                   'approbation_exigee': True}
        self.assertEqual(normaliser_section_presets(dict(section)), section)

    def test_valeur_non_booleenne_refusee_en_nommant_le_champ(self):
        for valeur in ('oui', 1, 0, ['x'], {'a': 1}):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ReglageInvalide) as refus:
                    normaliser_section_presets(
                        {'approbation_exigee': valeur})
                self.assertEqual(refus.exception.champ,
                                 'approbation_exigee')
                self.assertIn('Approbation exigée', str(refus.exception))

    def test_l_exemple_committe_traverse(self):
        publiee = CONTRAT_PARAMETRES['exemple']['presets']
        self.assertEqual(normaliser_section_presets(dict(publiee)), publiee)


class EquivalenceSansReglageTest(SimpleTestCase):
    """Réglage absent ⇒ la décision n'est même pas lue (D12)."""

    def test_aucune_lecture_de_la_decision(self):
        calepinage = faux_calepinage()
        with mock.patch('apps.calepinage.services.approbation.'
                        'approbation_exigee', return_value=False), \
                mock.patch('apps.calepinage.services.approbation.'
                           'est_approuve') as est_approuve, \
                mock.patch.object(feu_vert, 'option_active',
                                  return_value=False), \
                mock.patch('apps.crm.selectors.get_company_lead') as lead:
            self.assertIsNone(feu_vert.verifier_avant_retenue(calepinage))
        est_approuve.assert_not_called()
        lead.assert_not_called()


class RefusApprobationExigeeTest(SimpleTestCase):
    """Réglage actif : non approuvé ⇒ refus nommant le champ et qui décide."""

    def _verifier(self, calepinage, *, roles=('Directeur',)):
        with mock.patch('apps.calepinage.services.approbation.'
                        'approbation_exigee', return_value=True), \
                mock.patch.object(feu_vert, 'option_active',
                                  return_value=False), \
                mock.patch.object(feu_vert, '_roles_approbateurs',
                                  return_value=list(roles)):
            return feu_vert.verifier_avant_retenue(calepinage)

    def test_non_approuve_refuse_sur_le_champ_approbation(self):
        with self.assertRaises(ValidationError) as refus:
            self._verifier(faux_calepinage())
        message = refus.exception.detail['approbation'][0]
        self.assertIn("pas encore été approuvée", message)
        self.assertIn('Directeur', message)

    def test_refus_de_relecture_cite_son_motif(self):
        calepinage = faux_calepinage(
            {'etat': 'refuse', 'motif': 'Retrait de rive'})
        with self.assertRaises(ValidationError) as refus:
            self._verifier(calepinage)
        message = str(refus.exception.detail['approbation'][0])
        self.assertIn('REFUSÉE', message)
        self.assertIn('Retrait de rive', message)

    def test_aucun_role_porteur_le_dit(self):
        with self.assertRaises(ValidationError) as refus:
            self._verifier(faux_calepinage(), roles=())
        self.assertIn('AUCUN rôle',
                      str(refus.exception.detail['approbation'][0]))

    def test_approuve_passe(self):
        calepinage = faux_calepinage({'etat': 'approuve'})
        self.assertIsNone(self._verifier(calepinage))


# ── ORM — la CI est la gate de ces classes ─────────────────────────────────

from apps.calepinage.models import Calepinage, CalepinageVariante  # noqa: E402
from apps.calepinage.services.approbation import decider  # noqa: E402
from apps.calepinage.services.parametres import (  # noqa: E402
    enregistrer_parametres,
)
from apps.calepinage.services.variantes import retenir_variante  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402


def _exiger(company, valeur=True):
    enregistrer_parametres(company, {'presets': {'approbation_exigee': valeur}})


def url_retenir(pk, vid):
    return f'{url_detail(pk)}variantes/{vid}/retenir/'


class RetenirAvecApprobationEnBase(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='V1')

    def test_reglage_absent_retenir_marche_comme_aujourd_hui(self):
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_reglage_eteint_explicitement_equivaut_a_absent(self):
        _exiger(self.company, False)
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_reglage_actif_non_approuve_refuse(self):
        _exiger(self.company)
        with self.assertRaises(ValidationError) as refus:
            retenir_variante(self.variante)
        self.assertIn('approbation', refus.exception.detail)
        self.assertIn('Directeur',
                      str(refus.exception.detail['approbation'][0]))
        self.variante.refresh_from_db()
        self.assertFalse(self.variante.retenue)

    def test_reglage_actif_http_400_par_l_enveloppe_globale(self):
        _exiger(self.company)
        reponse = self.api.post(
            url_retenir(self.calepinage.pk, self.variante.pk), {},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('approbation', json.dumps(reponse.data,
                                                ensure_ascii=False))

    def test_reglage_actif_approuve_retenir_marche(self):
        _exiger(self.company)
        decider(self.calepinage, decision='approuve', user=self.user)
        self.variante.refresh_from_db()
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_valeur_non_booleenne_refusee_a_l_ecriture(self):
        with self.assertRaises(ReglageInvalide) as refus:
            _exiger(self.company, 'oui')
        self.assertEqual(refus.exception.champ, 'approbation_exigee')
