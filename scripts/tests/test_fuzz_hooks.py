"""ENF1b — tests des crochets Schemathesis du job `api-fuzz`
(`scripts/fuzz/schemathesis_hooks.py`). Stdlib pur : le module
`schemathesis` (absent du job stage-names) est remplacé par un bouchon.

Régression du run 37897343514 : le fuzzeur passait la politique réseau de
sa propre société en `enforce` et recevait ensuite 403 sur TOUT (1 760
opérations « Missing authentication », « Authentication stopped working
mid-run »).
"""
import enum
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _bouchon_schemathesis():
    mod = types.ModuleType('schemathesis')

    class GenerationMode(enum.Enum):
        POSITIVE = 'positive'
        NEGATIVE = 'negative'

    def auth(**kw):
        mod.auth_kwargs = kw
        return lambda cls: cls

    def deserializer(*_types):
        return lambda fn: fn

    mod.GenerationMode = GenerationMode
    mod.auth = auth
    mod.deserializer = deserializer
    mod.hook = lambda fn: fn
    return mod


def _charger_hooks(etat, ids_chemin=None):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                     encoding='utf-8') as fh:
        json.dump(etat, fh)
    os.environ['FUZZ_STATE_FILE'] = fh.name
    ids_fichier = None
    if ids_chemin is not None:
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as fi:
            json.dump(ids_chemin, fi)
        ids_fichier = fi.name
        os.environ['FUZZ_IDS_FILE'] = ids_fichier
    precedent = sys.modules.get('schemathesis')
    sys.modules['schemathesis'] = _bouchon_schemathesis()
    sys.modules.setdefault('requests', types.ModuleType('requests'))
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('schemathesis_hooks', None)
        return importlib.import_module('schemathesis_hooks')
    finally:
        _charger_hooks.auth_kwargs = getattr(
            sys.modules['schemathesis'], 'auth_kwargs', None)
        sys.path.pop(0)
        os.unlink(fh.name)
        os.environ.pop('FUZZ_STATE_FILE', None)
        os.environ.pop('FUZZ_IDS_FILE', None)
        if ids_fichier:
            os.unlink(ids_fichier)
        if precedent is None:
            sys.modules.pop('schemathesis', None)
        else:
            sys.modules['schemathesis'] = precedent


def _cas(hooks, methode, chemin, corps=None, params=None, mode='POSITIVE'):
    operation = types.SimpleNamespace(method=methode, path=chemin)
    meta = types.SimpleNamespace(generation=types.SimpleNamespace(
        mode=getattr(hooks.GenerationMode, mode)))
    return types.SimpleNamespace(operation=operation, body=corps,
                                 path_parameters=params or {}, meta=meta)


class CrochetsFuzzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}})

    def _appel(self, cas):
        self.hooks.before_call(None, cas, {})
        return cas

    def test_politique_reseau_enforce_ramenee_a_monitor(self):
        for methode, chemin in (
                ('POST', '/api/django/identity/network-policies/'),
                ('PATCH', '/api/django/identity/network-policies/{id}/'),
                ('PUT', '/api/django/identity/network-policies/{id}/')):
            for mode in ('POSITIVE', 'NEGATIVE'):
                with self.subTest(methode=methode, mode=mode):
                    cas = self._appel(_cas(self.hooks, methode, chemin,
                                           {'mode': 'enforce',
                                            'applies_to': 'all'}, mode=mode))
                    self.assertEqual(cas.body['mode'], 'monitor')
                    self.assertEqual(cas.body['applies_to'], 'all')

    def test_politique_reseau_autres_modes_intacts(self):
        for valeur in ('off', 'monitor', 42, None):
            with self.subTest(valeur=valeur):
                cas = self._appel(_cas(
                    self.hooks, 'PATCH',
                    '/api/django/identity/network-policies/{id}/',
                    {'mode': valeur}))
                self.assertEqual(cas.body['mode'], valeur)

    def test_lecture_et_autre_chemin_intacts(self):
        cas = self._appel(_cas(self.hooks, 'GET',
                               '/api/django/identity/network-policies/',
                               {'mode': 'enforce'}))
        self.assertEqual(cas.body['mode'], 'enforce')
        cas = self._appel(_cas(self.hooks, 'POST',
                               '/api/django/sav/tickets/',
                               {'mode': 'enforce'}))
        self.assertEqual(cas.body['mode'], 'enforce')

    def test_corps_non_dict_ignore(self):
        cas = self._appel(_cas(self.hooks, 'POST',
                               '/api/django/identity/network-policies/',
                               ['enforce']))
        self.assertEqual(cas.body, ['enforce'])

    def test_role_du_fuzzeur_protege(self):
        cas = self._appel(_cas(self.hooks, 'PATCH', '/api/django/roles/{id}/',
                               {'permissions': []}, params={'id': 7}))
        self.assertEqual(cas.path_parameters['id'],
                         self.hooks.ID_INEXISTANT)
        cas = self._appel(_cas(self.hooks, 'PATCH', '/api/django/roles/{id}/',
                               {'permissions': []}, params={'id': 8}))
        self.assertEqual(cas.path_parameters['id'], 8)

    def test_compte_et_societe_toujours_proteges(self):
        cas = self._appel(_cas(self.hooks, 'DELETE', '/api/django/users/{id}/',
                               params={'id': 4}))
        self.assertEqual(cas.path_parameters['id'],
                         self.hooks.ID_INEXISTANT)
        cas = self._appel(_cas(self.hooks, 'GET', '/api/django/users/{id}/',
                               params={'id': 4}))
        self.assertEqual(cas.path_parameters['id'], 4)

    def test_aucun_rejeu_sur_401_et_rafraichissement_proactif(self):
        # ENF11 — run 38129616897 : reauth_count 0, reauth_broke true.
        self.assertEqual(_charger_hooks.auth_kwargs,
                         {'refresh_interval': 600, 'retry_on': []})

    def test_bearer_genere_recoit_le_jeton_valide(self):
        # ENF11 — api-fuzz-full 40986772772 : 998 routes à cookie 401-seules.
        # Schemathesis 4.28 génère l'alternative `bearerJWT` (« Bearer » +
        # valeur d'en-tête quelconque) ; le serveur refuse un Authorization
        # mal formé (d4ef375b4) même avec le cookie valide.
        auth = self.hooks.FuzzAdminCookieAuth()
        for cle, valeur in (('Authorization', 'Bearer '),
                            ('Authorization', 'Bearer a b!#'),
                            ('authorization', 'Bearer x=y')):
            with self.subTest(cle=cle, valeur=valeur):
                cas = types.SimpleNamespace(
                    cookies={'access_token': 'genere'},
                    headers={cle: valeur, 'X-Autre': 'garde'})
                auth.set(cas, 'jwt.valide-1', None)
                self.assertEqual(cas.cookies['access_token'], 'jwt.valide-1')
                self.assertEqual(cas.headers,
                                 {cle: 'Bearer jwt.valide-1',
                                  'X-Autre': 'garde'})

    def test_bearer_jamais_ajoute_quand_absent(self):
        auth = self.hooks.FuzzAdminCookieAuth()
        for entetes in (None, {}, {'X-Autre': 'v'}):
            with self.subTest(entetes=entetes):
                cas = types.SimpleNamespace(cookies=None, headers=entetes)
                auth.set(cas, 'jwt', None)
                self.assertEqual(cas.cookies, {'access_token': 'jwt'})
                self.assertEqual(cas.headers, entetes)


class IdsCheminTests(unittest.TestCase):
    """ENF11 — ids réels pour `{id}`/`{pk}` (1 273 opérations 404-seules)."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}},
            ids_chemin={'/api/django/ventes/devis/': [11, 12, 13],
                        '/api/django/docs/': ['aaa', 'bbb']})

    def _appel(self, chemin, params, mode='POSITIVE', methode='GET'):
        cas = _cas(self.hooks, methode, chemin, params=params, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas

    def _valeurs(self, chemin, nb=200, **kw):
        return [self._appel(chemin, {'id': 10**6 + i}, **kw)
                .path_parameters['id'] for i in range(nb)]

    def test_id_reel_substitue_et_part_invalide_conservee(self):
        vals = self._valeurs('/api/django/ventes/devis/{id}/proposal/')
        reels = [v for v in vals if v in (11, 12, 13)]
        gardes = [v for v in vals if v >= 10**6]
        self.assertEqual(len(reels) + len(gardes), 200)
        self.assertTrue(0.15 < len(gardes) / 200 < 0.35, len(gardes))
        self.assertEqual(set(reels), {11, 12, 13})

    def test_deterministe(self):
        self.assertEqual(self._valeurs('/api/django/ventes/devis/{id}/'),
                         self._valeurs('/api/django/ventes/devis/{id}/'))

    def test_cas_negatifs_jamais_touches(self):
        vals = self._valeurs('/api/django/ventes/devis/{id}/', mode='NEGATIVE')
        self.assertTrue(all(v >= 10**6 for v in vals))

    def test_parametres_non_id_intacts(self):
        for gabarit, nom in (
                ('/api/django/ventes/devis/{token}/', 'token'),
                ('/api/django/ventes/devis/{jeton}/', 'jeton'),
                ('/api/django/ventes/devis/{slug}/', 'slug'),
                ('/api/django/ventes/devis/{key}/', 'key')):
            cas = self._appel(gabarit, {nom: 'abc'})
            self.assertEqual(cas.path_parameters[nom], 'abc')

    def test_sans_inventaire_ou_type_incompatible_intact(self):
        cas = self._appel('/api/django/inconnu/{id}/', {'id': 5})
        self.assertEqual(cas.path_parameters['id'], 5)
        # ids str (uuid) : jamais posés à la place d'un entier généré.
        vals = self._valeurs('/api/django/docs/{id}/')
        self.assertTrue(all(isinstance(v, int) for v in vals))

    def test_id_en_chaine_de_la_phase_coverage_substitue(self):
        # CI #1176 — la phase coverage rend `{id}` déjà en chaîne (« 0 ») :
        # l'id réel est posé sous la même forme (« 0 opérations avec id réel »
        # sinon) ; une chaîne non entière (uuid, slug) garde sa valeur.
        vals = [self._appel('/api/django/ventes/devis/{id}/', {'id': str(10**6 + i)})
                .path_parameters['id'] for i in range(200)]
        self.assertTrue(all(isinstance(v, str) for v in vals))
        reels = [v for v in vals if v in ('11', '12', '13')]
        self.assertTrue(0.6 < len(reels) / 200 < 0.9, len(reels))
        cas = self._appel('/api/django/ventes/devis/{id}/', {'id': 'abc'})
        self.assertEqual(cas.path_parameters['id'], 'abc')

    def test_fuzz_admin_protege_aussi_en_chaine(self):
        h = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}},
            ids_chemin={'/api/django/users/': [4]})
        for i in range(40):
            cas = _cas(h, 'DELETE', '/api/django/users/{id}/',
                       params={'id': str(10**6 + i)})
            h.before_call(None, cas, {})
            self.assertNotEqual(str(cas.path_parameters['id']), '4')

    def test_id_imbrique_second_parametre_intact(self):
        cas = self._appel('/api/django/ventes/devis/{id}/lignes/{ligne_id}/',
                          {'id': 10**6, 'ligne_id': 77})
        self.assertEqual(cas.path_parameters['ligne_id'], 77)

    def test_fuzz_admin_reste_protege_apres_substitution(self):
        h = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}},
            ids_chemin={'/api/django/users/': [4]})
        for i in range(40):
            cas = _cas(h, 'DELETE', '/api/django/users/{id}/',
                       params={'id': 10**6 + i})
            h.before_call(None, cas, {})
            self.assertNotEqual(cas.path_parameters['id'], 4)


class IdsFkImbriquesTests(unittest.TestCase):
    """ENF11 (achats) — les FK des LIGNES imbriquées reçoivent des ids réels."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'produit': [11, 12], 'fournisseur': [5]}})

    def _corps(self, mode='POSITIVE'):
        cas = _cas(self.hooks, 'POST', '/api/django/achats/retours-fournisseur/',
                   {'fournisseur': 99999, 'motif': 'x',
                    'lignes': [{'produit': 0, 'quantite': 3},
                               {'produit': 12, 'quantite': 1}]}, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas.body

    def test_produit_de_ligne_remplace_par_un_id_reel(self):
        corps = self._corps()
        self.assertEqual(corps['fournisseur'], 5)
        self.assertIn(corps['lignes'][0]['produit'], (11, 12))
        self.assertEqual(corps['lignes'][1]['produit'], 12)
        self.assertEqual(corps['lignes'][0]['quantite'], 3)

    def test_cas_negatif_jamais_touche(self):
        corps = self._corps(mode='NEGATIVE')
        self.assertEqual(corps['fournisseur'], 99999)
        self.assertEqual(corps['lignes'][0]['produit'], 0)


class FkCorpsSansReecritureTests(unittest.TestCase):
    """CI #997 — une FK déjà connue (ou une valeur du fil sans changement) n'est
    PAS réécrite : Schemathesis revalide toute clé réécrite sur sa valeur
    vivante et basculerait le cas positif en négatif."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'client_id': [5, 6], 'lead_id': [9]}})

    class _Journal(dict):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            self.ecritures = []

        def __setitem__(self, cle, valeur):
            self.ecritures.append(cle)
            super().__setitem__(cle, valeur)

    def _corps(self, **champs):
        corps = self._Journal(champs)
        cas = _cas(self.hooks, 'POST', '/api/django/portail/documents-client-portail/',
                   corps)
        self.hooks.before_call(None, cas, {})
        return corps

    def test_valeur_du_fil_en_chaine_non_reecrite(self):
        corps = self._corps(client_id='0', lead_id='0', libelle='x')
        self.assertEqual(corps.ecritures, [])
        self.assertEqual(corps['client_id'], '0')

    def test_id_deja_connu_non_reecrit(self):
        corps = self._corps(client_id=5, lead_id=9)
        self.assertEqual(corps.ecritures, [])

    def test_id_inconnu_toujours_remplace(self):
        corps = self._corps(client_id=0, lead_id=0)
        self.assertEqual(sorted(corps.ecritures), ['client_id', 'lead_id'])
        self.assertIn(corps['client_id'], (5, 6))
        self.assertEqual(corps['lead_id'], 9)


class FichiersPdfTests(unittest.TestCase):
    """CI #997 — le dépôt d'un gabarit réglementaire exige un PDF : un cas
    POSITIF en reçoit un ; négatifs, autres chemins et autres champs intacts."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}})

    def _corps(self, methode='POST', chemin='/api/django/calepinage/gabarits-dossiers/',
               corps=None, mode='POSITIVE'):
        cas = _cas(self.hooks, methode, chemin,
                   {'fichier': b'', 'code': '0'} if corps is None else corps,
                   mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas.body

    def test_octets_quelconques_remplaces_par_un_pdf(self):
        for methode, chemin in (
                ('POST', '/api/django/calepinage/gabarits-dossiers/'),
                ('PATCH', '/api/django/calepinage/gabarits-dossiers/{id}/')):
            with self.subTest(methode=methode):
                corps = self._corps(methode, chemin)
                self.assertTrue(corps['fichier'].startswith(b'%PDF-'))
                self.assertEqual(corps['code'], '0')

    def test_records_attachments_recoit_un_pdf(self):
        # CI #997 (2e passe) — la pièce jointe records suit la même table.
        corps = self._corps('POST', '/api/django/records/attachments/',
                            {'file': b'', 'model': 'crm.lead', 'id': '1'})
        self.assertTrue(corps['file'].startswith(b'%PDF-'))
        self.assertEqual(corps['model'], 'crm.lead')

    def test_portail_documents_client_recoit_un_pdf(self):
        # CI #997 (3) — le dépôt d'un document du portail exige un vrai fichier.
        corps = self._corps('POST', '/api/django/portail/documents-client-portail/',
                            {'fichier': b'', 'client_id': 1})
        self.assertTrue(corps['fichier'].startswith(b'%PDF-'))
        self.assertEqual(corps['client_id'], 1)

    def test_fiche_technique_recoit_un_pdf(self):
        # api-fuzz-full 27/10 — le PDF d'une fiche technique (création et
        # édition) : le serveur lit les octets magiques.
        for methode, chemin in (
                ('POST', '/api/django/stock/fiches-techniques/'),
                ('PUT', '/api/django/stock/fiches-techniques/{id}/'),
                ('PATCH', '/api/django/stock/fiches-techniques/{id}/')):
            with self.subTest(methode=methode):
                corps = self._corps(methode, chemin,
                                    {'pdf': b'd\xef\xbf\xbd', 'produit': 3})
                self.assertTrue(corps['pdf'].startswith(b'%PDF-'))
                self.assertEqual(corps['produit'], 3)

    def test_affiche_d_un_devis_recoit_un_png(self):
        # CI #997 (w4, ventes) — roof-image du devis lit les octets magiques.
        corps = self._corps('POST', '/api/django/ventes/devis/{id}/roof-image/',
                            {'image': b''})
        self.assertTrue(corps['image'].startswith(b'\x89PNG'))

    def test_scan_carte_et_photo_de_visite_recoivent_un_png(self):
        # ERR-ENF11-FUZZ-CRM / -VISITES — deux dépôts de PHOTO dont le serveur
        # lit les octets : un cas positif en reçoit un PNG décodable.
        scan = self._corps('POST', '/api/django/crm/leads/scan-carte/',
                           {'file': b''})
        self.assertTrue(scan['file'].startswith(b'\x89PNG'))
        photo = self._corps('POST', '/api/django/visites/visites/{id}/photos/',
                            {'fichier': b'', 'slot_code': 'general_facade'})
        self.assertTrue(photo['fichier'].startswith(b'\x89PNG'))
        self.assertEqual(photo['slot_code'], 'general_facade')
        piece = self._corps(
            'POST', '/api/django/crm/relance-etapes/{id}/piece-recue/',
            {'fichier': b'', 'type_piece': 'facture'})
        self.assertTrue(piece['fichier'].startswith(b'%PDF-'))
        negatif = self._corps('POST', '/api/django/crm/leads/scan-carte/',
                              {'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def test_note_de_lead_recoit_un_png(self):
        # ERR-ENF11-FUZZ-CRM — ``noter`` (multipart) : le fichier seul est une
        # note conforme ; ses octets sont lus par ``store_attachment``.
        corps = self._corps('POST', '/api/django/crm/leads/{id}/noter/',
                            {'file': b'', 'body': 'x'})
        self.assertTrue(corps['file'].startswith(b'\x89PNG'))
        self.assertEqual(corps['body'], 'x')

    def test_demande_d_approbation_recoit_un_pdf(self):
        # ERR-ENF11-FUZZ-AUTOMATION — le part ``file`` d'une demande reçoit un
        # PDF ; le type de demande et le payload restent intacts, un cas
        # NÉGATIF garde son fichier vide.
        chemin = '/api/django/automation/approval-requests/'
        corps = self._corps('POST', chemin, {'file': b'', 'request_type': 3})
        self.assertTrue(corps['file'].startswith(b'%PDF-'))
        self.assertEqual(corps['request_type'], 3)
        negatif = self._corps('POST', chemin, {'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def _operation_multipart(self, schema):
        corps = types.SimpleNamespace(
            media_type='multipart/form-data', definition={'schema': schema})
        return types.SimpleNamespace(body=[corps])

    def test_noms_de_fichiers_resout_le_ref_du_corps_regroupe(self):
        # CI #997 (3) — schéma référençant une énumération : Schemathesis range
        # le corps sous ``x-bundled`` et ne voit plus les champs binaires.
        propres = {'file': {'type': 'string', 'format': 'binary'},
                   'model': {'type': 'string'},
                   'pieces': {'type': 'array',
                              'items': {'type': 'string', 'format': 'binary'}}}
        regroupe = {'$ref': '#/x-bundled/schema5',
                    'x-bundled': {'schema5': {'type': 'object',
                                              'properties': propres}}}
        self.assertEqual(
            self.hooks._noms_de_fichiers(self._operation_multipart(regroupe)),
            {'file', 'pieces'})
        en_ligne = {'type': 'object', 'properties': propres}
        self.assertEqual(
            self.hooks._noms_de_fichiers(self._operation_multipart(en_ligne)),
            {'file', 'pieces'})
        self.assertEqual(self.hooks._noms_de_fichiers(
            types.SimpleNamespace(body=[types.SimpleNamespace(
                media_type='application/json',
                definition={'schema': en_ligne})])), set())

    def test_noms_de_fichiers_traverse_la_regle_de_racine_allof(self):
        # ERR-ENF11-FUZZ-CRM — ``x-corps-resserre`` enveloppe le corps en
        # ``{'allOf': [corps, règle]}`` (POST crm/leads/{id}/noter/) : le
        # fichier doit garder son nom, sinon Django le lit comme du texte.
        regle = {'anyOf': [{'required': ['body']}, {'required': ['file']}]}
        corps = {'type': 'object', 'properties': {
            'body': {'type': 'string'},
            'file': {'type': 'string', 'format': 'binary'}}}
        regroupe = {'allOf': [{'$ref': '#/x-bundled/schema1'}, regle],
                    'x-bundled': {'schema1': corps}}
        en_ligne = {'allOf': [corps, regle]}
        for schema in (regroupe, en_ligne):
            self.assertEqual(
                self.hooks._noms_de_fichiers(self._operation_multipart(schema)),
                {'file'})
        # Aucun membre à propriétés : le schéma est rendu tel quel (pas de nom).
        sans = {'allOf': [regle]}
        self.assertEqual(
            self.hooks._noms_de_fichiers(self._operation_multipart(sans)), set())

    def test_parts_de_fichier_recoivent_leur_nom(self):
        schema = {'type': 'object', 'properties': {
            'file': {'type': 'string', 'format': 'binary'},
            'model': {'type': 'string'}}}
        operation = self._operation_multipart(schema)
        vus = []

        def original(op, donnees, choisis=None):
            vus.append((op, choisis))
            return ([('file', (None, b'%PDF-1.4')), ('model', (None, b'x')),
                     ('file', ('deja.pdf', b'%PDF')), ('autre', (None, b'y'))],
                    None)

        prepare = self.hooks._avec_noms_de_fichier(original)
        fichiers, donnees = prepare(operation, {})
        self.assertEqual(fichiers, [
            ('file', ('file', b'%PDF-1.4')),     # nom posé
            ('model', (None, b'x')),             # champ texte : intact
            ('file', ('deja.pdf', b'%PDF')),     # nom déjà là : intact
            ('autre', (None, b'y'))])            # champ hors schéma : intact
        self.assertIsNone(donnees)
        self.assertEqual(vus, [(operation, None)])
        # Idempotent : un second habillage ne s'empile pas.
        self.assertIs(self.hooks._avec_noms_de_fichier(prepare), prepare)

    def test_champs_structures_resout_les_ref_du_corps_regroupe(self):
        # CI #997 (4) — ``champs`` (tableau d'objets) de gabarits-dossiers : le
        # corps regroupé cache ses propriétés ; seuls tableaux/objets sortent,
        # ni le texte, ni le fichier, ni la liste de fichiers.
        propres = {
            'fichier': {'type': 'string', 'format': 'binary'},
            'pieces': {'type': 'array',
                       'items': {'type': 'string', 'format': 'binary'}},
            'code': {'type': 'string'},
            'champs': {'type': 'array', 'items': {'$ref': '#/x-bundled/s2'}},
            'options': {'$ref': '#/x-bundled/s3'},
            'genre': {'$ref': '#/x-bundled/s4'}}
        regroupe = {'$ref': '#/x-bundled/s1', 'x-bundled': {
            's1': {'type': 'object', 'properties': propres},
            's2': {'type': 'object', 'properties': {}},
            's3': {'type': 'object'},
            's4': {'type': 'string', 'enum': ['a', 'b']}}}
        self.assertEqual(
            self.hooks._champs_structures(self._operation_multipart(regroupe)),
            {'champs', 'options'})
        self.assertEqual(self.hooks._champs_structures(
            types.SimpleNamespace(body=[types.SimpleNamespace(
                media_type='application/json',
                definition={'schema': regroupe})])), set())

    def test_collecte_json_complete_sans_ecraser(self):
        regroupe = {'$ref': '#/x-bundled/s1', 'x-bundled': {'s1': {
            'type': 'object', 'properties': {
                'champs': {'type': 'array', 'items': {'type': 'object'}},
                'deja': {'type': 'object'}}}}}
        contexte = types.SimpleNamespace(case=types.SimpleNamespace(
            operation=self._operation_multipart(regroupe)))

        def original(ctx):
            return {'deja': 'application/vnd.test+json'}

        collecte = self.hooks._avec_parts_json(original)
        self.assertEqual(collecte(contexte), {
            'deja': 'application/vnd.test+json',   # déjà vu : intact
            'champs': 'application/json'})         # ajouté
        self.assertIs(self.hooks._avec_parts_json(collecte), collecte)

    def test_binaire_schemathesis_garde_son_type(self):
        # ``Binary`` (str + ``.data``) : des octets nus feraient basculer le cas
        # positif en négatif à la revalidation de Schemathesis.
        class Binary(str):
            def __new__(cls, data):
                return super().__new__(cls)

            def __init__(self, data):
                self.data = data

        corps = self._corps(corps={'fichier': Binary(b'')})
        self.assertIsInstance(corps['fichier'], Binary)
        self.assertTrue(corps['fichier'].data.startswith(b'%PDF-'))

    def test_lecture_de_meta_sans_revalidation(self):
        # Après une substitution de FK, ``case.meta`` revaliderait le corps :
        # le crochet PDF lit ``_meta`` directement quand il existe.
        class Cas:
            _meta = types.SimpleNamespace(generation=types.SimpleNamespace(
                mode=None))

            @property
            def meta(self):
                raise AssertionError('case.meta lu : revalidation déclenchée')

        self.assertIs(self.hooks._meta_sans_revalidation(Cas()), Cas._meta)

    def test_parts_nuls_absents_sans_revalidation(self):
        # api-fuzz-full 25/10 (series-lot) — lu APRÈS la substitution de FK,
        # ``case.meta`` revalidait le corps à octets et le déclarait NÉGATIF.
        hooks = self.hooks

        class Cas:
            operation = types.SimpleNamespace(body=[types.SimpleNamespace(
                media_type='multipart/form-data')])
            _meta = types.SimpleNamespace(generation=types.SimpleNamespace(
                mode=hooks.GenerationMode.POSITIVE))
            body = {'fichier': 'f', 'produit': None}

            @property
            def meta(self):
                raise AssertionError('case.meta lu : revalidation déclenchée')

        cas = Cas()
        hooks._parts_nuls_absents(cas)
        self.assertEqual(cas.body, {'fichier': 'f'})

    def test_corps_a_fichier_non_marque_a_revalider(self):
        # Schemathesis déclare invalide tout corps à octets REVALIDÉ : le
        # drapeau « à revalider » du corps est retiré, celui de la query reste.
        class Binary(str):
            def __new__(cls, data):
                return super().__new__(cls)

            def __init__(self, data):
                self.data = data

        class Lieu:
            def __init__(self, valeur):
                self.value = valeur

        corps_lieu, query_lieu = Lieu('body'), Lieu('query')
        cas = _cas(self.hooks, 'POST', '/api/django/calepinage/gabarits-dossiers/',
                   {'fichier': Binary(b''), 'code': '0'})
        empreintes = {}
        cas._meta = types.SimpleNamespace(
            generation=cas.meta.generation,
            _dirty={corps_lieu, query_lieu},
            components={corps_lieu: 1, query_lieu: 1},
            clear_dirty=lambda lieu: cas._meta._dirty.discard(lieu),
            update_validated_hash=empreintes.__setitem__)
        cas._hash_container = lambda valeur: 42
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas._meta._dirty, {query_lieu})
        # L'empreinte validée du corps est réalignée, pas celle de la query.
        self.assertEqual(empreintes, {corps_lieu: 42})
        # Un corps sans octets garde son drapeau (revalidation normale).
        cas = _cas(self.hooks, 'POST', '/api/django/calepinage/gabarits-dossiers/',
                   {'code': '0'})
        cas._meta = types.SimpleNamespace(
            generation=cas.meta.generation,
            _dirty={corps_lieu},
            clear_dirty=lambda lieu: cas._meta._dirty.discard(lieu))
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas._meta._dirty, {corps_lieu})

    def test_valeur_texte_reste_du_texte(self):
        corps = self._corps(corps={'fichier': ''})
        self.assertIsInstance(corps['fichier'], str)
        self.assertTrue(corps['fichier'].startswith('%PDF-'))

    def test_import_tarif_et_fiche_pvsyst_recoivent_un_fichier_lisible(self):
        # CI #997 fuzz (2) — classeur xlsx (zip ouvrable) et fiche PVsyst.
        import io
        import zipfile
        for chemin in ('/api/django/stock/prix-fournisseurs/import-xlsx/',
                       '/api/django/achats/prix-fournisseurs/import-xlsx/'):
            corps = self._corps(chemin=chemin, corps={'fournisseur': 1, 'file': b''})
            self.assertTrue(zipfile.is_zipfile(io.BytesIO(corps['file'])), chemin)
            self.assertIn('xl/worksheets/sheet1.xml', zipfile.ZipFile(io.BytesIO(corps['file'])).namelist())
        corps = self._corps(chemin='/api/django/stock/fiches-techniques/importer-datasheet/',
                            corps={'produit': 1, 'file': ''})
        self.assertTrue(corps['file'].startswith('PVObject_=pvModule'))
        negatif = self._corps(chemin='/api/django/stock/prix-fournisseurs/import-xlsx/',
                              corps={'fournisseur': 1, 'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def test_releve_chantier_recoit_un_pdf_lu_par_le_stockage(self):
        # ERR-ENF11-FUZZ-INSTALLATIONS — ajouter-releve : ``store_attachment``
        # lit les octets magiques ; le champ ``phase`` du formulaire reste intact.
        chemin = '/api/django/installations/chantiers/{id}/ajouter-releve/'
        corps = self._corps(chemin=chemin, corps={'file': b'', 'phase': 'drone'})
        self.assertTrue(corps['file'].startswith(b'%PDF-'))
        self.assertEqual(corps['phase'], 'drone')
        negatif = self._corps(chemin=chemin, corps={'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def test_photo_produit_recoit_un_png(self):
        # CI #997 fuzz (4) - le serveur valide les octets magiques de la photo.
        chemin = '/api/django/stock/produits/{id}/photo/'
        corps = self._corps('POST', chemin, {'file': b''})
        self.assertTrue(corps['file'].startswith(b'\x89PNG'))
        self.assertEqual(self._corps('POST', chemin, {'file': b''}, mode='NEGATIVE')['file'], b'')
        self.assertEqual(self._corps('DELETE', chemin, {'file': b''})['file'], b'')

    def test_logo_et_signature_recoivent_une_image_lisible(self):
        # ENF11 (parametres) — le serveur lit les octets magiques de l'image
        # (PNG/JPEG/WebP) : un positif porte un PNG, un négatif reste intact.
        for chemin in ('/api/django/parametres/upload-logo/',
                       '/api/django/parametres/upload-signature/'):
            corps = self._corps(chemin=chemin, corps={'file': b''})
            self.assertTrue(corps['file'].startswith(b'\x89PNG\r\n\x1a\n'), chemin)
        negatif = self._corps(chemin='/api/django/parametres/upload-logo/',
                              corps={'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def test_import_generique_recoit_un_csv_lisible(self):
        # ENF11 imports : dry-run/commit lisent un CSV (en-têtes seuls) ; des
        # octets quelconques sont « Lecture impossible » (400).
        for chemin in ('/api/django/imports/dry-run/', '/api/django/imports/commit/',
                       '/api/django/imports/traductions/import/',
                       '/api/django/imports/feries/import/'):
            corps = self._corps('POST', chemin, {'file': b'', 'target': 'leads'})
            self.assertEqual(corps['file'], b'nom,email\r\n')
            self.assertEqual(corps['target'], 'leads')
        negatif = self._corps('POST', '/api/django/imports/dry-run/', {'file': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'')

    def test_import_uxviews_recoit_un_csv_lisible(self):
        # CI #1003 fuzz — import de vues / de favoris : un PNG est « Lecture du
        # fichier impossible » (400) ; un positif porte un CSV à en-têtes seuls.
        for chemin in ('/api/django/uxviews/saved-views/importer/',
                       '/api/django/uxviews/favoris/importer/'):
            corps = self._corps('POST', chemin, {'fichier': b'\x89PNG'})
            self.assertEqual(corps['fichier'], b'nom,email\r\n', chemin)
        negatif = self._corps('POST', '/api/django/uxviews/favoris/importer/',
                              {'fichier': b''}, mode='NEGATIVE')
        self.assertEqual(negatif['fichier'], b'')

    def test_releve_bancaire_dry_run_recoit_un_csv_lisible(self):
        # CI #1176 fuzz (aAVYqi) — un PNG est « Lecture du fichier
        # impossible » (400) ; un positif porte un CSV de relevé à en-têtes.
        chemin = '/api/django/ventes/paiements/import-releve/dry-run/'
        corps = self._corps('POST', chemin, {'file': b'\x89PNG'})
        self.assertEqual(corps['file'], b'date,libelle,montant\r\n')
        negatif = self._corps('POST', chemin, {'file': b'\x89PNG'}, mode='NEGATIVE')
        self.assertEqual(negatif['file'], b'\x89PNG')

    def test_negatif_autre_chemin_et_fichier_absent_intacts(self):
        self.assertEqual(self._corps(mode='NEGATIVE')['fichier'], b'')
        self.assertEqual(
            self._corps(chemin='/api/django/ged/documents/')['fichier'], b'')
        self.assertEqual(self._corps(corps={'code': '0'}), {'code': '0'})
        self.assertIsNone(self._corps(corps={'fichier': None})['fichier'])

    def test_depot_ged_recoit_un_fichier_du_format_lu(self):
        # CI #997 (2) : PDF au téléversement, PNG aux photos/scans séparés, CSV
        # (en-têtes + une ligne) à l'import en masse — champs de formulaire et
        # autres fichiers du corps intacts.
        ged = '/api/django/ged/documents/'
        for chemin, champ, debut in (
                (ged + 'televerser/', 'file', b'%PDF-'),
                (ged + 'assembler-photos/', 'photos', b'\x89PNG'),
                (ged + 'import-masse/', 'csv', b'nom,')):
            with self.subTest(chemin=chemin):
                corps = self._corps(
                    chemin=chemin,
                    corps={champ: [b''] if champ == 'photos' else b'',
                           'folder': 1, 'zip': b''})
                valeur = corps[champ][0] if champ == 'photos' else corps[champ]
                self.assertTrue(valeur.startswith(debut))
                self.assertEqual(corps['folder'], 1)
                self.assertEqual(corps['zip'], b'')

    def test_liste_de_fichiers_chaque_element_remplace(self):
        # ``files`` est une liste de fichiers (au moins un) : tous sont valides,
        # la liste garde sa longueur ; Binary garde son type.
        class Binary(str):
            def __new__(cls, data):
                return super().__new__(cls)

            def __init__(self, data):
                self.data = data

        premier = Binary(b'')
        for chemin, debut in (
                ('/api/django/ged/documents/scan-lot/', b'%PDF-'),
                ('/api/django/ged/documents/deposer-lot-scans-separe/',
                 b'\x89PNG')):
            with self.subTest(chemin=chemin):
                corps = self._corps(
                    chemin=chemin, corps={'files': [premier, b''],
                                          'folder': 1})
                self.assertEqual(len(corps['files']), 2)
                self.assertIs(corps['files'][0], premier)
                self.assertTrue(premier.data.startswith(debut))
                self.assertTrue(corps['files'][1].startswith(debut))

    def test_png_minimal_est_un_png_noir_valide(self):
        import struct
        import zlib
        png = self.hooks._PNG_MINIMAL
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
        pos, blocs = 8, {}
        while pos < len(png):
            n, = struct.unpack('>I', png[pos:pos + 4])
            type_, data = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + n]
            crc, = struct.unpack('>I', png[pos + 8 + n:pos + 12 + n])
            self.assertEqual(crc, zlib.crc32(type_ + data) & 0xffffffff)
            blocs[type_] = data
            pos += 12 + n
        self.assertEqual(struct.unpack('>II', blocs[b'IHDR'][:8]), (2, 2))
        # 2 lignes de (filtre 0 + 2 pixels RGB) toutes à zéro = pixels noirs.
        self.assertEqual(zlib.decompress(blocs[b'IDAT']), bytes(14))

    def test_depots_de_fichier_d_un_calepinage_recoivent_le_format_lu(self):
        # CI #997 (w4) : rendu de toiture, photo de site, fond de plan, carte
        # d'ombrage (PNG 8 px : image-document exige 8 px de côté au moins),
        # plan importé (DXF) et série météo (CSV) ; champs de formulaire
        # intacts, négatifs / GET / autres sous-ressources intacts.
        base = '/api/django/calepinage/calepinages/{id}/'
        attendus = (('roof-image/', 'image', b'\x89PNG'),
                    ('photos/', 'photo', b'\x89PNG'),
                    ('fond-plan/', 'fichier', b'\x89PNG'),
                    ('image-document/', 'fichier', b'\x89PNG'),
                    ('importer-plan/', 'fichier', b'0\nSECTION\n'),
                    ('meteo-fichier/', 'fichier', b'horodatage;gi_w_m2\r\n'))
        for suffixe, champ, debut in attendus:
            corps = self._corps(chemin=base + suffixe,
                                corps={champ: b'', 'genre': 'sol'})
            self.assertTrue(corps[champ].startswith(debut), suffixe)
            self.assertEqual(corps['genre'], 'sol', suffixe)
            negatif = self._corps(chemin=base + suffixe, mode='NEGATIVE',
                                  corps={champ: b''})
            self.assertEqual(negatif[champ], b'', suffixe)
            lecture = self._corps(chemin=base + suffixe, methode='GET',
                                  corps={champ: b''})
            self.assertEqual(lecture[champ], b'', suffixe)
        self.assertEqual(
            self._corps(chemin=base + 'photos/{photo_id}/calage/',
                        corps={'photo': b''})['photo'], b'')

    def test_png_de_capture_a_huit_pixels_et_dxf_de_plan_bien_forme(self):
        import struct
        png = self.hooks._PNG_CAPTURE
        entete = png[16:24]
        self.assertEqual(struct.unpack('>II', entete), (8, 8))
        lignes = self.hooks._DXF_PLAN.decode('ascii').split('\n')
        self.assertEqual(lignes[-1], '')
        lignes = lignes[:-1]
        # Un DXF est une suite de paires (code de groupe, valeur) ; le
        # contour fermé du calque « 0 » porte quatre sommets.
        self.assertEqual(len(lignes) % 2, 0)
        self.assertTrue(all(code.strip().lstrip('-').isdigit()
                            for code in lignes[0::2]))
        self.assertEqual(lignes.count('VERTEX'), 4)
        self.assertEqual(lignes[-2:], ['0', 'EOF'])

    def test_depot_ged_negatif_et_autres_operations_intacts(self):
        ged = '/api/django/ged/documents/'
        self.assertEqual(
            self._corps(chemin=ged + 'scan-lot/', mode='NEGATIVE',
                        corps={'files': [b'']})['files'], [b''])
        self.assertEqual(
            self._corps(chemin=ged + 'scan-lot/', methode='GET',
                        corps={'files': [b'']})['files'], [b''])
        self.assertEqual(
            self._corps(chemin=ged + '{id}/versions/',
                        corps={'files': [b'']})['files'], [b''])
        self.assertEqual(
            self._corps(chemin=ged + 'scan-lot/',
                        corps={'files': []})['files'], [])


class IdsFkParCheminTests(unittest.TestCase):
    """ENF11 (seed) — une règle par chemin donne les ids du BON modèle
    (``lot`` de stock = LotEntrepot), dans le corps ET la query."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'lot': [900, 901], 'activity_type': [3]},
            'fk_ids_chemin': [
                {'motif': r'^/api/django/stock/', 'champs': ['lot'],
                 'ids': [40], 'max': None},
                {'motif': r'/comparer/', 'champs': ['ids'],
                 'ids': [1, 2, 3], 'max': 2}]})

    def _appel(self, chemin, corps, mode='POSITIVE', query=None):
        cas = _cas(self.hooks, 'POST', chemin, corps, mode=mode)
        cas.query = query
        self.hooks.before_call(None, cas, {})
        return cas

    def test_regle_du_chemin_prioritaire_sur_la_table_par_nom(self):
        cas = self._appel('/api/django/stock/alertes-rappel/',
                          {'lot': 0, 'motif': 'x'})
        self.assertEqual(cas.body['lot'], 40)
        autre = self._appel('/api/django/ventes/x/', {'lot': 0})
        self.assertIn(autre.body['lot'], (900, 901))

    def test_regles_portail_client_lead_chantier_du_bon_modele(self):
        # ERR-ENF11-FUZZ-PORTAIL — le client, le lead et le chantier d'une
        # demande / d'un dépôt du portail viennent de LEUR modèle (le nom
        # ``chantier_id`` vise l'union de plusieurs modèles dans la table par
        # nom : un id réel d'un autre modèle donnait « Chantier inconnu(e) »).
        import importlib.util
        import re
        spec = importlib.util.spec_from_file_location(
            'prepare_fuzz_env_portail',
            ROOT / 'scripts' / 'fuzz' / 'prepare_fuzz_env.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        portail = {}
        for motif, champs, modele, _filtre, _maxi in module.REGLES_PAR_CHEMIN:
            if re.match(motif, '/api/django/portail/demandes-ticket-portail/'):
                for champ in champs:
                    portail[champ] = modele
        self.assertEqual(portail, {
            'client': 'crm.Client', 'client_id': 'crm.Client',
            'lead': 'crm.Lead', 'lead_id': 'crm.Lead',
            'chantier': 'installations.Installation',
            'chantier_id': 'installations.Installation'})
        self.assertFalse(any(
            re.match(motif, '/api/django/ventes/devis/')
            and 'chantier_id' in champs
            for motif, champs, *_ in module.REGLES_PAR_CHEMIN))

    def test_query_remplacee_entier_et_texte(self):
        cas = self._appel('/api/django/stock/x/', None,
                          query={'lot': 7, 'q': 'abc'})
        self.assertEqual(cas.query, {'lot': 40, 'q': 'abc'})
        cas = self._appel('/api/django/stock/x/', None, query={'lot': '7'})
        self.assertEqual(cas.query['lot'], '40')

    def test_query_texte_substituee_garde_le_type_genere(self):
        """CI #993 — phase coverage : la query part en chaînes mais le
        cliché typé dit entier ; la FK substituée doit rester un entier, sinon
        Schemathesis revalide ``'40'`` contre ``integer`` et bascule le cas
        positif en négatif (« accepted schema-violating request » sur 200)."""
        class Lieu(str, enum.Enum):
            QUERY = 'query'

        cas = _cas(self.hooks, 'GET', '/api/django/stock/x/')
        cas.query = {'lot': '7', 'q': 'abc', 'ids': ['7']}
        cas.meta.raw_containers = {
            Lieu.QUERY: {'lot': 7, 'q': 'abc', 'ids': [7]}}
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas.query['lot'], 40)
        self.assertEqual(cas.query['q'], 'abc')
        # Clé non substituée (règle absente) : forme fil intacte.
        self.assertEqual(cas.query['ids'], ['7'])

    def test_query_publiee_texte_recoit_un_entier_du_lien(self):
        """api-fuzz-full 27/10 (ENF11) — tranche 13, DELETE …/etiquettes/ :
        ``tag_id`` est publié ``type: string`` mais le lien stateful inféré y
        pose l'ENTIER ``id`` de ``GET /records/tags/`` ; substitué, il doit
        partir en texte (revalidé ``1`` contre ``string``, le cas positif
        basculait négatif : « accepted schema-violating request » sur 200)."""
        class Lieu(str, enum.Enum):
            QUERY = 'query'

        def parametre(nom, type_):
            return types.SimpleNamespace(name=nom, definition={
                'in': 'query', 'name': nom, 'schema': {'type': type_}})

        cas = _cas(self.hooks, 'DELETE', '/api/django/stock/x/{id}/tags/')
        cas.operation.query = [parametre('lot', 'string'),
                               parametre('q', 'string')]
        cas.query = {'lot': 7, 'q': 'abc'}
        cas.meta.raw_containers = {Lieu.QUERY: {'lot': 7, 'q': 'abc'}}
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas.query, {'lot': '40', 'q': 'abc'})
        # Publié ``integer`` : l'entier substitué reste un entier.
        cas = _cas(self.hooks, 'GET', '/api/django/stock/x/')
        cas.operation.query = [parametre('lot', 'integer')]
        cas.query = {'lot': 7}
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas.query, {'lot': 40})
        # api-fuzz-full 28/10 (tranche 11, ``object_id`` de GET
        # audit/security/) : id déjà réel, NON réécrit par le crochet — publié
        # ``string``, l'entier du lien part lui aussi en texte.
        cas = _cas(self.hooks, 'DELETE', '/api/django/stock/x/{id}/tags/')
        cas.operation.query = [parametre('lot', 'string')]
        cas.query = {'lot': 40}
        self.hooks.before_call(None, cas, {})
        self.assertEqual(cas.query, {'lot': '40'})

    def test_liste_bornee_et_objet_imbrique(self):
        cas = self._appel('/api/django/x/comparer/', {'ids': [7, 8, 9]})
        self.assertEqual(len(cas.body['ids']), 2)
        self.assertTrue(set(cas.body['ids']) <= {1, 2, 3})
        cas = self._appel('/api/django/records/activities/{id}/done/',
                          {'next': {'activity_type': 0}})
        self.assertEqual(cas.body['next']['activity_type'], 3)

    def test_cas_negatif_jamais_touche(self):
        cas = self._appel('/api/django/stock/x/', {'lot': 0},
                          mode='NEGATIVE', query={'lot': 7})
        self.assertEqual((cas.body['lot'], cas.query['lot']), (0, 7))


class CiblesRecordsTests(unittest.TestCase):
    """ENF11 (records) — ``{model, id}`` désigne une ligne réelle."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {},
            'cibles': {'crm.lead': [21, 22]}})

    def test_corps_et_query(self):
        cas = _cas(self.hooks, 'POST', '/api/django/records/tagged-items/',
                   {'model': 'crm.lead', 'id': 0, 'tag': 1})
        cas.query = {'model': 'sav.ticket', 'id': '5'}
        self.hooks.before_call(None, cas, {})
        self.assertIn(cas.body['id'], (21, 22))
        self.assertEqual(cas.query['model'], 'crm.lead')
        self.assertIn(cas.query['id'], ('21', '22'))


class IdsFkParCheminStockTests(unittest.TestCase):
    """ENF11 (stock/achats) — ``lot``/``retour`` du corps = ids du BON modèle
    sous /stock/ et /achats/ seulement ; ailleurs, comportement inchangé."""

    @classmethod
    def setUpClass(cls):
        regle = {'motif': r'^/api/django/(stock|achats)/', 'champs': ['lot'],
                 'ids': [40]}
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'lot': [900, 901]},
            'fk_ids_chemin': [regle, dict(regle, champs=['retour'], ids=[7])]})

    def _corps(self, chemin, corps, mode='POSITIVE'):
        cas = _cas(self.hooks, 'POST', chemin, corps, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas.body

    def test_stock_et_achats(self):
        self.assertEqual(self._corps('/api/django/stock/alertes-rappel/',
                                     {'lot': 0})['lot'], 40)
        self.assertEqual(self._corps('/api/django/achats/x/',
                                     {'retour': 3})['retour'], 7)

    def test_autres_routes_et_negatif_inchanges(self):
        self.assertIn(self._corps('/api/django/core/x/', {'lot': 0})['lot'],
                      (900, 901))
        self.assertEqual(self._corps('/api/django/core/x/',
                                     {'retour': 3})['retour'], 3)
        self.assertEqual(self._corps('/api/django/stock/x/', {'lot': 0},
                                     mode='NEGATIVE')['lot'], 0)


def _charger_inventaire():
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('inventorier_ids_chemin', None)
        return importlib.import_module('inventorier_ids_chemin')
    finally:
        sys.path.pop(0)


class InventaireIdsTests(unittest.TestCase):
    def setUp(self):
        self.inv = _charger_inventaire()

    def test_liste_paginee_et_nue(self):
        self.assertEqual(
            self.inv.parser_ids({'count': 2, 'results': [{'id': 3}, {'id': 5}]}),
            [3, 5])
        self.assertEqual(self.inv.parser_ids([{'id': 'u1'}, {'pk': 2}, {}]),
                         ['u1', 2])
        self.assertEqual(self.inv.parser_ids({'detail': 'x'}), [])
        self.assertEqual(self.inv.parser_ids([{'id': True}, 5]), [])

    def test_collections_et_inventaire(self):
        doc = {'paths': {
            '/api/django/a/': {'get': {}},
            '/api/django/a/{id}/': {'get': {}},
            '/api/django/a/{id}/sub/': {'get': {}},
            '/api/django/b/': {'post': {}},
            '/api/django/b/{pk}/': {'get': {}},
            '/api/django/c/{token}/': {'get': {}}}}
        self.assertEqual(self.inv.collections_du_schema(doc),
                         ['/api/django/a/'])
        table = self.inv.inventorier(
            doc, lambda p: {'results': [{'id': 9}]})
        self.assertEqual(table, {'/api/django/a/': [9]})

    def test_lecture_parallele_meme_table(self):
        doc = {'paths': {}}
        for k in range(12):
            doc['paths'][f'/api/django/r{k:02d}/'] = {'get': {}}
            doc['paths'][f'/api/django/r{k:02d}/{{id}}/'] = {'get': {}}

        def lire(prefixe):
            rang = int(prefixe.rstrip('/')[-2:])
            return None if rang % 5 == 0 else {'results': [{'id': rang}]}

        seq = self.inv.inventorier(doc, lire)
        self.assertEqual(len(seq), 9)
        for fils in (2, 3, 8):
            with self.subTest(fils=fils):
                par = self.inv.inventorier(doc, lire, workers=fils)
                self.assertEqual(par, seq)
                self.assertEqual(list(par), list(seq))

    def test_job_pr_inventorie_comme_le_nocturne(self):
        # ENF11 — `api-fuzz-pr` ne posait jamais FUZZ_IDS_FILE : ses cas
        # positifs gardaient des `{id}` aléatoires. Même script que
        # api-fuzz-full, sur le schéma FUZZÉ, AVANT `schemathesis run`.
        ci = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(
            encoding='utf-8')
        debut = ci.index('\n  api-fuzz-pr:\n')
        fin = ci.index('\n  backend-tests:\n', debut)
        job = ci[debut:fin]
        etape = job.index('scripts/fuzz/inventorier_ids_chemin.py')
        self.assertIn('--schema openapi-fuzz.json', job[etape:etape + 200])
        self.assertLess(job.index('api_fuzz_scope.py schema'), etape)
        self.assertLess(job.index('FUZZ_IDS_FILE=$FUZZ_IDS_FILE'), etape)
        self.assertLess(etape, job.index('schemathesis run '))
        plein = (ROOT / '.github' / 'workflows' / 'api-fuzz-full.yml'
                 ).read_text(encoding='utf-8')
        for texte in (job, plein):
            self.assertIn('echo "FUZZ_IDS_FILE=$FUZZ_IDS_FILE" >> '
                          '"$GITHUB_ENV"', texte)


def _charger_portee():
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('api_fuzz_scope', None)
        return importlib.import_module('api_fuzz_scope')
    finally:
        sys.path.pop(0)


def _doc_crud():
    reponse_201 = {'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/Produit'}}}}
    return {
        'openapi': '3.0.3',
        'paths': {
            '/api/django/stock/produits/': {
                'get': {'operationId': 'liste'},
                'post': {'operationId': 'cree',
                         'responses': {'201': reponse_201}}},
            '/api/django/stock/produits/{id}/': {
                'get': {'operationId': 'lit'},
                'delete': {'operationId': 'supprime'}},
            '/api/django/stock/produits/{id}/archiver/': {
                'post': {'operationId': 'archive'}},
            '/api/django/stock/produits/export/': {
                'get': {'operationId': 'exporte'}},
            '/api/django/ventes/devis/': {
                'post': {'operationId': 'cree_devis',
                         'responses': {'201': {'content': {}}}}},
            '/api/django/ventes/devis/{id}/': {
                'get': {'operationId': 'lit_devis'}},
            '/api/v1/stock/produits/': {'get': {'operationId': 'v1'}},
        },
        'components': {'schemas': {'Produit': {
            'type': 'object', 'properties': {'id': {'type': 'integer'}}}}},
    }


def _refuse(_chemin):
    raise LookupError(_chemin)


class PorteePRTests(unittest.TestCase):
    """ENF11 — sous-ensemble PR : fichiers modifiés -> opérations fuzzées."""

    @classmethod
    def setUpClass(cls):
        cls.m = _charger_portee()

    def test_fichiers_d_app_donnent_le_paquet(self):
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/ventes/views/facture.py',
            'backend/django_core/apps/stock/serializers.py',
            'backend/django_core/apps/stock/migrations/0101_x.py',
        ]), ['apps.stock', 'apps.ventes'])

    def test_tests_docs_et_hors_backend_ignores(self):
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/ventes/tests/test_x.py',
            'backend/django_core/apps/crm/tests_parsers.py',
            'backend/django_core/apps/sav/README.md',
            'frontend/src/App.jsx',
            'docs/PLAN.md',
            '',
        ]), [])

    def test_plateforme_et_harnais_donnent_core_et_authentication(self):
        for fichier in ('backend/django_core/erp_agentique/urls.py',
                        'backend/django_core/requirements.txt',
                        'scripts/fuzz/schemathesis_hooks.py',
                        'schemathesis.toml'):
            with self.subTest(fichier=fichier):
                self.assertEqual(self.m.proprietaires_modifies([fichier]),
                                 ['authentication', 'core'])
        self.assertEqual(self.m.proprietaires_modifies(
            ['backend/django_core/core/exceptions.py']), ['core'])
        self.assertEqual(self.m.proprietaires_modifies(
            ['backend/django_core/authentication/views.py']), ['authentication'])

    def test_contrats_et_dette_gelee_n_elargissent_pas_le_perimetre(self):
        # VNT M0 (12/10/2026) : un échantillon de contrat (PACT10) et la dette
        # gelée ne changent aucun comportement HTTP ; les compter relançait
        # crm/core/authentication à chaque tour (treadmill de gels).
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/crm/contract_samples/lead_devis_ligne.json',
            'backend/django_core/apps/ventes/contract_samples/README.md',
            'scripts/fuzz/api_fuzz_dette.txt',
        ]), [])
        self.assertEqual(self.m.proprietaires_modifies([
            'scripts/fuzz/api_fuzz_dette.txt',
            'backend/django_core/apps/ventes/domain/facturation_ops.py',
        ]), ['apps.ventes'])

    def test_proprietaire_du_module(self):
        self.assertEqual(self.m.proprietaire_du_module('apps.stock.views.produit'),
                         'apps.stock')
        self.assertEqual(self.m.proprietaire_du_module('core.views'), 'core')
        self.assertEqual(self.m.proprietaire_du_module(
            'authentication.views'), 'authentication')
        self.assertIsNone(self.m.proprietaire_du_module(
            'rest_framework_simplejwt.views'))
        self.assertIsNone(self.m.proprietaire_du_module(None))

    def test_modules_de_vue_essaie_les_valeurs_jusqu_a_resolution(self):
        def resoudre(chemin):
            if '00000000' not in chemin:
                raise LookupError(chemin)
            return 'apps.ged.views'
        self.assertEqual(self.m.modules_de_vue('/api/django/ged/x/{uuid}/', resoudre),
                         ('apps.ged.views',))
        self.assertEqual(self.m.modules_de_vue('/api/django/ged/x/{uuid}/', _refuse), ())

    def test_urlconf_traverse_compte_comme_proprietaire(self):
        # facturation monte des vues définies dans ventes (re-export).
        def resoudre(chemin):
            return ('apps.ventes.views', 'erp_agentique.urls', 'apps.facturation.urls')
        doc = {'paths': {'/api/django/facturation/factures/': {'get': {'operationId': 'f'}}}}
        sortie, _ = self.m.preparer_schema(doc, ['apps.facturation'], resoudre)
        self.assertEqual(list(sortie['paths']), ['/api/django/facturation/factures/'])
        sortie, _ = self.m.preparer_schema(doc, ['apps.stock'], resoudre)
        self.assertEqual(sortie['paths'], {})

    def test_schema_filtre_par_proprietaire_sans_miroir_v1(self):
        modules = {'stock': 'apps.stock.views', 'ventes': 'apps.ventes.views'}

        def resoudre(chemin):
            return modules[chemin.split('/')[3]]
        sortie, stats = self.m.preparer_schema(_doc_crud(), ['apps.stock'], resoudre)
        self.assertEqual(sorted(sortie['paths']), [
            '/api/django/stock/produits/',
            '/api/django/stock/produits/export/',
            '/api/django/stock/produits/{id}/',
            '/api/django/stock/produits/{id}/archiver/'])
        self.assertEqual(stats['operations'], 6)
        self.assertIn('components', sortie)

    def test_sans_proprietaire_tout_est_garde_sauf_v1(self):
        sortie, _ = self.m.preparer_schema(_doc_crud())
        self.assertNotIn('/api/v1/stock/produits/', sortie['paths'])
        self.assertIn('/api/django/ventes/devis/{id}/', sortie['paths'])

    def test_liens_crud_declares_depuis_le_201_avec_id(self):
        doc = _doc_crud()
        sortie, stats = self.m.preparer_schema(doc)
        liens = sortie['paths']['/api/django/stock/produits/']['post'][
            'responses']['201']['links']
        self.assertEqual(sorted(liens), [
            'DELETE /api/django/stock/produits/{id}/',
            'GET /api/django/stock/produits/{id}/',
            'POST /api/django/stock/produits/{id}/archiver/'])
        self.assertEqual(liens['GET /api/django/stock/produits/{id}/'], {
            'operationId': 'lit', 'parameters': {'id': '$response.body#/id'}})
        # 201 sans `id` (devis) : aucun lien ; l'action de collection
        # `export/` n'est pas un élément : aucun lien.
        self.assertNotIn('links', sortie['paths']['/api/django/ventes/devis/'][
            'post']['responses']['201'])
        self.assertEqual(stats['liens'], 3)
        # Le document d'entrée n'est jamais modifié.
        self.assertNotIn('links', doc['paths']['/api/django/stock/produits/'][
            'post']['responses']['201'])

    def test_lien_existant_jamais_ecrase(self):
        doc = _doc_crud()
        doc['paths']['/api/django/stock/produits/']['post']['responses']['201'][
            'links'] = {'GET /api/django/stock/produits/{id}/': {'operationId': 'x'}}
        sortie, stats = self.m.preparer_schema(doc)
        self.assertEqual(sortie['paths']['/api/django/stock/produits/']['post'][
            'responses']['201']['links']['GET /api/django/stock/produits/{id}/'],
            {'operationId': 'x'})
        self.assertEqual(stats['liens'], 2)

    def test_verdict_rouge_sur_constat_hors_dette_seulement(self):
        rapport = {'failures': [
            {'title': 'Server error', 'operations': ['GET /a/', 'POST /b/']},
            {'title': 'Undocumented HTTP status code', 'operations': ['GET /a/']},
        ]}
        nouveaux, revus = self.m.verdict(rapport, {'Server error|GET /a/'})
        self.assertEqual(nouveaux, ['Server error|POST /b/',
                                    'Undocumented HTTP status code|GET /a/'])
        self.assertEqual(revus, ['Server error|GET /a/'])
        self.assertEqual(self.m.verdict({'failures': []}, set()), ([], []))

    def test_erreur_du_moteur_toujours_rouge_jamais_gelable(self):
        # Rapport JSON Schemathesis 4.28 : `errors: [{title, count}]`, sans
        # opération — une opération en erreur n'a pas été testée.
        rapport = {'failures': [], 'errors': [{'title': "Unsupported type: 'Binary'",
                                               'count': 1}],
                   'operations': {'errored': 1}}
        nouveaux, _ = self.m.verdict(
            rapport, {"Erreur du moteur|Unsupported type: 'Binary'"})
        self.assertEqual(nouveaux, ["Erreur du moteur|Unsupported type: 'Binary'"])
        # Compteur seul (liste absente) : rouge quand même.
        nouveaux, _ = self.m.verdict({'operations': {'errored': 2}}, set())
        self.assertEqual(nouveaux, ['Erreur du moteur|2 opération(s) en erreur'])

    def test_run_inexploitable_rouge(self):
        self.assertEqual(self.m.verdict({'complete': False, 'stop_reason': 'interrupted'},
                                        set())[0],
                         ['Run incomplet|stop_reason=interrupted'])
        self.assertEqual(self.m.verdict({'auth': {'reauth_broke': True}}, set())[0],
                         ['Authentification perdue|reauth_broke'])
        # Fin normale ou plafond --max-time : run exploitable.
        for raison in ('completed', 'max_time'):
            rapport = {'complete': True, 'stop_reason': raison,
                       'auth': {'reauth_broke': False}, 'errors': [],
                       'operations': {'errored': 0}}
            self.assertEqual(self.m.verdict(rapport, set()), ([], []))

    def test_resume_d_alerte_nomme_les_regressions(self):
        texte = self.m.resume_markdown(['Server error|POST /b/'], ['Server error|GET /a/'])
        self.assertIn('1 constat(s) api-fuzz HORS de la dette gelée', texte)
        self.assertIn('- `Server error|POST /b/`', texte)
        self.assertIn('Aucune régression', self.m.resume_markdown([], ['x']))
        long = self.m.resume_markdown([f'Server error|GET /{i}/' for i in range(70)], [])
        self.assertIn('… et 10 autre(s)', long)

    def test_dette_versionnee_bien_formee(self):
        # ENF11 — une dette VIDE est l'état cible (D-ENF11-CRENEAU-400 a soldé
        # la dernière ligne) : seule la forme des lignes restantes est vérifiée.
        dette = self.m.charger_dette()
        self.assertIsInstance(dette, set)
        for ligne in dette:
            with self.subTest(ligne=ligne):
                titre, _, operation = ligne.partition('|')
                methode, _, chemin = operation.partition(' ')
                self.assertTrue(titre)
                self.assertIn(methode, {'GET', 'POST', 'PUT', 'PATCH', 'DELETE',
                                        'HEAD', 'OPTIONS', 'TRACE'})
                self.assertTrue(chemin.startswith('/'))

    def test_commande_verdict_code_retour(self):
        with tempfile.TemporaryDirectory() as tmp:
            rapport = Path(tmp) / 'r.json'
            dette = Path(tmp) / 'd.txt'
            rapport.write_text(json.dumps({'failures': [
                {'title': 'Server error', 'operations': ['GET /a/']}]}),
                encoding='utf-8')
            dette.write_text('# raison\nServer error|GET /a/\n', encoding='utf-8')
            args = ['verdict', '--rapport', str(rapport), '--dette', str(dette)]
            self.assertEqual(self.m.main(args), 0)
            dette.write_text('# raison\n', encoding='utf-8')
            self.assertEqual(self.m.main(args), 1)
            resume = Path(tmp) / 'alerte.md'
            self.assertEqual(self.m.main(args + ['--resume', str(resume)]), 1)
            self.assertIn('Server error|GET /a/', resume.read_text(encoding='utf-8'))


class ConfigSchemathesisTests(unittest.TestCase):
    """CI #993 (KAogBl) — le 428 d'ACAL316 est un REJET pour
    ``missing_required_header``, sur la SEULE opération ``layout``."""

    def test_428_admis_pour_l_en_tete_if_match_du_seul_layout(self):
        import tomllib

        with open(ROOT / 'schemathesis.toml', 'rb') as fh:
            config = tomllib.load(fh)
        visees = [op for op in config['operations']
                  if 'missing_required_header' in op.get('checks', {})]
        self.assertEqual(len(visees), 1)
        op = visees[0]
        # Un SEUL filtre (deux filtres include se combinent en OU).
        self.assertEqual(
            {k for k in op if k.startswith(('include-', 'exclude-'))},
            {'include-name'})
        self.assertEqual(op['include-name'],
                         'POST /api/django/calepinage/calepinages/{id}/layout/')
        self.assertNotIn('enabled', op)
        attendus = op['checks']['missing_required_header']['expected-statuses']
        # Les défauts de Schemathesis 4.28 gardés, 428 ajouté.
        self.assertEqual(sorted(attendus),
                         [400, 401, 403, 406, 415, 422, 428])

    def test_410_admis_pour_la_seule_route_retiree_du_portail_sav(self):
        # ERR-ENF11-FUZZ-SAV — ASAV27 : la route retirée répond 410 voulu.
        import tomllib

        with open(ROOT / 'schemathesis.toml', 'rb') as fh:
            config = tomllib.load(fh)
        visees = [op for op in config['operations']
                  if 'positive_data_acceptance' in op.get('checks', {})]
        # Deux routes nommées, jamais un motif : la route retirée du portail
        # SAV (410) et le créneau hors grille (400, D-ENF11-CRENEAU-400).
        self.assertEqual(sorted(op.get('include-name') for op in visees), [
            'POST /api/django/public/stock/portail-fournisseur/{token}/reserver-creneau/',
            'POST /api/django/sav/portail/tickets/'])
        op = next(o for o in visees
                  if o['include-name'] == 'POST /api/django/sav/portail/tickets/')
        self.assertEqual(
            {k for k in op if k.startswith(('include-', 'exclude-'))},
            {'include-name'})
        self.assertNotIn('enabled', op)
        attendus = op['checks']['positive_data_acceptance']['expected-statuses']
        # Les défauts de Schemathesis 4.28 gardés, 410 ajouté.
        self.assertEqual(sorted(str(s) for s in attendus),
                         ['2xx', '401', '403', '404', '409', '410', '429',
                          '5xx'])

    def test_400_admis_pour_le_seul_creneau_hors_grille(self):
        # D-ENF11-CRENEAU-400 — refus hors grille (ASTK191) = règle métier.
        import tomllib

        with open(ROOT / 'schemathesis.toml', 'rb') as fh:
            config = tomllib.load(fh)
        nom = ('POST /api/django/public/stock/portail-fournisseur/{token}/'
               'reserver-creneau/')
        visees = [op for op in config['operations']
                  if 'positive_data_acceptance' in op.get('checks', {})
                  and op.get('include-name') == nom]
        self.assertEqual(len(visees), 1)
        op = visees[0]
        self.assertEqual(
            {k for k in op if k.startswith(('include-', 'exclude-'))},
            {'include-name'})
        self.assertNotIn('enabled', op)
        attendus = op['checks']['positive_data_acceptance']['expected-statuses']
        # Les défauts de Schemathesis 4.28 gardés, 400 ajouté (et rien d'autre).
        self.assertEqual(sorted(str(s) for s in attendus),
                         ['2xx', '400', '401', '403', '404', '409', '429',
                          '5xx'])

    def test_503_admis_pour_la_seule_route_scan_carte_sans_cle_ocr(self):
        # CI #1001 (fuzz crm) — XSAL8 : sans clé OCR, 503 douce voulue.
        import tomllib

        with open(ROOT / 'schemathesis.toml', 'rb') as fh:
            config = tomllib.load(fh)
        visees = [op for op in config['operations']
                  if 'not_a_server_error' in op.get('checks', {})]
        self.assertEqual(len(visees), 1)
        op = visees[0]
        self.assertEqual(
            {k for k in op if k.startswith(('include-', 'exclude-'))},
            {'include-name'})
        self.assertEqual(op['include-name'],
                         'POST /api/django/crm/leads/scan-carte/')
        self.assertNotIn('enabled', op)
        attendus = op['checks']['not_a_server_error']['expected-statuses']
        # Les défauts de Schemathesis 4.28 gardés, 503 ajouté.
        self.assertEqual(sorted(str(s) for s in attendus),
                         ['2xx', '3xx', '4xx', '503'])


if __name__ == '__main__':
    unittest.main()


class PartageChemins(unittest.TestCase):
    """CI #997 — `api_fuzz_scope.py schema --shard i/N` : partition déterministe,
    exhaustive et disjointe des chemins (plus d'échantillon aléatoire)."""

    def setUp(self):
        import importlib
        self.scope = importlib.import_module("scripts.fuzz.api_fuzz_scope")

    def test_union_disjointe_et_deterministe(self):
        chemins = [f"/api/django/x/{k}/" for k in range(23)]
        tranches = [self.scope.partager_chemins(chemins, f"{i}/4") for i in range(4)]
        self.assertEqual(set().union(*tranches), set(chemins))
        for i in range(4):
            for j in range(i + 1, 4):
                self.assertFalse(tranches[i] & tranches[j], (i, j))
        self.assertEqual(tranches[1], self.scope.partager_chemins(list(reversed(chemins)), "1/4"))
        self.assertEqual(self.scope.partager_chemins(chemins, None), set(chemins))

    def test_tranche_invalide_refusee(self):
        with self.assertRaises(ValueError):
            self.scope.partager_chemins(["/a/"], "4/4")
        with self.assertRaises(ValueError):
            self.scope.partager_chemins(["/a/"], "0/0")

    def test_preparer_schema_tranche(self):
        doc = {"openapi": "3.0.3", "paths": {
            f"/api/django/x/{k}/": {"get": {"responses": {"200": {"description": "ok"}}}}
            for k in range(6)}, "components": {}}
        total = 0
        for i in range(3):
            sortie, stats = self.scope.preparer_schema(doc, None, None, shard=f"{i}/3")
            self.assertEqual(stats["chemins"], 2)
            total += stats["operations"]
        self.assertEqual(total, 6)
