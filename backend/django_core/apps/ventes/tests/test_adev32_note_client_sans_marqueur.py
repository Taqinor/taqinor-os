"""ADEV32 (C-ADEV-045) — ``Devis.note`` est le TEXTE CLIENT (servi en
``note_client`` par ``GET /public/proposal/<token>/data/`` et imprimé par
``/proposal``) : les marqueurs internes « [Copie de …] », « [Variante …] »,
« [Gamme …] » et « pièce jointe #… » n'y sont plus écrits — ils vont au
chatter ``DevisActivity`` de la copie.

Chaque test lit ``note_client`` du VRAI payload public (rejoue la sonde VB q2).
Garde de classe (même fichier) : aucun ``note=`` littéral/f-string/concat dans
un ``Devis.objects.create`` / ``Devis(...)`` / ``cloner_devis`` du paquet
ventes (analyse AST).

Test-du-test : remettre ``note=f'[Copie de {ref}] ' + …`` dans
``dupliquer_devis`` ⇒ ``test_copie`` et ``test_garde_ast`` échouent.
"""
import ast
import uuid
from pathlib import Path
from types import SimpleNamespace

from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, ShareLink
from apps.ventes.tests.test_proposal_data_shape import (
    make_client, make_company, make_devis, make_user)

MARQUEURS = ('[Copie de', '[Variante', '[Gamme', 'pièce jointe #')
RACINE_VENTES = Path(__file__).resolve().parents[1]


class NoteClientSansMarqueurTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('adev32-co')
        cls.user = make_user(cls.company)
        cls.client_obj = make_client(cls.company)
        cls.source = make_devis(cls.company, cls.user, cls.client_obj,
                                'DEV-ADEV32-SRC')
        Devis.objects.filter(pk=cls.source.pk).update(note='')
        cls.source.refresh_from_db()

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _note_client(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=self.company, devis=devis,
                                 token=token)
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json().get('note_client', '')

    def _assert_propre(self, copie, marqueur):
        copie.refresh_from_db()  # CLAUSE PERSISTANCE : relue en base
        self.assertEqual(copie.note or '', '')
        note_publique = self._note_client(copie)
        for m in MARQUEURS:
            self.assertNotIn(m, note_publique)
        self.assertTrue(
            copie.activites.filter(body__contains=marqueur).exists(),
            'marqueur %r absent du chatter de la copie' % marqueur)

    def test_copie(self):
        reponse = self.api.post(
            f'/api/django/ventes/devis/{self.source.pk}/dupliquer/', {},
            format='json')
        self.assertIn(reponse.status_code, (200, 201), reponse.content[:300])
        copie = Devis.objects.get(pk=reponse.data['id'])
        self._assert_propre(copie, '[Copie de DEV-ADEV32-SRC]')

    def test_variante(self):
        reponse = self.api.post(
            f'/api/django/ventes/devis/{self.source.pk}/dupliquer-variante/',
            {}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content[:300])
        self.assertTrue(reponse.data)
        for item in reponse.data:
            self._assert_propre(Devis.objects.get(pk=item['id']),
                                '[Variante ')

    def test_gamme(self):
        from apps.ventes.domain.gammes import creer_variante_gamme
        soeur = creer_variante_gamme(self.source, 'Premium', user=self.user)
        self._assert_propre(soeur, '[Gamme Premium]')

    def test_reserve(self):
        """La réserve garde sa DESCRIPTION en note (texte client) ; l'origine
        et « pièce jointe #… » vont au chatter."""
        from apps.ventes.domain.gammes import create_devis_from_reserve
        installation = SimpleNamespace(
            client=self.client_obj, client_id=self.client_obj.pk,
            company=self.company, devis=None,
            type_installation='commercial')
        reserve = SimpleNamespace(
            id=1, company=self.company, description='',
            photo_id=4242,
            intervention=SimpleNamespace(installation=installation))
        devis = create_devis_from_reserve(reserve=reserve, user=self.user)
        self._assert_propre(devis, 'pièce jointe #4242')

    def test_reserve_garde_la_description(self):
        from apps.ventes.domain.gammes import create_devis_from_reserve
        installation = SimpleNamespace(
            client=self.client_obj, client_id=self.client_obj.pk,
            company=self.company, devis=None,
            type_installation='commercial')
        reserve = SimpleNamespace(
            id=2, company=self.company, description='Fissure du rail',
            photo_id=7, intervention=SimpleNamespace(installation=installation))
        devis = create_devis_from_reserve(reserve=reserve, user=self.user)
        note_publique = self._note_client(devis)
        self.assertIn('Fissure du rail', note_publique)
        self.assertNotIn('pièce jointe #', note_publique)


class GardeAstEcrivainsNote(TestCase):
    """Aucun écrivain de ``Devis.note`` ne compose un texte (marqueur) dans
    le paquet ventes : ``note=`` d'un ``Devis.objects.create`` / ``Devis()``
    / ``cloner_devis`` n'est jamais une f-string, une concaténation ou une
    chaîne non vide. Les écrivains légitimes passent une valeur (saisie
    ``DevisWriteSerializer``, copie telle quelle ``reviser``/``renouveler``)."""

    @staticmethod
    def _est_ecrivain_devis(appel):
        f = appel.func
        if isinstance(f, ast.Name) and f.id in ('Devis', 'cloner_devis'):
            return True
        if isinstance(f, ast.Attribute):
            if f.attr == 'cloner_devis':
                return True
            if (f.attr in ('create', 'get_or_create', 'update_or_create')
                    and isinstance(f.value, ast.Attribute)
                    and f.value.attr == 'objects'
                    and isinstance(f.value.value, ast.Name)
                    and f.value.value.id == 'Devis'):
                return True
        return False

    @staticmethod
    def _compose(valeur):
        if isinstance(valeur, (ast.JoinedStr, ast.BinOp)):
            return True
        if isinstance(valeur, ast.Call) and isinstance(
                valeur.func, ast.Attribute) and valeur.func.attr == 'strip' \
                and isinstance(valeur.func.value, (ast.BinOp, ast.JoinedStr)):
            return True
        return (isinstance(valeur, ast.Constant)
                and isinstance(valeur.value, str) and valeur.value != '')

    def test_garde_ast(self):
        fautifs = []
        for chemin in sorted(RACINE_VENTES.rglob('*.py')):
            if 'tests' in chemin.parts or 'migrations' in chemin.parts:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Call) \
                        and self._est_ecrivain_devis(noeud):
                    for kw in noeud.keywords:
                        if kw.arg == 'note' and self._compose(kw.value):
                            fautifs.append('%s:%s' % (
                                chemin.relative_to(RACINE_VENTES),
                                noeud.lineno))
        self.assertEqual(fautifs, [], 'marqueur composé écrit dans '
                                      'Devis.note : %s' % fautifs)
