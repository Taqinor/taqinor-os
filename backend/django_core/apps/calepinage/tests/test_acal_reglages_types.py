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

    def test_put_multipart_refuse_415(self):
        # Fuzz CI #997 : un multipart ne porte que des chaînes → « doit être
        # un objet (reçu : str) » ; le PUT ne publie/accepte plus que du JSON.
        reponse = self.api.put(URL, {'imagerie': '{}'}, format='multipart')
        self.assertEqual(reponse.status_code, 415, reponse.data)

    def test_caractere_nul_400_nomme_jamais_500(self):
        # CI #997 api-fuzz (3) : une ``reference`` portant U+0000 passait la
        # normalisation puis cassait l'INSERT JSONB (500) ; le schéma publie
        # déjà « sans caractère nul » → 400 qui NOMME le chemin, rien d'écrit.
        reponse = self.api.put(URL, {'electrique_societe': {
            'seuil_bas_dc_ac': {'valeur': 1.1, 'source': 'societe',
                                'reference': 'norme\x00'}}}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('seuil_bas_dc_ac.reference',
                      reponse.data['electrique_societe'])
        # Une section à objet libre et une clé d'objet sont couvertes aussi.
        autre = self.api.put(URL, {'presets': {'a\x00': 1}}, format='json')
        self.assertEqual(autre.status_code, 400, autre.content)
        self.assertIn('presets', autre.data)
        self.assertFalse(
            ParametresCalepinage.objects.filter(company=self.company).exists())


class CaractereInterditTest(SimpleTestCase):
    """CI #997 api-fuzz (3) — le chemin du premier texte que JSONB refuse."""

    def test_nul_et_demi_substitut_isole_nommes_le_reste_passe(self):
        from apps.calepinage.services.parametres import (
            _chemin_caractere_interdit as chemin,
        )

        self.assertEqual(chemin({'a': ['ok', 'b\x00']}, 's'), 's.a[1]')
        self.assertEqual(chemin({'a\x00': 1}, 's'), 's (clé)')
        self.assertEqual(chemin({'a': chr(0xD800)}, 's'), 's.a')
        self.assertIsNone(chemin({'a': 'é😀', 'b': [1, None, 2.5]}, 's'))


class FormeRequetePartielleTest(SimpleTestCase):
    """CI #997 fuzz — le PUT est partiel : aucune section n'est obligatoire
    dans le schéma de requête (les écrans n'en envoient qu'une)."""

    def test_sections_facultatives_en_requete_obligatoires_en_reponse(self):
        from apps.calepinage.views.parametres import _forme_reglages

        requete = _forme_reglages('X', partielle=True).fields
        reponse = _forme_reglages('Y').fields
        self.assertTrue(requete)
        self.assertFalse(any(c.required for c in requete.values()))
        self.assertTrue(all(c.required for c in reponse.values()))


class SectionsResserreesRequeteTest(SimpleTestCase):
    """CI #997 fuzz (2) — le schéma du PUT ne promet que ce que le serveur
    accepte : une clé de plus (``x-schemathesis-additional``) dans une section
    à vocabulaire fermé était « conforme » puis refusée 400."""

    @staticmethod
    def _valeurs(schema):
        if 'anyOf' in schema:
            return [v for s in schema['anyOf'] for v in
                    SectionsResserreesRequeteTest._valeurs(s)]
        genre = schema['type']
        if genre == 'string':
            return list(schema['enum'])
        if genre == 'boolean':
            return [True, False]
        if genre in ('number', 'integer'):
            bornes = [schema.get('minimum', 0)]
            if 'maximum' in schema:
                bornes.append(schema['maximum'])
            return bornes
        return [SectionsResserreesRequeteTest._instance(schema)]

    @staticmethod
    def _instance(schema):
        """Une valeur MINIMALE conforme à ``schema`` (tables structurées)."""
        faire = SectionsResserreesRequeteTest._instance
        if 'anyOf' in schema:
            return faire(schema['anyOf'][0])
        genre = schema['type']
        if genre == 'string':
            return 'x'
        if genre in ('number', 'integer'):
            return schema.get('minimum', 0)
        if genre == 'array':
            return [faire(schema['items'])]
        proprietes = schema.get('properties', {})
        rendu = {nom: faire(proprietes[nom])
                 for nom in schema.get('required', ())}
        if not rendu and schema.get('minProperties'):
            rendu = {'x': faire(schema['additionalProperties'])}
        return rendu

    def test_sections_a_registre_publiees_cle_par_cle_et_acceptees(self):
        from apps.calepinage.services.parametres import (
            _normaliser_section_a_registre,
        )
        from apps.calepinage.views.parametres import (
            _sections_requete_resserrees,
        )

        champs = _sections_requete_resserrees()
        refus = []
        for section in REGISTRES:
            schema = champs[section]._spectacular_annotation['field']
            self.assertIs(schema['additionalProperties'], False)
            self.assertEqual(set(schema['properties']),
                             set(registre(section)), section)
            for cle, entree in schema['properties'].items():
                for valeur in self._valeurs(entree['properties']['valeur']):
                    try:
                        _normaliser_section_a_registre(
                            section, {cle: {'valeur': valeur,
                                            'source': 'societe',
                                            'reference': ''}})
                    except ReglageInvalide as erreur:
                        refus.append((section, cle, valeur, str(erreur)))
        self.assertEqual(refus, [])

    def test_sections_a_vocabulaire_ferme_refusent_toute_cle_de_plus(self):
        from apps.calepinage.services.parametres import _normaliseurs
        from apps.calepinage.views.parametres import (
            _SECTIONS_A_VOCABULAIRE_FERME, _sections_requete_resserrees,
        )

        champs = _sections_requete_resserrees()
        acceptees = []
        for section in _SECTIONS_A_VOCABULAIRE_FERME:
            schema = champs[section]._spectacular_annotation['field']
            self.assertIs(schema['additionalProperties'], False)
            try:
                _normaliseurs()[section]({'x-schemathesis-additional': {}})
                acceptees.append(section)
            except ReglageInvalide:
                pass
        self.assertEqual(acceptees, [])


class FormeDesTablesTest(SimpleTestCase):
    """CI #997 fuzz — ``PUT parametres/`` acceptait (200) une ``valeur`` de
    table dont les items n'étaient pas du type publié
    (``electrique_societe.regle_bom_structure.valeur`` = liste d'items du
    mauvais type). Chaque clé ``table`` a désormais SA forme, lue par le
    validateur d'écriture ET publiée dans le contrat : ce que le contrat
    refuse, le serveur le refuse en nommant le chemin fautif."""

    @staticmethod
    def _tables():
        return [(section, cle) for section, types in TYPES_CLES.items()
                for cle, declaration in types.items()
                if declaration['type'] == 'table']

    @staticmethod
    def _ecrire(section, cle, valeur):
        from apps.calepinage.services.parametres import (
            _normaliser_section_a_registre,
        )

        return _normaliser_section_a_registre(section, {cle: {
            'valeur': valeur, 'source': 'societe', 'reference': ''}})

    def test_chaque_cle_table_declare_sa_forme_et_la_publie(self):
        from apps.calepinage.services.parametres_cles import (
            FORMES_TABLES, forme_de_table,
        )
        from apps.calepinage.views.parametres import (
            _sections_requete_resserrees,
        )

        tables = self._tables()
        self.assertEqual(len(tables), 5)
        champs = _sections_requete_resserrees()
        ecarts = []
        for section, cle in tables:
            forme = forme_de_table(section, cle)
            publie = champs[section]._spectacular_annotation['field'][
                'properties'][cle]['properties']['valeur']
            if (not forme or publie.get('type') != forme.get('type')
                    or publie.get('required') != forme.get('required')):
                ecarts.append((section, cle))
        self.assertEqual(ecarts, [])
        declarees = {(s, c) for s, formes in FORMES_TABLES.items()
                     for c in formes}
        self.assertEqual(declarees, set(tables))

    def test_la_forme_minimale_conforme_est_acceptee_telle_quelle(self):
        from apps.calepinage.services.parametres_cles import forme_de_table

        ecarts = []
        for section, cle in self._tables():
            valeur = SectionsResserreesRequeteTest._instance(
                forme_de_table(section, cle))
            rendu = self._ecrire(section, cle, valeur)
            if rendu[cle]['valeur'] != valeur:
                ecarts.append((section, cle))
        self.assertEqual(ecarts, [])

    def test_les_vraies_saisies_des_etapes_restent_acceptees(self):
        regle = {'rails_par_module': 2.0, 'pinces_par_module': 2.0,
                 'pinces_supplement': 4.0, 'crochets_par_module': 0.6,
                 'crochets_minimum': 4.0, 'source': 'Cahier de pose K2'}
        pose = {'flush': {'uc_w_m2k': 20.0, 'uv_w_m3sk': 0.0,
                          'source': 'mesure', 'reference': 'essai'}}
        saisies = (
            ('electrique_societe', 'regle_bom_structure', regle),
            ('electrique_societe', 'correspondances_nomenclature',
             {'coffret_dc': 12, 'onduleur': 'REF-9'}),
            ('simulation', 'thermique_par_pose', pose),
            ('simulation', 'lid_par_techno',
             {'PERC': {'pct': 2.0, 'source': 'fiche', 'reference': ''}}),
            ('simulation', 'indisponibilite_fenetres',
             [{'debut': '2026-06-01', 'fin': '2026-06-08', 'motif': 'x'}]),
        )
        ecarts = [cle for section, cle, valeur in saisies
                  if self._ecrire(section, cle, valeur)[cle]['valeur']
                  != valeur]
        self.assertEqual(ecarts, [])

    def test_items_du_mauvais_type_refuses_en_nommant_le_chemin(self):
        refuses = (
            ('electrique_societe', 'regle_bom_structure', ['x'], 'objet'),
            ('electrique_societe', 'regle_bom_structure', [1.5], 'objet'),
            ('electrique_societe', 'regle_bom_structure',
             {'rails_par_module': 'deux'}, 'rails_par_module'),
            ('electrique_societe', 'regle_bom_structure',
             {'rails_par_module': 1.0}, 'pinces_par_module'),
            ('electrique_societe', 'correspondances_nomenclature',
             {'coffret_dc': 1.5}, 'coffret_dc'),
            ('electrique_societe', 'correspondances_nomenclature',
             ['a'], 'objet'),
            ('simulation', 'thermique_par_pose',
             {'flush': {'uc_w_m2k': True, 'source': 's'}}, 'uc_w_m2k'),
            ('simulation', 'thermique_par_pose', [1.0], 'objet'),
            ('simulation', 'lid_par_techno',
             {'PERC': {'pct': 120, 'source': 's'}}, 'hors bornes'),
            ('simulation', 'lid_par_techno', {'PERC': 2.0}, 'PERC'),
            ('simulation', 'lid_par_techno',
             {'PERC': {'source': 's'}}, 'obligatoire'),
            ('simulation', 'indisponibilite_fenetres', [0.0], '[0]'),
            ('simulation', 'indisponibilite_fenetres',
             [{'debut': 5, 'fin': '2026-06-08'}], 'debut'),
            ('simulation', 'indisponibilite_fenetres',
             {'debut': '2026-06-01'}, 'liste'),
        )
        ecarts = []
        for section, cle, valeur, mot in refuses:
            try:
                self._ecrire(section, cle, valeur)
            except ReglageInvalide as refus:
                if (cle not in str(refus) or mot not in str(refus)
                        or refus.champ != cle):
                    ecarts.append((cle, valeur, str(refus)))
            else:
                ecarts.append((cle, valeur, 'ACCEPTÉ'))
        self.assertEqual(ecarts, [])
