"""CAL233 — la structure du module est posée UNE fois, et elle tient.

Deux garanties, prouvées sans base de données :

1. ``apps/calepinage/services`` et ``apps/calepinage/views`` sont des PAQUETS
   (jamais des modules ``services.py`` / ``views.py``). Les deux formes ne
   peuvent pas coexister en Python : si une lane repose un module plat, ce
   test rougit AVANT que la collision n'arrive en fusion.

2. Le module n'expose QUE DEUX formes d'URL :
   ``/api/django/calepinage/calepinages/<pk>/…`` (sous-ressources en
   ``@action`` du routeur DRF) et ``/api/django/calepinage/parametres/``.
   Deux familles d'URL pour un même objet, c'est l'incident PACT10 par
   construction (écran « AO — Tableau de bord », 03/08/2026) : ce test
   échoue si une URL du module sort de ces deux formes.

Run :
    python manage.py test apps.calepinage.tests.test_structure_urls -v2
"""
import pathlib

from django.test import SimpleTestCase

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

#: Motifs engendrés par ``DefaultRouter`` à la racine (api-root + suffixe de
#: format) : ils ne portent aucune ressource, donc ils sont hors contrat.
#: CAL16 — la troisième forme (``<drf_format_suffix:format>``) est celle que
#: DRF engendre RÉELLEMENT pour l'api-root dès qu'un viewset est enregistré :
#: elle est apparue au premier ``router.register`` (le routeur était vide quand
#: cette liste a été écrite). C'est la même route sans ressource que les deux
#: autres — jamais une seconde famille d'URL.
_RACINE_ROUTEUR = ('', r'\.(?P<format>[a-z0-9]+)/?',
                   '<drf_format_suffix:format>')


def _routes(patterns, prefixe=''):
    """Aplatit un ``urlpatterns`` en la liste des routes complètes."""
    routes = []
    for motif in patterns:
        chemin = prefixe + str(motif.pattern)
        enfants = getattr(motif, 'url_patterns', None)
        if enfants is not None:
            routes.extend(_routes(enfants, chemin))
        else:
            routes.append(chemin)
    return routes


class StructurePaquetsTest(SimpleTestCase):
    """``services/`` et ``views/`` sont des paquets, pas des modules plats."""

    def test_services_est_un_paquet(self):
        self.assertTrue((RACINE_APP / 'services' / '__init__.py').is_file())
        self.assertFalse(
            (RACINE_APP / 'services.py').exists(),
            "apps/calepinage/services.py réapparu : il ne peut pas coexister "
            "avec le paquet services/ (CAL233).")

    def test_views_est_un_paquet(self):
        self.assertTrue((RACINE_APP / 'views' / '__init__.py').is_file())
        self.assertFalse(
            (RACINE_APP / 'views.py').exists(),
            "apps/calepinage/views.py réapparu : il ne peut pas coexister "
            "avec le paquet views/ (CAL233).")

    def test_pas_de_viewsets_plat(self):
        """Un second foyer de vues (``viewsets.py``) rouvrirait l'ambiguïté."""
        self.assertFalse(
            (RACINE_APP / 'viewsets.py').exists(),
            "apps/calepinage/viewsets.py : les vues du module vivent dans le "
            "paquet views/ (CAL233), nulle part ailleurs.")

    def test_reexport_nomme_le_sous_module_manquant(self):
        """Un nom inconnu échoue en NOMMANT les sous-modules connus."""
        from apps.calepinage import services

        with self.assertRaises(AttributeError) as capture:
            services.fonction_qui_nexiste_pas
        self.assertIn('creation', str(capture.exception))


class FormeUrlUniqueTest(SimpleTestCase):
    """Toute URL du module tient dans les DEUX formes admises."""

    def test_deux_formes_seulement(self):
        from apps.calepinage import urls
        from apps.calepinage.views import PREFIXES_URL_AUTORISES

        hors_contrat = []
        for route in _routes(urls.urlpatterns):
            if route in _RACINE_ROUTEUR:
                continue
            premier = route.lstrip('^').split('/', 1)[0]
            if premier not in PREFIXES_URL_AUTORISES:
                hors_contrat.append(route)

        self.assertEqual(
            hors_contrat, [],
            "URL(s) hors des deux formes admises "
            f"({' / '.join(PREFIXES_URL_AUTORISES)}) : {hors_contrat}. "
            "Une sous-ressource s'expose en @action du viewset pivot, jamais "
            "en nouvelle famille d'URL (CAL233).")

    def test_les_prefixes_sont_les_bons(self):
        """L'objet métier a UNE forme d'URL ; le moteur n'est pas l'objet.

        CAL22 — ``moteur`` rejoint la liste : c'est un CALCUL SANS ÉTAT (sans
        identifiant, n'appartenant à aucun calepinage), dont le chemin est figé
        depuis le jour 1 par ``contract_samples/moteur_calculer.json``. La
        règle protège le calepinage lui-même, qui reste servi sous
        ``calepinages/<pk>/…`` et nulle part ailleurs.
        """
        from apps.calepinage.views import PREFIXES_URL_AUTORISES

        # ACAL238 — ``gabarits-dossiers`` : réglage société (contrat ACAL15).
        self.assertEqual(PREFIXES_URL_AUTORISES,
                         ('calepinages', 'moteur', 'parametres',
                          'gabarits-dossiers'))
        self.assertNotIn(
            'calepinage', PREFIXES_URL_AUTORISES,
            "Aucun second préfixe ne doit servir l'objet métier lui-même.")


class SchemaOpenApiDuModuleTest(SimpleTestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE — le schéma publié DIT ce que le module sert.

    Sans ``@extend_schema``, drf-spectacular publie le ``Calepinage`` du
    viewset comme requête ET réponse de TOUTE ``@action`` : un schéma qui ment
    (60 « réponses hors schéma » à l'api-fuzz du 11/10/2026).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        generateur = SchemaGenerator(patterns=[
            path('api/django/calepinage/', include('apps.calepinage.urls'))])
        cls.schema = generateur.get_schema(request=None, public=True)

    def _refs(self, noeud):
        import json

        return json.dumps(noeud, sort_keys=True)

    def test_aucune_operation_ne_publie_le_serialiseur_du_pivot_en_reponse(self):
        fautives = []
        for chemin, item in self.schema['paths'].items():
            for methode, operation in item.items():
                if methode not in ('get', 'post', 'patch', 'put', 'delete'):
                    continue
                for code, reponse in operation.get('responses', {}).items():
                    if code[0] != '2':
                        continue
                    if '#/components/schemas/Calepinage"' in self._refs(
                            reponse):
                        fautives.append(f'{methode.upper()} {chemin}')
        self.assertEqual(
            fautives, [],
            "Ces opérations publient le serialiseur « Calepinage » (écriture) "
            "comme réponse : déclarer @extend_schema(responses=…) à côté de "
            f"l'@action (forme_reponse / forme_du_contrat) : {fautives}")

    def test_aucune_action_ne_demande_le_corps_du_pivot_par_defaut(self):
        fautives = []
        for chemin, item in self.schema['paths'].items():
            for methode, operation in item.items():
                if methode not in ('post', 'put'):
                    continue
                corps = operation.get('requestBody')
                refs = self._refs(corps) if corps else ''
                if '#/components/schemas/CalepinageRequest"' in refs:
                    fautives.append(f'{methode.upper()} {chemin}')
        self.assertEqual(
            fautives, [],
            "Ces opérations héritent du corps du pivot sans l'avoir déclaré "
            f"(@extend_schema(request=…)) : {fautives}")

    def test_la_liste_et_les_ecritures_publient_la_forme_lue(self):
        """Ce que ``to_representation`` rend : ``lead`` en objet, ``nom``."""
        composants = self.schema['components']['schemas']
        lecture = composants['CalepinageLecture']['properties']
        self.assertIn('nom', lecture)
        self.assertNotEqual(lecture['lead'].get('type'), 'integer')

    def test_les_formes_du_contrat_suivent_leurs_echantillons(self):
        import json

        from apps.calepinage.serializers import (
            FORMES_DU_CONTRAT, forme_du_contrat,
        )

        self.assertGreater(len(FORMES_DU_CONTRAT), 20)
        composants = self.schema['components']['schemas']
        for composant, (fichier, cle) in sorted(FORMES_DU_CONTRAT.items()):
            with self.subTest(composant=composant):
                echantillon = (RACINE_APP / 'contract_samples' / fichier)
                attendu = set(json.loads(
                    echantillon.read_text(encoding='utf-8'))[cle])
                self.assertTrue(attendu, f'{fichier}[{cle}] est vide')
                if composant in composants:
                    self.assertEqual(
                        set(composants[composant]['properties']), attendu,
                        f"{composant} a dérivé de {fichier}[{cle}] : "
                        "régénérer la forme depuis l'échantillon.")
        self.assertEqual(
            set(forme_du_contrat('CalepinageTestDerive',
                                 'calepinage_troncons.json').fields),
            {'troncons', 'totaux', 'omissions', 'verdicts'})

    def _operation(self, methode, suffixe):
        return self.schema['paths'][
            '/api/django/calepinage/calepinages/' + suffixe][methode]

    def test_corps_oneof_ou_brut_publie_obligatoire(self):
        """ERR-ENF11-FUZZ-CALEPINAGE — un corps ``oneOf``/``anyOf`` ou brut
        passait pour facultatif : une requête SANS corps, refusée en 400,
        était « conforme » (api-fuzz du 13/10/2026)."""
        for methode, suffixe in (
                ('post', ''), ('post', '{id}/approbation/'),
                ('post', '{id}/suggestions-pente/'),
                ('post', '{id}/pose-reelle/'),
                ('post', '{id}/joindre-piece/')):
            with self.subTest(operation=f'{methode} {suffixe}'):
                corps = self._operation(methode, suffixe)['requestBody']
                self.assertIs(corps.get('required'), True)

    def test_joindre_piece_publie_en_multipart_seul(self):
        """Le champ binaire publié en JSON faisait planter le moteur du fuzz
        (« Unsupported type: 'Binary' ») : l'upload est multipart seul."""
        corps = self._operation('post', '{id}/joindre-piece/')['requestBody']
        self.assertEqual(list(corps['content']), ['multipart/form-data'])

    def test_refus_sans_motif_et_bornes_publies(self):
        corps = self._operation('post', '{id}/approbation/')['requestBody']
        schema = corps['content']['application/json']['schema']
        composants = self.schema['components']['schemas']
        schema = composants[schema['$ref'].rsplit('/', 1)[-1]]
        refus = [branche for branche in schema['oneOf']
                 if branche['properties']['decision']['anyOf']
                 == [{'enum': ['refuse']}]]
        self.assertEqual(refus[0]['required'], ['motif'])
        ids = composants['CalepinageComparerProjetsRequeteRequest'][
            'properties']['ids']
        self.assertEqual((ids['minItems'], ids['maxItems']), (1, 5))

    def _corps_multipart(self, suffixe):
        schema = self._operation('post', suffixe)['requestBody']['content'][
            'multipart/form-data']['schema']
        return self.schema['components']['schemas'][
            schema['$ref'].rsplit('/', 1)[-1]]

    def test_depots_de_fichier_publient_le_predicat_du_serveur(self):
        """ERR-ENF11-FUZZ-CALEPINAGE (w4) — photo, fond de plan et série météo :
        le schéma dit EXACTEMENT ce que le serveur exige (date saisie, genre
        énuméré, jeton / fournisseur non blancs) ; sans cela le fuzz envoyait
        une valeur « conforme » (``" "``, genre libre) et recevait 400."""
        from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL

        composants = self.schema['components']['schemas']
        photo = self._corps_multipart('{id}/photos/')
        self.assertEqual(sorted(photo['required']), ['photo', 'prise_le'])
        self.assertEqual(photo['properties']['prise_le'],
                         {'type': 'string', 'format': 'date'})
        genre = composants[
            photo['properties']['genre']['$ref'].rsplit('/', 1)[-1]]
        self.assertEqual(genre['enum'], ['drone', 'oblique', 'sol'])
        fond = self._corps_multipart('{id}/fond-plan/')
        self.assertEqual(fond['properties']['base_empreinte']['pattern'],
                         MOTIF_NON_BLANC_SANS_NUL)
        meteo = self._corps_multipart('{id}/meteo-fichier/')
        self.assertEqual(meteo['properties']['fournisseur']['pattern'],
                         MOTIF_NON_BLANC_SANS_NUL)

    def test_importer_plan_publie_le_rang_et_le_calage_du_serveur(self):
        """Le rang d'entité (≥ 1) et le calage (deux points, distance dans les
        bornes) sont publiés tels que ``lire_calage`` les juge : un seul
        prédicat (le ``CalageSerializer``)."""
        from apps.calepinage.services.import_plan import (
            DISTANCE_CALAGE_MIN_M, ROTATION_CALAGE_MAX_DEG,
        )

        composants = self.schema['components']['schemas']
        corps = self._corps_multipart('{id}/importer-plan/')
        self.assertEqual(corps['required'], ['fichier'])
        self.assertEqual(corps['properties']['entite'],
                         {'type': 'integer', 'minimum': 1})
        calage = composants[
            corps['properties']['calage']['$ref'].rsplit('/', 1)[-1]]
        self.assertEqual(sorted(calage['required']),
                         ['distanceM', 'pointA', 'pointB'])
        self.assertEqual(calage['properties']['pointA']['minItems'], 2)
        self.assertEqual(calage['properties']['distanceM']['minimum'],
                         DISTANCE_CALAGE_MIN_M)
        rotation = calage['properties']['rotationDeg']
        self.assertEqual(rotation['maximum'], ROTATION_CALAGE_MAX_DEG)
        self.assertIs(rotation['nullable'], True)
        self.assertNotIn('rotationDeg', calage['required'])

    def _composant(self, schema):
        return self.schema['components']['schemas'][
            schema['$ref'].rsplit('/', 1)[-1]]

    def test_suggestion_pente_publie_au_moins_un_pan(self):
        """``zones`` : liste NON VIDE (``minItems: 1``) — le serveur refuse un
        document sans pan ; publié libre, ``[]`` était un cas « conforme »."""
        operation = self.schema['paths'][
            '/api/django/calepinage/parametres/suggestion-pente/']['post']
        corps = self._composant(operation['requestBody']['content'][
            'application/json']['schema'])
        document = self._composant(corps['properties']['roof_layout'])
        self.assertEqual(document['required'], ['zones'])
        self.assertEqual(document['properties']['zones']['minItems'], 1)

    def test_edition_du_schema_unifilaire_publie_ce_que_le_service_juge(self):
        """Textes non blancs sans nul d'au plus 120 signes, positions {x, y}
        positives : le prédicat de ``services/sld.py``, dit au schéma."""
        from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL

        from apps.calepinage.services.sld import LONGUEUR_TEXTE_MAX

        operation = self._operation('post', '{id}/schema-unifilaire/')
        corps = self._composant(operation['requestBody']['content'][
            'application/json']['schema'])
        self.assertEqual(sorted(corps['properties']),
                         ['libelles', 'positions', 'reperes'])
        for rubrique in ('libelles', 'reperes'):
            texte = corps['properties'][rubrique]['additionalProperties']
            self.assertEqual(texte['maxLength'], LONGUEUR_TEXTE_MAX)
            self.assertEqual(texte['pattern'], MOTIF_NON_BLANC_SANS_NUL)
            self.assertIs(texte['nullable'], True)
        position = self._composant(
            corps['properties']['positions']['additionalProperties'][
                'allOf'][0])
        self.assertEqual(position['required'], ['x', 'y'])
        self.assertEqual(position['properties']['x']['minimum'], 0)

    def test_depuis_modele_publie_un_rattachement_et_des_identifiants_bornes(self):
        """Au moins un de lead / client / devis (``anyOf``), identifiants
        entiers de 1 à 2^31-1, titre de 200 signes au plus, corps obligatoire :
        ce que le serveur exige, dit au schéma."""
        operation = self._operation('post', 'depuis-modele/')
        self.assertIs(operation['requestBody'].get('required'), True)
        corps = self._composant(operation['requestBody']['content'][
            'application/json']['schema'])
        self.assertEqual(corps['anyOf'], [{'required': ['lead_id']},
                                          {'required': ['client_id']},
                                          {'required': ['devis_id']}])
        for cle in ('modele_id', 'lead_id', 'client_id', 'devis_id'):
            self.assertEqual(corps['properties'][cle]['minimum'], 1, cle)
            self.assertEqual(corps['properties'][cle]['maximum'],
                             2_147_483_647, cle)
        self.assertEqual(corps['properties']['titre']['maxLength'], 200)

    def test_meteo_fichier_lu_peut_etre_null(self):
        """``GET meteo-fichier/`` sert ``null`` sans fichier retenu."""
        reponse = self._operation('get', '{id}/meteo-fichier/')['responses']
        schema = reponse['200']['content']['application/json']['schema']
        self.assertIs(schema.get('nullable'), True)

    def test_layout_ecrit_documente_son_428(self):
        """ACAL316 — ``POST layout/`` sans jeton If-Match répond 428 : le code
        est publié (api-fuzz du 14/10/2026 « code HTTP non documenté »)."""
        reponses = self._operation('post', '{id}/layout/')['responses']
        self.assertIn('200', reponses)
        self.assertIn('428', reponses)
        schema = reponses['428']['content']['application/json']['schema']
        composant = self.schema['components']['schemas'][
            schema['$ref'].rsplit('/', 1)[-1]]
        self.assertEqual(list(composant['properties']), ['detail'])

    def test_layout_ecrit_exige_son_jeton_et_un_corps_non_vide(self):
        """ACAL316 — la précondition fait partie du contrat : l'en-tête
        ``If-Match`` est OBLIGATOIRE et non blanc, le corps obligatoire et
        non vide (api-fuzz du 14/10/2026 : un ``If-Match`` vide, « conforme »,
        recevait le 428 — requête conforme rejetée)."""
        operation = self._operation('post', '{id}/layout/')
        jeton = [p for p in operation['parameters']
                 if p['in'] == 'header' and p['name'] == 'If-Match']
        self.assertEqual(len(jeton), 1)
        self.assertIs(jeton[0]['required'], True)
        self.assertEqual(jeton[0]['schema'],
                         {'type': 'string', 'pattern': r'\S'})
        corps = operation['requestBody']
        self.assertIs(corps.get('required'), True)
        regle = corps['content']['application/json']['schema']['allOf'][1]
        self.assertEqual(regle['minProperties'], 1)
        for cle in ('roof_layout', 'layout'):
            self.assertEqual(regle['properties'][cle],
                             {'type': 'object', 'minProperties': 1})
        lecture = self._operation('get', '{id}/layout/')
        self.assertNotIn('If-Match', [p['name'] for p in
                                      lecture.get('parameters', [])])
