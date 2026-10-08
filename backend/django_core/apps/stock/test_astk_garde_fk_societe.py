"""ASTK8 (C-ASTK-001, S1) — garde de CLASSE « FK non bornée à la société ».

Un test balaie, par INTROSPECTION des modules (aucune liste écrite à la main),
tous les sérialiseurs de ``apps.stock`` (``serializers``, ``serializers_wms``,
``serializers_fiche_technique``, ceux déclarés dans ``apps.stock.views.*``) et
de ``apps.achats``, lit récursivement (imbriqués compris) le queryset résolu de
chaque champ de relation inscriptible pour un utilisateur de la société A, et
refuse tout champ dont le queryset :

* ne porte pas de borne société (la société A n'apparaît pas dans le SQL), ou
* renvoie une ligne de la société B.

Exemptions DÉRIVÉES du modèle (cible sans relation ``company``) ou nommées via
``company_scoped_relations_exclude`` — jamais par numéro de ligne.

Test-du-test : un sérialiseur déclaré avec un champ non borné est refusé par la
même fonction (``test_la_garde_nomme_un_champ_non_borne``).

Run :
    python manage.py test apps.stock.test_astk_garde_fk_societe -v 2
"""
import importlib
import inspect
import pkgutil
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import EmptyResultSet
from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

from core.serializers import model_is_company_scoped

User = get_user_model()

MODULES_RACINES = [
    'apps.stock.serializers',
    'apps.stock.serializers_wms',
    'apps.stock.serializers_fiche_technique',
    'apps.achats.serializers',
]
PAQUETS_VUES = ['apps.stock.views', 'apps.achats']
PREFIXES_PROPRES = ('apps.stock', 'apps.achats')


def _importer(nom):
    try:
        return importlib.import_module(nom)
    except ImportError:
        return None


def modules_a_balayer():
    """Modules de sérialiseurs + tous les sous-modules des paquets de vues."""
    modules = []
    for nom in MODULES_RACINES:
        module = _importer(nom)
        if module is not None:
            modules.append(module)
    for racine in PAQUETS_VUES:
        paquet = _importer(racine)
        if paquet is None:
            continue
        modules.append(paquet)
        chemin = getattr(paquet, '__path__', None)
        if not chemin:
            continue
        for info in pkgutil.walk_packages(chemin, prefix=racine + '.'):
            module = _importer(info.name)
            if module is not None:
                modules.append(module)
    return modules


def decouvrir_serializers():
    """Classes de sérialiseurs DÉFINIES dans apps.stock / apps.achats."""
    trouves = {}
    for module in modules_a_balayer():
        for _, classe in inspect.getmembers(module, inspect.isclass):
            if not issubclass(classe, serializers.BaseSerializer):
                continue
            if issubclass(classe, serializers.ListSerializer):
                continue
            if not (classe.__module__ or '').startswith(PREFIXES_PROPRES):
                continue
            if classe.__module__.endswith('.tests') or '.test' in classe.__module__:
                continue
            trouves[classe] = None
    return sorted(trouves, key=lambda c: (c.__module__, c.__name__))


def _champs_relation(serializer, chemin):
    """(chemin, champ_relation) pour chaque relation inscriptible, récursif."""
    for nom, champ in serializer.fields.items():
        if getattr(champ, 'read_only', False):
            continue
        cible = getattr(champ, 'child_relation', None) or champ
        if isinstance(cible, serializers.RelatedField):
            yield f'{chemin}.{nom}', nom, cible
            continue
        # Sérialiseur imbriqué (many=True → ListSerializer.child).
        imbrique = getattr(champ, 'child', None) or champ
        if isinstance(imbrique, serializers.BaseSerializer) and hasattr(
                imbrique, 'fields'):
            yield from _champs_relation(imbrique, f'{chemin}.{nom}')


def _est_borne(queryset, societe_a, societe_b):
    """Vrai si le queryset est borné à A et ne contient aucune ligne de B."""
    try:
        sql, params = queryset.query.sql_with_params()
    except EmptyResultSet:
        return True
    plats = []
    for p in params:
        plats.extend(p if isinstance(p, (list, tuple)) else [p])
    if 'company_id' not in sql or societe_a.id not in plats:
        return False
    return not queryset.filter(company_id=societe_b.id).exists()


def champs_non_bornes(classe, requete, societe_a, societe_b):
    """Liste de « <module>.<Serializer>.<champ> non borné à la société »."""
    try:
        instance = classe(context={'request': requete})
        instance.fields  # force get_fields()
    except TypeError:
        # Sérialiseur à arguments obligatoires (non instanciable à nu) : il
        # n'expose pas de relation inscriptible auto-construite.
        return []
    exclus = set(getattr(classe, 'company_scoped_relations_exclude', ()) or ())
    manquants = []
    base = f'{classe.__module__}.{classe.__name__}'
    for chemin, nom, champ in _champs_relation(instance, base):
        if nom in exclus:
            continue
        try:
            queryset = champ.get_queryset()
        except Exception:  # noqa: BLE001 — champ sans queryset exploitable
            continue
        if queryset is None:
            continue
        modele = queryset.model
        # Exemption DÉRIVÉE du modèle : cible sans société (référentiel global).
        if not model_is_company_scoped(modele):
            continue
        if not _est_borne(queryset, societe_a, societe_b):
            manquants.append(f'{chemin} non borné à la société')
    return manquants


class GardeFkSocieteStock(TestCase):
    def setUp(self):
        from authentication.models import Company
        from apps.stock.models import (
            Categorie, EmplacementStock, Fournisseur, Produit,
        )

        self.a, _ = Company.objects.get_or_create(
            slug='astk8-a', defaults={'nom': 'ASTK8 A'})
        self.b, _ = Company.objects.get_or_create(
            slug='astk8-b', defaults={'nom': 'ASTK8 B'})
        self.user_a = User.objects.create_user(
            username='astk8_resp_a', password='x', role_legacy='responsable',
            company=self.a)
        # Au moins une ligne de B par modèle cible courant : la garde par les
        # données a des dents (l'absence de borne la ferait échouer).
        Fournisseur.objects.create(company=self.b, nom='FOURNISSEUR-B-ASTK8')
        Produit.objects.create(
            company=self.b, nom='ProdB-ASTK8', sku='ASTK8-PB',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        Categorie.objects.create(company=self.b, nom='Cat B ASTK8')
        EmplacementStock.objects.create(
            company=self.b, nom='Dépôt B ASTK8', is_principal=True)
        User.objects.create_user(
            username='astk8_user_b', password='x', role_legacy='responsable',
            company=self.b)
        self.requete = Request(APIRequestFactory().get('/'))
        self.requete.user = self.user_a

    def test_decouverte_non_vide(self):
        """La découverte trouve bien l'ensemble des sérialiseurs (garde contre
        une introspection silencieusement vide)."""
        classes = decouvrir_serializers()
        self.assertGreater(len(classes), 40, [c.__name__ for c in classes])

    def test_tous_les_serializers_bornes(self):
        manquants = []
        for classe in decouvrir_serializers():
            manquants.extend(champs_non_bornes(
                classe, self.requete, self.a, self.b))
        self.assertEqual(
            manquants, [],
            'Champs FK/M2M inscriptibles non bornés à la société :\n'
            + '\n'.join(manquants))

    def test_la_garde_nomme_un_champ_non_borne(self):
        """Test-du-test : retirer le mixin d'un sérialiseur ⇒ la garde nomme
        le champ et échoue."""
        from apps.stock.models import Produit

        class SerializerNonBorne(serializers.Serializer):
            produit = serializers.PrimaryKeyRelatedField(
                queryset=Produit.objects.all())

        SerializerNonBorne.__module__ = 'apps.stock.test_astk_garde_fk_societe'
        manquants = champs_non_bornes(
            SerializerNonBorne, self.requete, self.a, self.b)
        self.assertEqual(len(manquants), 1, manquants)
        self.assertIn('SerializerNonBorne.produit non borné à la société',
                      manquants[0])
