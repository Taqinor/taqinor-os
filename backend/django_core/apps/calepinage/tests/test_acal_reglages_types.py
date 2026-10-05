"""ACAL132 — réglages de simulation TYPÉS, refus nommé, PUT qui FUSIONNE.

Constats C-ACAL-067 / C-ACAL-068 (audit 2026-10-04) : le registre des
réglages de simulation ne disait pas le TYPE d'une valeur — « 2,5 » ou « abc »
étaient stockés tels quels, puis l'étape qui les lisait basculait en silence
sur un repli (``etapes/iam.py`` : b0 illisible ⇒ Fresnel) ; et un PUT d'une
seule clé REMPLAÇAIT toute la section (``setattr``), effaçant ``mode_meteo``
quand l'API n'envoyait que ``fenetre_annees`` (LIVEX-18, D-ACAL-8).

Ce qui est tenu ici, sur la source réelle (``enregistrer_parametres`` et la
route ``PUT /api/django/calepinage/parametres/``), sans aucun mock :
  * « 2,5 » est normalisé en 2.5 ; « abc » / nan / inf / hors bornes / mot
    hors liste ⇒ 400 qui nomme la clé DANS sa section, rien n'est écrit ;
  * le PUT d'une clé CONSERVE les autres clés de la section ; ``null`` RETIRE ;
  * PUT → GET → PUT sans changement ⇒ ligne octet-identique ;
  * le registre servi porte le type de chaque clé.

Run :
    python manage.py test apps.calepinage.tests.test_acal_reglages_types -v2
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import registre_des_reglages
from apps.calepinage.services.parametres import (
    ReglageInvalide,
    _normaliser_section_simulation,
    enregistrer_parametres,
)
from apps.calepinage.services.parametres_cles import (
    REGISTRES,
    TYPES_CLES,
    registre,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL = '/api/django/calepinage/parametres/'


def _saisie(valeur, source='saisie'):
    return {'valeur': valeur, 'source': source}


class TypesDeclaresTest(SimpleTestCase):
    """Chaque clé du registre a UN type — aucune clé ne passe sans."""

    def test_chaque_cle_du_registre_a_un_type(self):
        total = 0
        for section in REGISTRES:
            for cle in registre(section):
                total += 1
                with self.subTest(section=section, cle=cle):
                    self.assertIn(cle, TYPES_CLES.get(section, {}))
                    self.assertTrue(TYPES_CLES[section][cle].get('type'))
        self.assertEqual(total, 37)  # 28 simulation + 9 electrique_societe

    def test_aucun_type_pour_une_cle_hors_registre(self):
        for section, types in TYPES_CLES.items():
            self.assertEqual(sorted(set(types) - set(registre(section))), [])


class NormalisationParTypeTest(SimpleTestCase):
    """Le normaliseur PUR — la règle de chaque type, refus nommé."""

    def test_virgule_decimale_normalisee(self):
        rendu = _normaliser_section_simulation({
            'sigma_modele_pct': _saisie('2,5'),
            'b0_iam': _saisie('0,05', 'texte'),
        })
        self.assertEqual(rendu['sigma_modele_pct']['valeur'], 2.5)
        self.assertIsInstance(rendu['sigma_modele_pct']['valeur'], float)
        self.assertEqual(rendu['b0_iam']['valeur'], 0.05)

    def test_valeur_illisible_refusee_en_nommant_la_cle_et_sa_section(self):
        for valeur in ('abc', 'nan', 'inf', '1e400', True, [1, 2]):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ReglageInvalide) as refus:
                    _normaliser_section_simulation(
                        {'sigma_modele_pct': _saisie(valeur)})
                self.assertEqual(refus.exception.champ, 'sigma_modele_pct')
                self.assertEqual(refus.exception.section, 'simulation')
                self.assertIn('sigma_modele_pct', str(refus.exception))

    def test_hors_bornes_et_hors_liste_refuses(self):
        cas = (
            ('sigma_modele_pct', 150),
            ('sigma_modele_pct', -1),
            ('mode_meteo', 'annuel'),
            ('modele_iam', 'inconnu'),
            ('resolution_minutes', 0),
            ('resolution_minutes', 7.5),
            ('fenetre_annees', '2024-2015'),
            ('albedo_mensuel', [0.2] * 11),
        )
        for cle, valeur in cas:
            with self.subTest(cle=cle, valeur=valeur):
                with self.assertRaises(ReglageInvalide) as refus:
                    _normaliser_section_simulation({cle: _saisie(valeur)})
                self.assertEqual(refus.exception.champ, cle)

    def test_formes_admises_normalisees(self):
        rendu = _normaliser_section_simulation({
            'mode_meteo': _saisie('  TMY ', 'societe'),
            'resolution_minutes': _saisie('60', 'texte'),
            'fenetre_annees': _saisie('2015-2024', 'societe'),
            'salissure_mensuelle_pct': _saisie('2,0', 'mesure'),
            'attenuation_horizon': _saisie('aucune', 'societe'),
            'thermique_par_pose': _saisie({'flush': {'uc_w_m2k': 20.0}},
                                          'mesure'),
        })
        self.assertEqual(rendu['mode_meteo']['valeur'], 'tmy')
        self.assertEqual(rendu['resolution_minutes']['valeur'], 60)
        self.assertEqual(rendu['fenetre_annees']['valeur'], [2015, 2024])
        self.assertEqual(rendu['salissure_mensuelle_pct']['valeur'], 2.0)
        self.assertIs(rendu['attenuation_horizon']['valeur'], False)
        self.assertEqual(rendu['thermique_par_pose']['valeur'],
                         {'flush': {'uc_w_m2k': 20.0}})

    def test_normalisation_idempotente(self):
        une_fois = _normaliser_section_simulation({
            'sigma_modele_pct': _saisie('2,5'),
            'fenetre_annees': _saisie('2015-2024', 'societe'),
        })
        self.assertEqual(_normaliser_section_simulation(une_fois), une_fois)


class EcritureFusionneeTest(TestCase):
    """``enregistrer_parametres`` — fusion par clé, null retire, rien
    d'écrit sur un refus."""

    def setUp(self):
        self.company = Company.objects.create(nom='Types Co',
                                              slug='acal132-types')

    def _section(self, nom='simulation'):
        return getattr(ParametresCalepinage.objects.get(company=self.company),
                       nom)

    def test_put_fusionne_la_section(self):
        enregistrer_parametres(self.company, {'simulation': {
            'mode_meteo': _saisie('pluriannuel', 'societe'),
            'fenetre_annees': _saisie('2015-2024', 'societe'),
        }})
        enregistrer_parametres(self.company, {'simulation': {
            'fenetre_annees': _saisie([2016, 2024], 'societe'),
        }})
        section = self._section()
        self.assertEqual(section['mode_meteo']['valeur'], 'pluriannuel')
        self.assertEqual(section['fenetre_annees']['valeur'], [2016, 2024])

    def test_cle_null_retiree(self):
        enregistrer_parametres(self.company, {'simulation': {
            'mode_meteo': _saisie('tmy', 'societe'),
            'sigma_modele_pct': _saisie(4.0),
        }})
        enregistrer_parametres(self.company,
                               {'simulation': {'sigma_modele_pct': None}})
        self.assertEqual(sorted(self._section()), ['mode_meteo'])

    def test_refus_n_ecrit_rien(self):
        enregistrer_parametres(self.company, {'simulation': {
            'mode_meteo': _saisie('tmy', 'societe')}})
        avant = self._section()
        with self.assertRaises(ReglageInvalide):
            enregistrer_parametres(self.company, {'simulation': {
                'mode_meteo': None,
                'sigma_modele_pct': _saisie('abc')}})
        self.assertEqual(self._section(), avant)

    def test_remplacer_garde_sa_semantique(self):
        enregistrer_parametres(self.company, {'simulation': {
            'mode_meteo': _saisie('tmy', 'societe'),
            'sigma_modele_pct': _saisie(4.0)}})
        enregistrer_parametres(
            self.company,
            {'simulation': {'sigma_modele_pct': _saisie(3.0)}},
            remplacer=True)
        self.assertEqual(sorted(self._section()), ['sigma_modele_pct'])


class RouteParametresTest(TestCase):
    """La route réelle : 400 nommé, fusion, aller-retour octet-identique."""

    def setUp(self):
        self.company = Company.objects.create(nom='Route Co',
                                              slug='acal132-route')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(
            username='acal132_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def _ligne(self):
        reglages = ParametresCalepinage.objects.get(company=self.company)
        return {section: getattr(reglages, section)
                for section in ParametresCalepinage.SECTIONS}

    def test_virgule_decimale_normalisee(self):
        reponse = self.api.put(URL, {'simulation': {
            'sigma_modele_pct': _saisie('2,5')}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            reponse.data['simulation']['sigma_modele_pct']['valeur'], 2.5)
        self.assertEqual(
            self._ligne()['simulation']['sigma_modele_pct']['valeur'], 2.5)

    def test_valeur_illisible_400_nommee(self):
        reponse = self.api.put(URL, {'simulation': {
            'sigma_modele_pct': _saisie('abc')}}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('sigma_modele_pct', reponse.data['simulation'])
        self.assertFalse(
            ParametresCalepinage.objects.filter(company=self.company).exists())

    def test_put_fusionne_la_section(self):
        self.api.put(URL, {'simulation': {
            'mode_meteo': _saisie('pluriannuel', 'societe'),
            'fenetre_annees': _saisie('2015-2024', 'societe')}},
            format='json')
        reponse = self.api.put(URL, {'simulation': {
            'fenetre_annees': _saisie('2017-2024', 'societe')}},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            reponse.data['simulation']['mode_meteo']['valeur'], 'pluriannuel')

    def test_cle_null_retiree(self):
        self.api.put(URL, {'simulation': {
            'mode_meteo': _saisie('tmy', 'societe'),
            'tolerance_validation_pct': _saisie(5)}}, format='json')
        reponse = self.api.put(URL, {'simulation': {
            'tolerance_validation_pct': None}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertNotIn('tolerance_validation_pct', reponse.data['simulation'])
        self.assertIn('mode_meteo', reponse.data['simulation'])

    def test_aller_retour_octet_identique(self):
        self.api.put(URL, {'simulation': {
            'sigma_modele_pct': _saisie('2,5'),
            'mode_meteo': _saisie('tmy', 'societe')}}, format='json')
        apres_premier = self._ligne()
        lu = self.api.get(URL).data
        reponse = self.api.put(URL, {'simulation': lu['simulation']},
                               format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._ligne(), apres_premier)

    def test_registre_servi_porte_le_type(self):
        servi = self.api.get(URL).data['registre']
        self.assertEqual(servi, registre_des_reglages())
        par_cle = {ligne['cle']: ligne for ligne in servi['simulation']}
        self.assertEqual(par_cle['sigma_modele_pct']['type'], 'pourcentage')
        self.assertEqual(par_cle['sigma_modele_pct']['maximum'], 100)
        self.assertEqual(par_cle['mode_meteo']['valeurs'],
                         ['tmy', 'pluriannuel'])
