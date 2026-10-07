"""CALX348 — exiger l'approbation (réglage société). DÉCISION FONDATEUR
07/10/2026 : retenir -> approuver -> publier ; la retenue n'exige plus
l'approbation, la porte est la publication (générer / resynchroniser, pièces
d'exécution, ACAL116).

Ce qui est prouvé ici :

* ÉQUIVALENCE (D12) : réglage absent ⇒ ``verifier_avant_publication`` ne lit
  même pas la décision d'approbation, et retenir une variante marche comme
  aujourd'hui sur un calepinage jamais approuvé ;
* la clé ``approbation_exigee`` de la section ``presets`` est VALIDÉE
  booléenne à l'écriture (``services/presets.py``), refus nommant le champ ;
  toutes les autres clés de la section traversent inchangées ;
* réglage actif et calepinage non approuvé => la RETENUE passe ; la
  PUBLICATION (devis / exécution) est refusée par une ``ValidationError`` sur
  le champ ``approbation`` (400 par l'enveloppe globale) ; approuvé et à jour
  => la publication passe ;
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


def faux_calepinage(approbation=None, layout_hash='e' * 64):
    return SimpleNamespace(company=object(), approbation=approbation,
                           lead_id=None, devis=None, layout_hash=layout_hash)


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
            self.assertIsNone(feu_vert.verifier_avant_publication(calepinage))
        est_approuve.assert_not_called()
        lead.assert_not_called()


class RefusApprobationExigeeTest(SimpleTestCase):
    """Réglage actif : la retenue passe ; la publication exige l'accord."""

    def _verifier(self, calepinage, geste=feu_vert.GESTE_DEVIS):
        with mock.patch('apps.calepinage.services.approbation.'
                        'approbation_exigee', return_value=True), \
                mock.patch.object(feu_vert, 'option_active',
                                  return_value=False):
            return feu_vert.verifier_avant_publication(calepinage,
                                                       geste=geste)

    def test_retenue_sans_approbation_passe(self):
        # Décision fondateur 07/10/2026 : la retenue n'exige plus d'accord.
        self.assertIsNone(
            self._verifier(faux_calepinage(), geste=feu_vert.GESTE_RETENUE))

    def test_non_approuve_refuse_la_publication_sur_le_champ_approbation(
            self):
        for geste in (feu_vert.GESTE_DEVIS, feu_vert.GESTE_EXECUTION):
            with self.subTest(geste=geste):
                with self.assertRaises(ValidationError) as refus:
                    self._verifier(faux_calepinage(), geste=geste)
                self.assertIn('Approbation à jour exigée',
                              refus.exception.detail['approbation'][0])

    def test_refuse_en_relecture_refuse_la_publication(self):
        calepinage = faux_calepinage(
            {'etat': 'refuse', 'motif': 'Retrait de rive'})
        with self.assertRaises(ValidationError) as refus:
            self._verifier(calepinage)
        self.assertIn('approbation', refus.exception.detail)

    def test_approuve_passe(self):
        # ACAL114 — l'accord porte l'empreinte imprimée d'aujourd'hui.
        calepinage = faux_calepinage({'etat': 'approuve',
                                      'empreinte_approuvee': 'e' * 64})
        self.assertIsNone(self._verifier(calepinage))

    def test_approuve_mais_perime_refuse(self):
        calepinage = faux_calepinage({'etat': 'approuve',
                                      'empreinte_approuvee': 'a' * 64})
        with self.assertRaises(ValidationError) as refus:
            self._verifier(calepinage)
        self.assertIn('approbation', refus.exception.detail)


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
        # ACAL114 — une conception DESSINÉE (approuvable), la même dans la
        # variante : l'accord porte sur l'empreinte imprimée de la variante.
        from apps.ventes.services import layout_hash

        dessin = {'zones': [{'id': 'z1', 'label': 'Pan Sud',
                             'vertices': [[0, 0], [10, 0], [10, 6]]}]}
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=dessin, layout_hash=layout_hash(dessin) or '')
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='V1',
            roof_layout=dessin)

    def test_reglage_absent_retenir_marche_comme_aujourd_hui(self):
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_reglage_eteint_explicitement_equivaut_a_absent(self):
        _exiger(self.company, False)
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_reglage_actif_non_approuve_retenir_passe_puis_publication_refusee(
            self):
        _exiger(self.company)
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)
        self.calepinage.refresh_from_db()
        for geste in (feu_vert.GESTE_DEVIS, feu_vert.GESTE_EXECUTION):
            with self.subTest(geste=geste):
                with self.assertRaises(ValidationError) as refus:
                    feu_vert.verifier_avant_publication(
                        self.calepinage, geste=geste)
                self.assertIn('approbation', refus.exception.detail)

    def test_reglage_actif_http_retenir_200_puis_publication_400(self):
        _exiger(self.company)
        reponse = self.api.post(
            url_retenir(self.calepinage.pk, self.variante.pk), {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        with self.assertRaises(ValidationError) as refus:
            feu_vert.verifier_avant_publication(
                self.calepinage, geste=feu_vert.GESTE_DEVIS)
        self.assertIn('approbation', refus.exception.detail)

    def test_reglage_actif_approuve_puis_publication_passe(self):
        _exiger(self.company)
        retenir_variante(self.variante)
        decider(self.calepinage, decision='approuve', user=self.user)
        self.calepinage.refresh_from_db()
        self.assertIsNone(feu_vert.verifier_avant_publication(
            self.calepinage, geste=feu_vert.GESTE_DEVIS))

    def test_valeur_non_booleenne_refusee_a_l_ecriture(self):
        with self.assertRaises(ReglageInvalide) as refus:
            _exiger(self.company, 'oui')
        self.assertEqual(refus.exception.champ, 'approbation_exigee')
