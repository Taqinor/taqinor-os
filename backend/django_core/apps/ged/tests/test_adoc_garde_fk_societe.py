"""ADOC36 — garde de classe : aucune FK inscriptible d'un sérialiseur GED
n'accepte la ligne d'une autre société.

Découverte par INTROSPECTION du module `apps.ged.serializers` (aucune liste
de sérialiseurs écrite à la main) : pour chaque champ relationnel non
read_only dont le modèle cible porte `company`, le queryset résolu pour un
utilisateur de la société A ne doit contenir AUCUNE ligne de la société B.
Les exceptions (cible sans société) sont dérivées du modèle cible.
"""
import inspect

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework import serializers

from apps.crm.models import Client
from apps.ged import serializers as ged_serializers
from apps.ged.models import (
    Cabinet, Coffre, DemandeSignatureDocument, Document, DocumentTag,
    DocumentVersion, ExigenceDossier, Folder, ModeleDocument,
    TypeChampSignature,
)
from apps.roles.models import Role
from authentication.models import Company
from core.serializers import model_is_company_scoped

User = get_user_model()


def _semer(company, suffixe):
    """Au moins une ligne de chaque modèle cible pour la société donnée."""
    user = User.objects.create_user(
        username=f'adoc36-{suffixe}', password='x', company=company,
        role_legacy='admin')
    cab = Cabinet.objects.create(company=company, nom=f'Cab {suffixe}')
    folder = Folder.objects.create(company=company, cabinet=cab,
                                   nom=f'F {suffixe}')
    doc = Document.objects.create(company=company, folder=folder,
                                  nom=f'D {suffixe}')
    DocumentVersion.objects.create(company=company, document=doc, version=1,
                                   file_key=f'attachments/{suffixe}.pdf')
    DocumentTag.objects.create(company=company, nom=f'T {suffixe}')
    ExigenceDossier.objects.create(company=company, folder=folder,
                                   libelle=f'E {suffixe}')
    Coffre.objects.create(company=company, nom=f'C {suffixe}',
                          proprietaire=user)
    Client.objects.create(company=company, nom=f'Cl {suffixe}',
                          email=f'{suffixe}@example.com')
    Role.objects.create(company=company, nom=f'R {suffixe}')
    ModeleDocument.objects.create(company=company, nom=f'M {suffixe}')
    TypeChampSignature.objects.create(
        company=company, code=f'tc{suffixe}', libelle=f'TC {suffixe}',
        mode_saisie='texte')
    DemandeSignatureDocument.objects.create(
        company=company, document=doc, signataire_nom='S',
        signataire_email=f's{suffixe}@example.com', created_by=user)
    return user


def _serialiseurs_ged():
    for _nom, classe in inspect.getmembers(ged_serializers, inspect.isclass):
        if (issubclass(classe, serializers.ModelSerializer)
                and classe.__module__ == ged_serializers.__name__):
            yield classe


def _relations_inscriptibles(serialiseur):
    for nom, champ in serialiseur.fields.items():
        if getattr(champ, 'read_only', False):
            continue
        relation = getattr(champ, 'child_relation', champ)
        if not isinstance(relation, serializers.RelatedField):
            continue
        if getattr(relation, 'read_only', False):
            continue
        yield nom, relation


class GardeFkSocieteGed(TestCase):
    def setUp(self):
        self.co_a = Company.objects.get_or_create(
            slug='adoc36-a', defaults={'nom': 'ADOC36 A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='adoc36-b', defaults={'nom': 'ADOC36 B'})[0]
        self.user_a = _semer(self.co_a, 'a')
        _semer(self.co_b, 'b')
        requete = RequestFactory().get('/')
        requete.user = self.user_a
        self.contexte = {'request': requete}

    def test_tous_les_serializers_bornes(self):
        classes = list(_serialiseurs_ged())
        self.assertGreater(len(classes), 20)
        fuites, sans_fixture = [], set()
        for classe in classes:
            serialiseur = classe(context=self.contexte)
            for nom, relation in _relations_inscriptibles(serialiseur):
                qs = relation.get_queryset()
                if qs is None or not model_is_company_scoped(qs.model):
                    continue
                if not qs.model._default_manager.filter(
                        company=self.co_b).exists():
                    sans_fixture.add(qs.model.__name__)
                    continue
                if qs.filter(company=self.co_b).exists():
                    fuites.append(
                        f'{classe.__name__}.{nom} non borné à la société')
        self.assertEqual(
            sans_fixture, set(),
            'Ajoutez une ligne de la société B pour ces modèles cibles : '
            f'{sorted(sans_fixture)}')
        self.assertEqual(fuites, [], '\n'.join(fuites))
