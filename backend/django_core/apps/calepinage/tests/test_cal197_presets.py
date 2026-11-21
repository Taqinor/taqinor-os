"""CAL197 — presets société de calepinage : réutilisés, jamais réinventés.

Ce qui est prouvé ici :

* les jeux MAISON se posent par l'UNIQUE chemin d'écriture du domaine
  (``enregistrer_parametres``, section ``presets``, clé ``jeux``) et se
  relisent par ``jeux_de_societe`` — ENF18 : les jumeaux
  ``enregistrer_jeu`` / ``retirer_jeu``, sans appelant de production, sont
  retirés ;
* les presets d'une société n'apparaissent JAMAIS dans une autre (multi-
  société) ;
* ``selectors.presets_de_societe`` publie les jeux MAISON (SOLMVP15 : la
  seconde source, les presets de portée société du module d'appels d'offres,
  sort du produit avec sa table — aucun jeu maison n'a bougé) ;
* renvoyer la section ``presets`` ENTIÈRE (comme le fait l'écran
  Bibliothèque) en changeant ``jeux`` NE TOUCHE PAS le catalogue de kits de
  pose, qui vit dans la même section (SOLMVP15).

Run :
    python manage.py test apps.calepinage.tests.test_cal197_presets -v2
"""
from django.test import SimpleTestCase, TestCase

from apps.calepinage import selectors
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.presets import jeux_de_societe
from authentication.models import Company


def _poser_jeux(company, jeux):
    """Le geste de l'écran : la section ``presets`` renvoyée en entier."""
    section = dict(selectors.parametres_de_societe(company).get('presets')
                   or {})
    section['jeux'] = jeux
    return enregistrer_parametres(company, {'presets': section})


class JeuxMaisonTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Presets Co',
                                              slug='presets-co-197')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-197')

    def test_societe_sans_reglage_recoit_liste_vide(self):
        self.assertEqual(jeux_de_societe(self.company), [])

    def test_poser_puis_lire(self):
        _poser_jeux(self.company, [{
            'id': 'standard', 'nom': 'Standard',
            'marge_toiture_m': 0.3, 'espacement_rangee_m': 0.02,
        }])
        jeux = jeux_de_societe(self.company)
        self.assertEqual(len(jeux), 1)
        self.assertEqual(jeux[0]['nom'], 'Standard')
        self.assertEqual(jeux[0]['marge_toiture_m'], 0.3)

    def test_renvoyer_la_liste_remplace_les_jeux(self):
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard',
                                    'marge_toiture_m': 0.3}])
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard v2',
                                    'marge_toiture_m': 0.5}])
        jeux = jeux_de_societe(self.company)
        self.assertEqual(len(jeux), 1)
        self.assertEqual(jeux[0]['nom'], 'Standard v2')
        self.assertEqual(jeux[0]['marge_toiture_m'], 0.5)

    def test_retirer_un_jeu_c_est_renvoyer_la_liste_sans_lui(self):
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard'}])
        _poser_jeux(self.company, [])
        self.assertEqual(jeux_de_societe(self.company), [])

    def test_isolation_multi_societe(self):
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard'}])
        self.assertEqual(jeux_de_societe(self.autre), [])


class PresetsDeSocieteSelectorTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Presets Sel Co',
                                              slug='presets-sel-co-197')

    def test_publie_les_jeux_maison(self):
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard'}])

        resultat = selectors.presets_de_societe(self.company)

        self.assertEqual(len(resultat['module']), 1)
        self.assertEqual(resultat['module'][0]['id'], 'std')
        self.assertEqual(resultat['module'][0]['nom'], 'Standard')

    def test_societe_none_rend_une_liste_vide(self):
        resultat = selectors.presets_de_societe(None)
        self.assertEqual(resultat['module'], [])

    def test_ecrire_un_jeu_ne_touche_pas_le_catalogue_de_kits(self):
        """SOLMVP15 — les deux vivent dans la section ``presets`` : un
        écrivain de l'une ne doit JAMAIS effacer l'autre (la section est
        remplacée en bloc par ``enregistrer_parametres`` : l'écrivain renvoie
        donc la section entière)."""
        from apps.calepinage.services.kits_catalogue import kits_de_societe

        enregistrer_parametres(self.company, {'presets': {'kits': [
            {'id': 7, 'code': 'K7', 'libelle': 'Kit 7', 'actif': True},
        ]}})
        _poser_jeux(self.company, [{'id': 'std', 'nom': 'Standard'}])

        self.assertEqual([k['code'] for k in
                          kits_de_societe(self.company)], ['K7'])
        self.assertEqual(len(jeux_de_societe(self.company)), 1)

        _poser_jeux(self.company, [])
        self.assertEqual([k['code'] for k in
                          kits_de_societe(self.company)], ['K7'])


class ChampsDePresetTest(SimpleTestCase):
    """ACAL961 — les champs admis d'un préréglage, bâtis depuis ``REGLAGES``."""

    def test_une_ligne_par_reglage_hors_libelle_rives_priorite(self):
        from apps.calepinage.services.gabarits import REGLAGES
        from apps.calepinage.services.presets import champs_de_preset

        attendues = [cle for cle, _ in REGLAGES
                     if cle not in ('libelle', 'rives', 'priorite')]
        lignes = champs_de_preset()
        self.assertEqual([ligne['cle'] for ligne in lignes], attendues)
        for ligne in lignes:
            self.assertEqual(
                set(ligne), {'cle', 'libelle', 'type', 'unite', 'valeurs'})

    def test_unites_types_et_valeurs(self):
        from apps.calepinage.services.gabarits import (
            FAMILLES, ORIENTATIONS, TYPES_TOITURE,
        )
        from apps.calepinage.services.presets import champs_de_preset

        par_cle = {ligne['cle']: ligne for ligne in champs_de_preset()}
        self.assertEqual(par_cle['allee_m']['unite'], 'm')
        self.assertEqual(par_cle['pitchDeg']['unite'], '°')
        self.assertEqual(par_cle['chassis_sous_pente_deg']['unite'], '°')
        self.assertIsNone(par_cle['rangees']['unite'])
        self.assertEqual(par_cle['rangees']['type'], 'entier')
        self.assertEqual(par_cle['neededAuto']['type'], 'booleen')
        self.assertEqual(par_cle['pitchDeg']['type'], 'nombre')
        self.assertEqual(par_cle['orientation']['valeurs'],
                         list(ORIENTATIONS))
        self.assertEqual(par_cle['famille']['valeurs'], list(FAMILLES))
        self.assertEqual(par_cle['roofType']['valeurs'], list(TYPES_TOITURE))
        self.assertIsNone(par_cle['allee_m']['valeurs'])

    def test_retirer_une_cle_de_reglages_retire_la_ligne(self):
        """Mutant : la liste suit ``REGLAGES``, elle n'en copie rien."""
        from unittest import mock

        from apps.calepinage.services import gabarits
        from apps.calepinage.services.presets import champs_de_preset

        reduit = tuple(c for c in gabarits.REGLAGES if c[0] != 'allee_m')
        with mock.patch.object(gabarits, 'REGLAGES', reduit):
            self.assertNotIn('allee_m',
                             [ligne['cle'] for ligne in champs_de_preset()])

    def test_le_contrat_publie_la_meme_liste(self):
        import json
        import pathlib

        from apps.calepinage.services.presets import champs_de_preset

        racine = pathlib.Path(__file__).resolve().parent.parent
        contrat = json.loads((racine / 'contract_samples'
                              / 'parametres_calepinage.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(contrat['exemple']['champs_preset'],
                         champs_de_preset())
        self.assertEqual(contrat['exemple_vide']['champs_preset'],
                         champs_de_preset())
