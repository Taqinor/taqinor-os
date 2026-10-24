"""NTEXT21 — points d'extension UI : ONGLETS custom sur une fiche.

``GET core/ui-onglets/?cible=ventes.devis`` renvoie les onglets APPLICABLES
(actifs + palier) ; avec ``&target_id=<id>`` en plus, la ``condition``
(arbre core.rules) de chaque onglet est évaluée sur CET enregistrement et un
onglet ``objet_custom_lie`` embarque son ``contenu`` (délégué à un résolveur
ENREGISTRÉ, ``core.ui_extensions.register_onglet_resolver`` — même patron
que les boutons NTEXT20, ``core`` ne connaît aucune app métier).
"""
import itertools

# ENF20 — modèles domaine résolus par libellé : core n'importe aucune app.
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import UiOngletCustom

User = get_user_model()

URL = '/api/django/core/ui-onglets/'

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT21 Co {next(_seq)}')


def make_user(company, role='normal', username=None):
    return User.objects.create_user(
        username=username or f'ntext21-u{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class OngletsApplicablesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.commercial = make_user(self.company, role='normal')
        self.admin = make_user(self.company, role='admin')

    def test_onglet_applicable_apparait(self):
        UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis', titre='Suivi',
            type_contenu=UiOngletCustom.TypeContenu.HTML, ref='<p>Ok</p>')
        res = _auth(self.commercial).get(f'{URL}?cible=ventes.devis')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('Suivi', [o['titre'] for o in res.data])

    def test_onglet_reserve_a_un_palier(self):
        UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis', titre='Marge',
            type_contenu=UiOngletCustom.TypeContenu.HTML, ref='',
            role_tier='admin')
        res_commercial = _auth(self.commercial).get(
            f'{URL}?cible=ventes.devis')
        self.assertNotIn('Marge', [o['titre'] for o in res_commercial.data])
        res_admin = _auth(self.admin).get(f'{URL}?cible=ventes.devis')
        self.assertIn('Marge', [o['titre'] for o in res_admin.data])

    def test_onglet_inactif_absent(self):
        UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis', titre='Coupé',
            type_contenu=UiOngletCustom.TypeContenu.HTML, ref='',
            actif=False)
        res = _auth(self.commercial).get(f'{URL}?cible=ventes.devis')
        self.assertNotIn('Coupé', [o['titre'] for o in res.data])


class ContenuObjetCustomLieTests(TestCase):
    """Le critère NTEXT21 : un onglet « Interventions liées » sur la fiche
    devis liste les enregistrements d'un objet custom filtrés par l'id du
    devis (résolveur réel de ``apps.customfields``, branché via
    ``CustomfieldsConfig.ready()``)."""

    def setUp(self):
        Client = django_apps.get_model('crm', 'Client')
        CustomObjectDef = django_apps.get_model('customfields', 'CustomObjectDef')
        CustomRecord = django_apps.get_model('customfields', 'CustomRecord')
        Devis = django_apps.get_model('ventes', 'Devis')

        self.company = make_company()
        self.user = make_user(self.company)
        client = Client.objects.create(
            company=self.company, nom='Client interventions')
        self.devis = Devis.objects.create(
            company=self.company, reference='NTEXT21-D1', client=client,
            statut='brouillon')
        self.autre_devis = Devis.objects.create(
            company=self.company, reference='NTEXT21-D2', client=client,
            statut='brouillon')

        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='interventions', libelle='Interventions')
        self.record_lie = CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'devis_id': self.devis.pk, 'note': 'Visite technique'})
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'devis_id': self.autre_devis.pk, 'note': 'Autre devis'})

        self.onglet = UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis',
            titre='Interventions liées',
            type_contenu=UiOngletCustom.TypeContenu.OBJET_CUSTOM_LIE,
            ref='interventions')

    def test_contenu_filtre_par_id_du_devis(self):
        res = _auth(self.user).get(
            f'{URL}?cible=ventes.devis&target_id={self.devis.pk}')
        self.assertEqual(res.status_code, 200, res.data)
        onglet = next(
            o for o in res.data if o['titre'] == 'Interventions liées')
        ids = [c['id'] for c in onglet['contenu']]
        self.assertEqual(ids, [self.record_lie.pk])
        self.assertEqual(
            onglet['contenu'][0]['data']['note'], 'Visite technique')

    def test_sans_target_id_pas_de_contenu_calcule(self):
        res = _auth(self.user).get(f'{URL}?cible=ventes.devis')
        onglet = next(
            o for o in res.data if o['titre'] == 'Interventions liées')
        self.assertNotIn('contenu', onglet)


class ConditionOngletTests(TestCase):
    """Un onglet dont la ``condition`` est fausse sur l'enregistrement ciblé
    est omis (arbre core.rules, comme les conditions de champ XPLT15)."""

    def setUp(self):
        Client = django_apps.get_model('crm', 'Client')
        Devis = django_apps.get_model('ventes', 'Devis')

        self.company = make_company()
        self.user = make_user(self.company)
        client = Client.objects.create(
            company=self.company, nom='Client condition')
        self.devis = Devis.objects.create(
            company=self.company, reference='NTEXT21-COND', client=client,
            statut='brouillon')

    def test_condition_vraie_onglet_visible(self):
        UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis', titre='Conditionnel',
            type_contenu=UiOngletCustom.TypeContenu.HTML, ref='<p>x</p>',
            condition={'field': 'statut', 'operator': 'eq',
                       'value': 'brouillon'})
        res = _auth(self.user).get(
            f'/api/django/core/ui-onglets/?cible=ventes.devis&target_id='
            f'{self.devis.pk}')
        self.assertIn('Conditionnel', [o['titre'] for o in res.data])

    def test_condition_schema_et_serveur_un_seul_predicat(self):
        # CI #1000 — l'arbre publié au schéma de requête est exactement le
        # prédicat appliqué : `{}` / `true` / opérateur inconnu / `field`
        # blanc = 400 (« conformes » au JSON libre d'avant) ; `null`, une
        # feuille, un groupe ET et un groupe NON = 201.
        import jsonschema
        from core.champs_stricts import (
            arbre_conditions_valide, schema_arbre_conditions)
        valideur = jsonschema.Draft7Validator(schema_arbre_conditions())
        feuille = {'field': 'statut', 'operator': 'eq', 'value': 'x'}
        mauvais = [{}, True, [], 'x', {'field': 'a'}, {'field': ' ',
                   'operator': 'eq'}, {'field': 'a', 'operator': 'EQ'},
                   {'op': 'and', 'conditions': []},
                   {'op': 'not', 'conditions': [feuille, feuille]},
                   {'op': 'AND', 'conditions': [feuille]}]
        bons = [feuille, {'op': 'and', 'conditions': [feuille]},
                {'conditions': [feuille, feuille]},
                {'op': 'not', 'conditions': [feuille]}]
        for arbre in mauvais:
            self.assertFalse(valideur.is_valid(arbre), arbre)
            self.assertFalse(arbre_conditions_valide(arbre), arbre)
        for arbre in bons:
            self.assertTrue(valideur.is_valid(arbre), arbre)
            self.assertTrue(arbre_conditions_valide(arbre), arbre)
        api = _auth(make_user(self.company, role='admin'))
        base = {'cible': 'ventes.devis', 'titre': 'T',
                'type_contenu': 'html', 'ref': ''}
        for arbre in mauvais:
            res = api.post(URL, {**base, 'condition': arbre}, format='json')
            self.assertEqual(res.status_code, 400, (arbre, res.data))
            self.assertIn('condition', res.data)
        for arbre in bons + [None]:
            res = api.post(URL, {**base, 'condition': arbre}, format='json')
            self.assertEqual(res.status_code, 201, (arbre, res.data))

    def test_condition_cles_inconnues_jamais_stockees(self):
        # api-fuzz-full 24/10 — une clé inconnue portant un caractère nul
        # faisait refuser le jsonb (500) : l'arbre est stocké canonique.
        api = _auth(make_user(self.company, role='admin'))
        feuille = {'field': 'statut', 'operator': 'ne', 'cle\x00': {'a': 1},
                   'op': {'x': []}}
        res = api.post(URL, {
            'cible': 'ventes.devis', 'titre': 'T', 'type_contenu': 'html',
            'ref': '', 'condition': {'op': 'and', 'conditions': [feuille],
                                     '.exe': {}}}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(
            UiOngletCustom.objects.get(pk=res.data['id']).condition,
            {'op': 'and', 'conditions': [
                {'field': 'statut', 'operator': 'ne'}]})

    def test_condition_fausse_onglet_omis(self):
        UiOngletCustom.objects.create(
            company=self.company, cible='ventes.devis', titre='Conditionnel',
            type_contenu=UiOngletCustom.TypeContenu.HTML, ref='<p>x</p>',
            condition={'field': 'statut', 'operator': 'eq',
                       'value': 'accepte'})
        res = _auth(self.user).get(
            f'/api/django/core/ui-onglets/?cible=ventes.devis&target_id='
            f'{self.devis.pk}')
        self.assertNotIn('Conditionnel', [o['titre'] for o in res.data])
