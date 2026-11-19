"""AG1 — Tests du registre d'actions agentiques.

Couvre :
- :class:`AgentAction` valide ses champs (risk autorisé, key obligatoire) ;
- :func:`register` est unique (refuse une key en double) ;
- :func:`for_user` filtre par permission ERP (rôle de la société) ;
- un superuser voit tout, un anonyme rien, une action sans permission est
  ouverte à tout authentifié.
"""
import ast
import re
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.roles.models import Role
from apps.agent.registry import (
    AgentAction, RISK_INTERNAL, RISK_OUTWARD, register, unregister,
    all_actions, for_user,
)

User = get_user_model()


class AgentActionDataclassTest(TestCase):
    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='k', label='L', description='d',
                        endpoint='/x/', risk='bogus')

    def test_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            AgentAction(key='', label='L', description='d', endpoint='/x/')

    def test_as_dict_shape(self):
        a = AgentAction(
            key='demo.read', label='Lire', description='Lit un truc',
            endpoint='/api/x/', method='get', required_permission='stock_voir',
            risk=RISK_OUTWARD, confirm_summary='résumé')
        d = a.as_dict()
        self.assertEqual(d['key'], 'demo.read')
        self.assertEqual(d['method'], 'GET')  # normalisé en majuscules
        self.assertEqual(d['required_permission'], 'stock_voir')
        self.assertEqual(d['risk'], RISK_OUTWARD)
        self.assertEqual(d['confirm_summary'], 'résumé')
        # COP-G7 — le catalogue porte la carte, le lot et les objets nommés.
        self.assertEqual((d['carte'], d['lot'], d['objets']), (None, None, {}))
        b = AgentAction(
            key='demo.carte', label='L', description='d', endpoint='/x/{id}/',
            carte='document', lot='copilote', objets={'id': 'devis'})
        self.assertEqual(
            {k: b.as_dict()[k] for k in ('carte', 'lot', 'objets')},
            {'carte': 'document', 'lot': 'copilote', 'objets': {'id': 'devis'}})
        # ``objets`` est une copie : le catalogue servi ne mute pas l'action.
        b.as_dict()['objets']['id'] = 'facture'
        self.assertEqual(b.objets, {'id': 'devis'})

    def test_carte_lot_et_objets_hors_ensemble_refuses(self):
        for champ, valeur in (('carte', 'inconnue'), ('lot', 'tous'),
                              ('objets', {'id': 'ligne'})):
            with self.assertRaises(ValueError, msg=champ):
                AgentAction(key='k', label='L', description='d',
                            endpoint='/x/', **{champ: valeur})


class RegisterUniquenessTest(TestCase):
    def tearDown(self):
        unregister('tmp.unique')

    def test_duplicate_key_rejected(self):
        a = AgentAction(key='tmp.unique', label='X', description='d',
                        endpoint='/x/')
        register(a)
        try:
            with self.assertRaises(ValueError):
                register(AgentAction(key='tmp.unique', label='Y',
                                     description='d2', endpoint='/y/'))
        finally:
            unregister('tmp.unique')

    def test_register_appears_in_all_actions(self):
        register(AgentAction(key='tmp.unique', label='X', description='d',
                             endpoint='/x/', risk=RISK_INTERNAL))
        keys = [a.key for a in all_actions()]
        self.assertIn('tmp.unique', keys)


class ForUserFilterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Agent Co', slug='agent-co')
        # Rôle « lecture seule » : ne porte que crm_voir.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « vendeur » : peut créer des devis + PDF.
        self.sales_role = Role.objects.create(
            company=self.company, nom='Vendeur',
            permissions=['ventes_creer', 'ventes_pdf', 'crm_voir'])
        self.sales = User.objects.create_user(
            username='sales', password='x', role=self.sales_role,
            company=self.company)
        self.superuser = User.objects.create_superuser(
            username='root', password='x')

    def test_readonly_user_sees_only_permitted(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertIn('crm.lead.list', keys)              # crm_voir → autorisé
        self.assertNotIn('ventes.devis.creer_auto', keys)  # ventes_creer manquant
        self.assertNotIn('ventes.devis.generer_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_sales_user_sees_sales_actions(self):
        keys = {a.key for a in for_user(self.sales)}
        self.assertIn('ventes.devis.creer_auto', keys)
        self.assertIn('ventes.devis.generer_pdf', keys)
        self.assertIn('crm.lead.list', keys)
        self.assertNotIn('stock.produit.delete', keys)  # stock_supprimer manquant

    def test_superuser_sees_everything(self):
        keys = {a.key for a in for_user(self.superuser)}
        # COP-G1 — le superuser est administrateur : copilote allumé par défaut
        # (``admins``), donc les actions du lot « herite » lui sont masquées.
        builtin = {a.key for a in all_actions() if a.lot != 'herite'}
        self.assertTrue(builtin.issubset(keys))

    def test_action_without_permission_open_to_authenticated(self):
        a = AgentAction(key='tmp.open', label='Ouvert', description='d',
                        endpoint='/open/', required_permission=None)
        register(a)
        try:
            self.assertIn('tmp.open', {x.key for x in for_user(self.readonly)})
        finally:
            unregister('tmp.open')

    def test_anonymous_sees_nothing(self):
        class _Anon:
            is_authenticated = False
        self.assertEqual(for_user(_Anon()), [])
        self.assertEqual(for_user(None), [])


class InterrupteurCopiloteTest(TestCase):
    """COP-G1 — ``ASSISTANT_COPILOTE`` (aucun | admins | tous ; inconnu =
    aucun) : une action ``lot='copilote'`` n'est servie que si le copilote est
    allumé pour le compte, une action ``lot='herite'`` que s'il est éteint,
    une action sans lot toujours."""

    def setUp(self):
        company = Company.objects.create(nom='Copilote Co', slug='copilote-co')
        admin_role = Role.objects.create(
            company=company, nom='Administrateur',
            permissions=['roles_gerer', 'crm_voir'])
        sales_role = Role.objects.create(
            company=company, nom='Commercial', permissions=['crm_voir'])
        self.admin = User.objects.create_user(
            username='cop_admin', password='x', role=admin_role,
            company=company)
        self.commercial = User.objects.create_user(
            username='cop_sales', password='x', role=sales_role,
            company=company)
        for cle, lot in (('tmp.cop.copilote', 'copilote'),
                         ('tmp.cop.herite', 'herite'),
                         ('tmp.cop.sans_lot', None)):
            register(AgentAction(key=cle, label=cle, description='d',
                                 endpoint='/x/', lot=lot))
            self.addCleanup(unregister, cle)

    def _servies(self, user, valeur):
        with self.settings(ASSISTANT_COPILOTE=valeur):
            return {a.key for a in for_user(user)
                    if a.key.startswith('tmp.cop.')}

    def test_tous_allume_pour_admin_et_commercial(self):
        attendu = {'tmp.cop.copilote', 'tmp.cop.sans_lot'}
        self.assertEqual(self._servies(self.admin, 'tous'), attendu)
        self.assertEqual(self._servies(self.commercial, 'tous'), attendu)

    def test_admins_allume_seulement_pour_admin(self):
        self.assertEqual(self._servies(self.admin, 'admins'),
                         {'tmp.cop.copilote', 'tmp.cop.sans_lot'})
        self.assertEqual(self._servies(self.commercial, 'admins'),
                         {'tmp.cop.herite', 'tmp.cop.sans_lot'})

    def test_aucun_et_valeur_inconnue_eteignent_pour_tous(self):
        for valeur in ('aucun', 'TOUS_', 'oui', ''):
            for user in (self.admin, self.commercial):
                self.assertEqual(self._servies(user, valeur),
                                 {'tmp.cop.herite', 'tmp.cop.sans_lot'},
                                 (valeur, user.username))

    def test_valeur_insensible_a_la_casse_et_aux_blancs(self):
        self.assertIn('tmp.cop.copilote', self._servies(self.admin, ' Admins '))

    def test_description_hors_lot_ne_cite_aucun_outil_du_lot_copilote(self):
        """Critique finale F1 — une action servie à TOUS ne renvoie jamais le
        modèle vers un outil que le compte peut ne pas avoir (copilote éteint) :
        registre réel de toutes les apps, aucune description hors lot ne cite
        la clé d'une action du lot « copilote »."""
        actions = list(all_actions())
        du_lot = sorted(a.key for a in actions if a.lot == 'copilote')
        self.assertIn('crm.suivi.preparer_touche', du_lot)
        fautes = {a.key: [cle for cle in du_lot if cle in a.description]
                  for a in actions if a.lot != 'copilote'}
        self.assertEqual({k: v for k, v in fautes.items() if v}, {})

    def test_ged_docqa_admin_copilote_allume_seulement(self):
        """FND11 (D-W2-5) — l'outil qui rend le texte des documents : absent
        pour un commercial et pour TOUT compte copilote éteint (la seule
        exception nommée à « éteint = identique ») ; présent pour un
        administrateur copilote allumé."""
        def sert(user, valeur):
            with self.settings(ASSISTANT_COPILOTE=valeur):
                return 'ged.docqa.retrieve' in {a.key for a in for_user(user)}
        self.assertTrue(sert(self.admin, 'admins'))
        self.assertFalse(sert(self.commercial, 'tous'))
        self.assertFalse(sert(self.admin, 'aucun'))
        self.assertFalse(sert(self.commercial, 'aucun'))

    def test_defaut_du_reglage_est_admins(self):
        from django.conf import settings
        self.assertEqual(getattr(settings, 'ASSISTANT_COPILOTE', None), 'admins')

    def test_confirmation_suit_la_meme_regle(self):
        """Une action du lot ``copilote`` éteint pour le compte est refusée par
        l'endpoint de confirmation (403), comme absente du catalogue."""
        from rest_framework.test import APIClient

        from apps.agent.services import calculer_preuve_confirmation

        def confirmer(user):
            client = APIClient()
            client.force_authenticate(user)
            corps = {'action_key': 'tmp.cop.copilote', 'risk_level': 'internal',
                     'inputs': {}, 'preuve': calculer_preuve_confirmation(
                         secret='s', action_key='tmp.cop.copilote',
                         company_id=user.company_id, user_id=user.pk,
                         inputs={}, object_id=None)}
            return client.post('/api/django/agent/logs/confirmer/', corps,
                               format='json').status_code

        with self.settings(ASSISTANT_COPILOTE='admins', AGENT_HMAC_SECRET='s'):
            self.assertEqual(confirmer(self.commercial), 403)
            self.assertEqual(confirmer(self.admin), 201)


def _feuilles(garde):
    """Aplatit une garde composée DRF (``A | B`` : ``op1`` / ``op2``)."""
    if hasattr(garde, 'op1') and hasattr(garde, 'op2'):
        return _feuilles(garde.op1) + _feuilles(garde.op2)
    return [garde]


def _chemin_de_l_action(action):
    """Chemin concret de la route d'une action. AIC99 — un paramètre de chemin
    à valeurs fermées (``enum``) prend sa PREMIÈRE valeur (la route la plus
    stricte, déclarée en tête) ; un id, 1."""
    entrees = (action.inputs or {}).get('properties', {})
    return re.sub(r'\{([a-z_]+)\}', lambda m: str(
        (entrees.get(m.group(1), {}).get('enum') or ['1'])[0]), action.endpoint)


def _gardes_lues(action):
    """Gardes RÉELLES de la route d'une action du catalogue, lues sur la vue
    qui la sert (résolution d'URL + ``get_permissions()``, rien n'est exécuté) :
    ``(codes, conditionnels, admin, modules)`` — codes de grille
    (``HasPermissionOrLegacy`` / ``HasPermission`` / ``DroitDeLaGrille``) qui
    jouent toujours, ceux qui ne jouent que selon le corps, garde palier
    administrateur, modules de droits des gardes « module »
    (``IsResponsableOrAdmin``, ``LectureDuModule``)."""
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory

    from authentication.permissions import (
        IsAdminRole, IsResponsableOrAdmin, LectureDuModule, module_de_la_vue)

    chemin = _chemin_de_l_action(action)
    trouve = resolve(chemin)
    cls = getattr(trouve.func, 'cls', None)
    vue = cls(**getattr(trouve.func, 'initkwargs', {}))
    vue.request = APIRequestFactory().generic(action.method.upper(), chemin)
    vue.kwargs, vue.format_kwarg = trouve.kwargs, None
    actions = getattr(trouve.func, 'actions', None) or {}
    vue.action = actions.get(action.method.lower())
    codes, conditionnels, admin, modules = set(), set(), False, set()
    for garde in (f for g in vue.get_permissions() for f in _feuilles(g)):
        # FND14 — ``DroitDeLaGrille(code, champ=|operation=|export=)`` ne joue
        # que si le corps porte ce champ / cette opération (nom suffixé ``__``).
        cible = conditionnels if '__' in type(garde).__name__ else codes
        for nom in (c.__name__ for c in type(garde).__mro__):
            for prefixe in ('HasPermissionOrLegacy_', 'HasPermission_'):
                if nom.startswith(prefixe):
                    cible.add(nom[len(prefixe):])
        admin = admin or isinstance(garde, IsAdminRole)
        if isinstance(garde, (IsResponsableOrAdmin, LectureDuModule)):
            modules.add(getattr(garde, 'module_fige', None)
                        or module_de_la_vue(vue))
    return codes, conditionnels, admin, modules - {None}


def _gardes_de_la_route(action):
    """Gardes RÉELLES de la route (voir :func:`_gardes_lues`) : ``(codes,
    admin, modules)``, codes conditionnels compris."""
    codes, conditionnels, admin, modules = _gardes_lues(action)
    return codes | conditionnels, admin, modules


class _DroitsSondes(list):
    """Permissions du rôle d'un compte SONDE : tout code est accordé sauf
    ``refuse``, et chaque code DEMANDÉ (``code in permissions`` : ce que lisent
    ``has_erp_permission``, ``is_admin_role``…) est noté dans ``demandes``.
    L'itération (``set(permissions)`` des gardes « module ») rend le registre
    entier moins ``refuse``."""

    def __init__(self, codes, refuse):
        super().__init__(c for c in codes if c != refuse)
        self.refuse, self.demandes = refuse, set()

    def __contains__(self, code):
        self.demandes.add(code)
        return code != self.refuse


def _compte_sonde(refuse):
    """Compte JAMAIS enregistré (aucune base) d'un rôle fin qui porte tout le
    registre sauf ``refuse`` : il franchit toute garde, et la sonde voit chaque
    code que la route lui demande. Sans société : aucun débit par société."""
    from authentication.permissions import codes_du_registre

    droits = _DroitsSondes(sorted(codes_du_registre()), refuse)
    compte = User(pk=2 ** 31 - 7, username='sonde-parite')
    compte.role = Role(pk=2 ** 31 - 7, nom='Sonde', permissions=droits)
    return compte, droits


def _corps_minimal(action):
    """Les entrées REQUISES hors chemin, en valeurs factices (première valeur
    d'un ``enum``) : une garde liée à une entrée FACULTATIVE (réaffecter,
    émettre une facture) reste conditionnelle et n'est pas exigée."""
    schema = action.inputs or {}
    proprietes = schema.get('properties', {})
    defauts = {'integer': 1, 'number': 1, 'boolean': True, 'array': [], 'object': {}}

    def valeur(spec):
        if spec.get('enum'):
            return spec['enum'][0]
        return '2030-01-02' if spec.get('format') == 'date' else defauts.get(spec.get('type'), 'x')
    return {cle: valeur(proprietes.get(cle, {})) for cle in schema.get('required', [])
            if '{' + cle + '}' not in action.endpoint}


def _issue_sonde(action, refuse=None):
    """``(issue, codes demandés)`` de la route JOUÉE (dispatch DRF complet) par
    le compte sonde qui a tout sauf ``refuse``. Aucune base (``SimpleTestCase``) :
    la première lecture lève et ARRÊTE la vue — la sonde ne voit que ce qui est
    joué AVANT toute lecture : gardes de la classe ET refus écrits dans le corps
    de la vue. ``issue`` = statut HTTP, ou le nom de l'exception d'arrêt."""
    import json
    from unittest import mock

    from django.urls import resolve
    from rest_framework.test import APIRequestFactory, force_authenticate

    chemin, methode = _chemin_de_l_action(action), action.method.upper()
    corps = '' if methode == 'GET' else json.dumps(_corps_minimal(action))
    requete = APIRequestFactory().generic(methode, chemin, corps, content_type='application/json')
    compte, droits = _compte_sonde(refuse)
    force_authenticate(requete, user=compte)
    trouve = resolve(chemin)
    with mock.patch('core.exceptions._journalise_500'):  # l'arrêt « base interdite » n'est pas un incident
        try:
            issue = trouve.func(requete, *trouve.args, **trouve.kwargs).status_code
        except Exception as exc:  # la sonde NOTE l'arrêt : il est son issue
            issue = type(exc).__name__
    return issue, droits.demandes


def _codes_exiges(action):
    """Codes dont le SEUL refus rend 403 avant toute lecture : garde de la
    classe OU contrôle du corps de la vue (``PeutEncaisser`` de
    ``generer-facture``, ``_adseng_reporting_company``…). Vide quand la sonde
    ne peut pas jouer la route (403 même avec tous les droits)."""
    issue, demandes = _issue_sonde(action)
    if issue == 403:
        return set()
    return {code for code in sorted(demandes) if _issue_sonde(action, code)[0] == 403}


def _verdict_permission(action):
    """``(juste, détail)`` — FND14 : la permission du catalogue est un code que
    la route EXIGE (codes des gardes lues qui jouent toujours + codes exigés
    par la sonde ; un code conditionnel, ex. ``crm_reassign`` au changement
    d'``owner``, n'est pas exigé) ; sans code, la garde palier administrateur
    (``roles_gerer``), puis un code du module d'une garde « module », puis
    aucun code (route ouverte à tout compte interne)."""
    from authentication.permissions import codes_du_module

    codes, _conditionnels, admin, modules = _gardes_lues(action)
    exiges = _codes_exiges(action)
    connus, attendu = codes | exiges, action.required_permission
    if connus:
        juste = attendu in connus
    elif admin:
        juste = attendu == 'roles_gerer'
    elif modules:
        juste = any(attendu in codes_du_module(m) for m in modules)
    else:
        juste = attendu is None
    return juste, (f'{action.key} : catalogue {attendu!r}, route codes={sorted(codes)} '
                   f'exigés={sorted(exiges)} admin={admin} modules={sorted(modules)}')


class PariteCataloguePermissionRouteTest(SimpleTestCase):
    """COP-G2 + FND14 — la permission du CATALOGUE est la garde de la ROUTE,
    pour TOUTES les actions enregistrées (toutes apps, builtins compris) : une
    action offerte à un compte qui reçoit 403 (``automation.rule.propose_draft``,
    ``ventes.devis.generer_facture`` qui déclarait ``ventes_valider`` quand le
    corps de la vue exige ``encaisser``), ou cachée à un compte qui peut
    l'exécuter, trompe le modèle. La route est JOUÉE (:func:`_codes_exiges`),
    jamais lue comme un texte. Une garde que ni la lecture ni la sonde ne
    tranchent est listée ICI avec sa raison (jamais ignorée en silence) et le
    test échoue si cette liste cesse d'être exacte."""

    # clé -> raison pour laquelle la garde de la route n'est pas tranchable.
    NON_LISIBLES = {
        'ged.docqa.retrieve': (
            "catalogue `roles_gerer` (FND11 : verrou administrateur PLUS strict "
            "que la route) ; la route est une garde de MODULE (LectureDuModule "
            "ged) + l'ACL coffre-fort lue dans la vue"),
    }
    # (b) préfixe de clé -> raison : une ÉCRITURE dont le code est un code de
    # LECTURE parce que la route n'en connaît pas d'autre.
    ECRITURES_SOUS_CODE_DE_LECTURE = {
        'taches.': (
            "le module Tâches n'a qu'un droit, `taches_voir` : la route "
            "(`PermissionTaches`, apps/taches/views/base.py) l'exige pour lire "
            "ET pour écrire dans l'espace PRIVÉ du compte"),
    }

    def test_permission_du_catalogue_egale_garde_de_la_route(self):
        ecarts, non_lisibles = [], set()
        for action in all_actions():
            juste, detail = _verdict_permission(action)
            if not juste and action.key in self.NON_LISIBLES:
                non_lisibles.add(action.key)
            elif not juste:
                ecarts.append(detail)
        self.assertEqual(ecarts, [])
        self.assertEqual(non_lisibles, set(self.NON_LISIBLES))

    def test_une_ecriture_exige_un_code_d_ecriture(self):
        """(b) — une méthode d'écriture (hors ``lecture``) déclare un code qui
        accorde une écriture (``_role_grants_write`` : ni ``*_voir``, ni portée,
        ni code hors registre), jamais un code de lecture ni aucun code."""
        fautes, couverts = [], set()
        for action in all_actions():
            code = action.required_permission
            if (action.method.upper() in ('GET', 'HEAD', 'OPTIONS') or action.lecture
                    or (code is not None and User._role_grants_write([code]))):
                continue
            prefixe = next((p for p in self.ECRITURES_SOUS_CODE_DE_LECTURE
                            if action.key.startswith(p)), None)
            if prefixe is None:
                fautes.append(f'{action.key} ({action.method}) : {code!r}')
            couverts.add(prefixe)
        self.assertEqual(fautes, [])
        self.assertEqual(couverts - {None}, set(self.ECRITURES_SOUS_CODE_DE_LECTURE))

    def test_la_sonde_voit_les_refus_du_corps_de_la_vue(self):
        """La sonde JOUE la route : elle trouve le code qu'aucune classe de
        garde ne porte (refus écrit dans le corps de la vue, ou garde maison)."""
        par_cle = {a.key: a for a in all_actions()}
        for cle, code in (('ventes.devis.generer_facture', 'encaisser'),
                          ('adsengine.ads.top', 'adsengine_view'),
                          ('taches.journee.lire', 'taches_voir')):
            with self.subTest(cle=cle):
                self.assertNotIn(code, _gardes_de_la_route(par_cle[cle])[0])
                self.assertIn(code, _codes_exiges(par_cle[cle]))

    def test_le_perimetre_est_tout_le_catalogue(self):
        prefixes = {a.key.split('.', 1)[0] for a in all_actions()}
        self.assertLessEqual({'crm', 'ventes', 'stock', 'sav', 'installations',
                              'adsengine', 'taches', 'erp', 'ged', 'automation',
                              'reporting'}, prefixes)
        self.assertGreaterEqual(len(all_actions()), 80)

    def test_les_deux_ecarts_corriges_restent_alignes(self):
        par_cle = {a.key: a for a in all_actions()}
        self.assertEqual(
            par_cle['ventes.facture.enregistrer_paiement'].required_permission,
            'encaisser')
        self.assertEqual(
            par_cle['automation.rule.propose_draft'].required_permission,
            'roles_gerer')


class GuardedWriteActionsTest(TestCase):
    """FG351 — les écritures en langage naturel (Devis/Lead/Client) sont des
    actions GARDÉES : risk=outward (=> propose→confirm côté relais) et gatées
    par une permission ERP (jamais exécutées en lecture seule)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Write Co', slug='write-co')
        # Rôle « lecture seule » : crm_voir uniquement (aucun droit d'écriture).
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='wro', password='x', role=self.readonly_role,
            company=self.company)
        # Rôle « commercial » : crm_creer + ventes_creer → peut proposer toutes
        # les créations.
        self.writer_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_creer', 'ventes_creer'])
        self.writer = User.objects.create_user(
            username='wwr', password='x', role=self.writer_role,
            company=self.company)

    def _by_key(self):
        return {a.key: a for a in all_actions()}

    def test_builtin_write_actions_registered(self):
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            self.assertIn(key, catalogue)
        # L'ancienne création de devis VIDE n'existe plus : le Copilote crée
        # toujours un devis dimensionné via l'auto-devis (ventes_creer).
        self.assertNotIn('ventes.devis.create', catalogue)
        self.assertNotIn('ventes.devis.creer', catalogue)

    def test_write_actions_are_guarded_outward(self):
        action = self._by_key()['crm.client.create']
        # outward => le relais renvoie une PROPOSITION à confirmer (jamais
        # une exécution immédiate).
        self.assertEqual(action.risk, RISK_OUTWARD)
        self.assertEqual(action.method.upper(), 'POST')
        self.assertTrue(action.confirm_summary)

    def test_crm_lead_create_declare_une_seule_fois_par_crm(self):
        """COP-G2 — plus de builtin doublon : la déclaration servie est celle
        de ``apps/crm/agent_actions.py`` (descriptions « Sert à : »). Son niveau
        de risque (outward) est gardé par les tests de l'app crm."""
        action = self._by_key()['crm.lead.create']
        self.assertTrue(action.description.startswith('Sert à'))
        self.assertEqual(action.method.upper(), 'POST')

    def test_creation_de_lead_copilote_allume_ou_eteint(self):
        """COP2-C — ``crm.lead.create`` reste tel quel pour un compte dont le
        copilote est ÉTEINT (lot « herite », rien ne change pour lui) ;
        copilote ALLUMÉ, c'est ``crm.lead.creer`` (lot « copilote », garde de
        doublon) qui est servi, jamais les deux."""
        par_cle = self._by_key()
        self.assertEqual(par_cle['crm.lead.create'].lot, 'herite')
        self.assertEqual(par_cle['crm.lead.creer'].lot, 'copilote')
        self.assertEqual(par_cle['crm.lead.creer'].required_permission,
                         'crm_creer')
        self.assertEqual(par_cle['crm.lead.creer'].risk, RISK_OUTWARD)
        for reglage, attendu in (('aucun', ('crm.lead.create',)),
                                 ('tous', ('crm.lead.creer',))):
            with self.settings(ASSISTANT_COPILOTE=reglage):
                cles = {a.key for a in for_user(self.writer)}
            vus = tuple(sorted(k for k in cles if k in (
                'crm.lead.create', 'crm.lead.creer')))
            self.assertEqual(vus, attendu, reglage)

    def test_actions_retirees_du_catalogue(self):
        """COP-G2 — ``ventes.devis.proposal_pdf`` doublonnait
        ``ventes.devis.generer_pdf`` (même route /proposal)."""
        self.assertNotIn('ventes.devis.proposal_pdf', self._by_key())
        self.assertIn('ventes.devis.generer_pdf', self._by_key())

    def test_write_actions_gated_by_permission(self):
        catalogue = self._by_key()
        self.assertEqual(
            catalogue['crm.client.create'].required_permission, 'crm_creer')
        self.assertEqual(
            catalogue['crm.lead.create'].required_permission, 'crm_creer')
        # L'auto-devis (déclaré par l'app ventes) reste gaté par ventes_creer.
        self.assertEqual(
            catalogue['ventes.devis.creer_auto'].required_permission,
            'ventes_creer')

    def test_readonly_cannot_propose_writes(self):
        keys = {a.key for a in for_user(self.readonly)}
        self.assertNotIn('crm.client.create', keys)
        self.assertNotIn('crm.lead.create', keys)
        self.assertNotIn('ventes.devis.creer_auto', keys)

    def test_writer_can_propose_writes(self):
        keys = {a.key for a in for_user(self.writer)}
        self.assertIn('crm.client.create', keys)
        self.assertIn('crm.lead.create', keys)
        self.assertIn('ventes.devis.creer_auto', keys)

    def test_client_and_lead_require_nom(self):
        catalogue = self._by_key()
        for key in ('crm.client.create', 'crm.lead.create'):
            self.assertIn('nom', catalogue[key].inputs.get('required', []), key)


# AANA63 — le guide des tables et les exemples SQL du prompt de l'agent SQL
# (`_AGENT_PREFIX` de backend/fastapi_ia/app/services/sql_agent_service.py)
# ne citent que des colonnes et des statuts des modèles Django. Prompt lu dans
# le VRAI source (ast, aucun import FastAPI) ; toute puce non analysable échoue.
_SOURCE = (Path(__file__).resolve().parents[4] / 'fastapi_ia' / 'app'
           / 'services' / 'sql_agent_service.py')

_IDENT = r'[a-z_][a-z0-9_]*'
_LISTE = re.compile(rf'^{_IDENT}(\s*[,/]\s*{_IDENT})*$')
_SEP = re.compile(r'\s+[=:]\s+')
_QUOTE = re.compile(r"'([^']*)'")
_POINTE = re.compile(rf'\b({_IDENT})\.({_IDENT})\b')
_MOTS_SQL = {
    'select', 'from', 'where', 'order', 'by', 'desc', 'asc', 'and', 'or',
    'not', 'in', 'between', 'interval', 'sum', 'count', 'current_date',
    'limit', 'is', 'null', 'as',
}


def _prefixe():
    arbre = ast.parse(_SOURCE.read_text(encoding='utf-8'))
    for noeud in arbre.body:
        if (isinstance(noeud, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '_AGENT_PREFIX'
                        for t in noeud.targets)):
            return ast.literal_eval(noeud.value)
    raise AssertionError('_AGENT_PREFIX introuvable')


def _schema():
    """db_table -> {colonne: valeurs de choices (ensemble, vide si aucun)}."""
    out = {}
    for modele in apps.get_models():
        out[modele._meta.db_table] = {
            f.column: {str(c[0]) for c in (f.flatchoices or [])}
            for f in modele._meta.concrete_fields
        }
    return out


def _guide_et_exemples(texte):
    guide = texte.split('GUIDE DES TABLES', 1)[1]
    guide, exemples = guide.split('EXEMPLES DE REQUETES CORRECTES', 1)
    return guide, exemples


def _sections(guide):
    """[(tables, puces, lignes_libres)] ; une puce = '  - ' + ses lignes de
    continuation (indentées de 4 espaces)."""
    sections = []
    for ligne in guide.splitlines():
        if '→' in ligne and not ligne.startswith(' '):
            tete, queue = ligne.split('→', 1)
            tables = re.findall(r'\b[a-z]+_[a-z_]+\b', queue.split('(')[0])
            entete = re.search(r'\(([^)]*)\)', queue)
            sections.append((tables, [], []))
            if entete:
                sections[-1][1].append(entete.group(1).strip())
        elif not sections:
            continue
        elif ligne.startswith('  - '):
            sections[-1][1].append(ligne[4:].strip())
        elif ligne.startswith('    ') and sections[-1][1]:
            sections[-1][1][-1] += ' ' + ligne.strip()
        elif ligne.strip():
            sections[-1][2].append(ligne.strip())
    return sections


class PromptAgentSqlSchemaTests(SimpleTestCase):
    longMessage = False  # message court : la colonne fautive, pas le schéma

    def setUp(self):
        self.schema = _schema()
        self.texte = _prefixe()

    def _colonnes(self, tables):
        cols = {}
        for t in tables:
            self.assertIn(t, self.schema, f'table citée inexistante : {t}')
            for c, ch in self.schema[t].items():
                cols.setdefault(c, set()).update(ch)
        return cols

    def _verifier_pointes(self, texte):
        for table, col in _POINTE.findall(texte):
            if table in self.schema:
                self.assertIn(col, self.schema[table], f'{table}.{col}')

    def test_colonnes_citees_existent(self):
        guide, _ = _guide_et_exemples(self.texte)
        sections = _sections(guide)
        self.assertGreaterEqual(len(sections), 8)
        for tables, puces, libres in sections:
            cols = self._colonnes(tables)
            for puce in puces:
                for segment in (s.strip() for s in puce.split(' ; ')):
                    morceaux = _SEP.split(segment, 1)
                    gauche = morceaux[0].strip()
                    if not _LISTE.match(gauche):
                        self.fail(f'puce non analysable : {segment!r}')
                    noms = re.split(r'\s*[,/]\s*', gauche)
                    for nom in noms:
                        self.assertIn(nom, cols, f'{tables} : colonne {nom}')
                    droite = morceaux[1] if len(morceaux) > 1 else ''
                    for valeur in _QUOTE.findall(droite):
                        permis = set().union(*(cols[n] for n in noms))
                        self.assertIn(valeur, permis,
                                      f'{tables} : statut {nom}={valeur!r}')
            for libre in libres:
                self._verifier_pointes(libre)
        self._verifier_pointes(guide)

    def test_exemples_sql_sur_le_schema_reel(self):
        _, exemples = _guide_et_exemples(self.texte)
        lignes = [x[2:] for x in exemples.splitlines()
                  if x.startswith('- ')]
        self.assertGreaterEqual(len(lignes), 5)
        for ligne in lignes:
            sql = ligne.split(' : ', 1)[1]
            tables = re.findall(rf'\bFROM\s+({_IDENT})', sql)
            self.assertEqual(len(tables), 1, sql)
            cols = self._colonnes(tables)
            jetons = re.findall(rf"'[^']*'|{_IDENT}", sql.lower())
            derniere = None
            for i, jeton in enumerate(jetons):
                if jeton.startswith("'"):
                    if i and jetons[i - 1] == 'interval':
                        continue
                    self.assertIsNotNone(derniere, sql)
                    self.assertIn(jeton.strip("'"), cols[derniere],
                                  f'{sql} : statut {jeton}')
                elif jeton in _MOTS_SQL or jeton == tables[0]:
                    continue
                else:
                    self.assertIn(jeton, cols, f'{sql} : colonne {jeton}')
                    if cols[jeton]:
                        derniere = jeton

    def test_ca_facture_ht_et_devis_sans_montant_stocke(self):
        # AANA77 (D-AANA-6) : montant_ht/montant_ttc NULL sur une facture
        # classique — aucun exemple ne fait passer leur somme pour le CA.
        guide, exemples = _guide_et_exemples(self.texte)
        self.assertNotIn('SUM(montant_ht) FROM', self.texte)
        self.assertNotIn('SUM(montant_ttc) FROM', self.texte)
        self.assertIn('NULL sur une facture classique', guide)
        nb = [x for x in exemples.splitlines()
              if x.startswith('- Nombre de factures emises : ')]
        self.assertEqual(len(nb), 1, exemples)
        self.assertIn("statut IN ('emise','payee','en_retard')", nb[0])
        self.assertNotIn('ventes_devis.montant', self.texte)
        self.assertNotIn('statut_paiement', self.texte)


# TCH112 — cartes Tâches du Copilote (reference/api.md §8, §11) : chacune est une
# clé de CARTES, nommée dans `cartes_donnees` d'`assistant_reponse.json` par
# l'échantillon de SA route, et toute action `taches.*` rend l'une d'elles.
CARTES_TACHES = ('ma_journee', 'plan_propose', 'liste_taches', 'tache',
                 'capture_apercu', 'rythme', 'plan_projet', 'projet',
                 'revue_semaine', 'priorites', 'point')
_DJANGO_CORE = Path(__file__).resolve().parents[3]
_CHEMIN_ECHANTILLON = re.compile(r'apps/[a-z_]+/contract_samples/[a-z_]+\.json')


class CartesTachesTests(SimpleTestCase):
    def _cartes_donnees(self):
        import json
        chemin = _DJANGO_CORE / 'apps' / 'agent' / 'contract_samples' / 'assistant_reponse.json'
        return json.loads(chemin.read_text(encoding='utf-8'))['cartes_donnees']

    def test_chaque_carte_taches_est_dans_cartes(self):
        from apps.agent.registry import CARTES
        self.assertEqual(sorted(set(CARTES_TACHES) - CARTES), [])

    def test_chaque_carte_taches_nomme_un_echantillon_qui_existe(self):
        donnees = self._cartes_donnees()
        for carte in CARTES_TACHES:
            with self.subTest(carte=carte):
                chemins = _CHEMIN_ECHANTILLON.findall(donnees.get(carte, ''))
                self.assertTrue(chemins, carte)
                for chemin in chemins:
                    self.assertTrue((_DJANGO_CORE / chemin).is_file(), chemin)

    def test_cartes_donnees_ne_nomme_que_des_cartes_connues(self):
        from apps.agent.registry import CARTES
        self.assertEqual(sorted(set(self._cartes_donnees()) - CARTES), [])

    def test_toute_action_taches_rend_une_carte_taches(self):
        for action in all_actions():
            if action.key.startswith('taches.'):
                with self.subTest(cle=action.key):
                    self.assertIn(action.carte, CARTES_TACHES)


class FondationVague2Tests(SimpleTestCase):
    """Copilote vague 2 (FND2) — champs `lecture` / `noyau` / `natif_seul`,
    objets et cartes réservés, action `erp.ouvrir`, description de la
    suppression d'un produit."""

    def _par_cle(self):
        return {a.key: a for a in all_actions()}

    def test_as_dict_porte_lecture_noyau_et_natif_seul(self):
        neuve = AgentAction(key='demo.neuve', label='L', description='d',
                            endpoint='/x/', lot='copilote')
        d = neuve.as_dict()
        self.assertEqual((d['lecture'], d['noyau'], d['natif_seul']), (False, False, True))
        lue = AgentAction(key='demo.lue', label='L', description='d', endpoint='/x/',
                          method='POST', lecture=True)
        self.assertEqual((lue.as_dict()['lecture'], lue.as_dict()['natif_seul']), (True, False))
        par_cle = self._par_cle()
        self.assertTrue(par_cle['erp.ouvrir'].as_dict()['noyau'])
        self.assertFalse(par_cle['erp.ouvrir'].as_dict()['natif_seul'])
        self.assertFalse(par_cle['crm.lead.chercher'].as_dict()['natif_seul'])

    def test_noyau_et_vague1_ne_nomment_que_des_actions_enregistrees(self):
        from apps.agent.registry import CLES_COPILOTE_VAGUE1, LOT_HERITE, NOYAU
        par_cle = self._par_cle()
        self.assertEqual(sorted(NOYAU - set(par_cle)), [])
        self.assertEqual(sorted(CLES_COPILOTE_VAGUE1 - set(par_cle)), [])
        self.assertEqual([k for k in NOYAU if par_cle[k].lot == LOT_HERITE], [])
        self.assertEqual(sorted(k for k in CLES_COPILOTE_VAGUE1
                                if par_cle[k].lot != 'copilote'), [])

    def test_objets_et_cartes_reserves(self):
        from apps.agent.registry import CARTES, OBJETS
        self.assertLessEqual({
            'calepinage', 'variante', 'visite', 'chantier', 'intervention', 'ticket',
            'equipement', 'produit', 'bcf', 'fournisseur', 'utilisateur'}, OBJETS)
        self.assertLessEqual({
            'lien_ecran', 'fiche_calepinage', 'liste_calepinages', 'contenance',
            'liste_visites', 'fiche_visite', 'charge_equipe', 'liste_chantiers',
            'fiche_chantier', 'vente_etat', 'liste_impayes', 'liste_factures',
            'facture_brouillon', 'niveau_stock', 'parc_client', 'liste_tickets',
            'fiche_ticket', 'chiffres_ca', 'plan', 'preference', 'liste_devis', 'bcf',
            'comparaison_variantes'}, CARTES)

    def test_erp_ouvrir_suit_la_table_des_ecrans(self):
        from apps.agent import ecrans
        from apps.agent.registry import OBJETS
        action = self._par_cle()['erp.ouvrir']
        proprietes = action.inputs['properties']
        self.assertEqual(proprietes['ecran']['enum'], ecrans.cles())
        self.assertEqual(proprietes['onglet']['enum'], ecrans.onglets_calepinage())
        self.assertEqual((action.method, action.risk, action.lot, action.carte,
                          action.required_permission),
                         ('GET', RISK_INTERNAL, 'copilote', 'lien_ecran', None))
        for cle, fiche in ecrans.ecrans().items():
            with self.subTest(ecran=cle):
                self.assertTrue(fiche['chemin'].startswith('/'))
                self.assertNotIn('//', fiche['chemin'])
                self.assertIn(fiche['objet'], OBJETS | {None})
                self.assertEqual('{id}' in fiche['chemin'], bool(fiche['objet']))
        self.assertFalse({'parametres', 'utilisateurs', 'roles', 'securite'} & set(ecrans.cles()))

    def test_suppression_de_produit_eteint_identique_allume_vraie(self):
        par_cle = self._par_cle()
        ancienne, neuve = par_cle['stock.produit.delete'], par_cle['stock.produit.supprimer']
        self.assertEqual((ancienne.lot, neuve.lot), ('herite', 'copilote'))
        self.assertEqual(ancienne.description,
                         'Supprime définitivement un produit du catalogue.')
        self.assertIn('ARCHIVE', neuve.description)
        for champ in ('endpoint', 'method', 'required_permission', 'risk', 'inputs'):
            self.assertEqual(getattr(ancienne, champ), getattr(neuve, champ), champ)
