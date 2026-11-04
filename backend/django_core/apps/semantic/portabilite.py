"""NTDATA48 — PORTABILITÉ de la couche sémantique (esprit Open Semantic Interchange).

EXPORT : les métriques d'une société en un document JSON vendor-neutre — clé,
libellé, définition, dataset, mesure (agrégat ou formule), unité, décimales,
dimensions, filtres, état — réutilisable dans un outil BI externe ou dans une
autre instance. Rien de propre à la base (ni ``id``, ni ``company``, ni
horodatage) : le document décrit des DÉFINITIONS, pas des lignes.

IMPORT SYMÉTRIQUE : le même document, rejoué. ``commit=False`` (défaut) est un
DRY-RUN qui dit, métrique par métrique, ce qui serait créé / modifié / laissé
identique / refusé, sans rien écrire. ``commit=True`` applique, en UNE
transaction, et seulement si AUCUNE entrée n'est refusée (tout ou rien — un
import à moitié appliqué laisserait deux écrans en désaccord).

LISTE BLANCHE : une entrée ne porte QUE les clés de ``CHAMPS_PORTABLES`` — une
clé inconnue (``company``, ``id``, faute de frappe) est refusée en nommant la
clé, jamais ignorée en silence. Chaque entrée passe ensuite par le MÊME
sérialiseur que le CRUD (NTDATA10), donc par ``MetricDefinition.clean`` : une
seule règle de validation.

Exporter puis réimporter dans la même société donne « identique » partout ;
dans une société vide, recrée les mêmes métriques à l'identique.
"""
from django.db import transaction

#: Identifiant du format (lu à l'import pour refuser un document étranger).
FORMAT = 'taqinor.semantic.metriques'
VERSION_FORMAT = 1
#: Les seules clés d'une entrée de métrique portable.
CHAMPS_PORTABLES = (
    'cle', 'libelle', 'description', 'dataset', 'mesure', 'unite', 'format',
    'dimensions_par_defaut', 'filtres', 'actif',
)
#: Borne d'un import (un référentiel de métriques, pas un entrepôt).
MAX_METRIQUES_IMPORT = 500


def _entree(definition):
    return {champ: getattr(definition, champ) for champ in CHAMPS_PORTABLES}


def exporter_metriques(company):
    """Le document portable des métriques de ``company`` (actives ou non)."""
    from .models import MetricDefinition

    definitions = MetricDefinition.objects.filter(
        company=company).order_by('cle')
    return {
        'format': FORMAT,
        'version': VERSION_FORMAT,
        'metriques': [_entree(d) for d in definitions],
    }


def _verdict(definition_existante, donnees):
    if definition_existante is None:
        return 'creee'
    actuel = _entree(definition_existante)
    if all(actuel.get(k) == v for k, v in donnees.items()):
        return 'identique'
    return 'modifiee'


def importer_metriques(company, entrees, *, commit=False, auteur=None,
                       contexte=None):
    """Valide (et, si ``commit``, applique) un document de métriques.

    Renvoie ``{'commit': bool, 'applique': bool, 'resultats': [...]}`` — une
    ligne par entrée : ``{'cle', 'action': creee|modifiee|identique|refusee,
    'erreurs'}``.
    """
    from . import services
    from .models import MetricDefinition
    from .serializers import MetricDefinitionSerializer

    existantes = {d.cle: d for d in MetricDefinition.objects.filter(
        company=company)}
    resultats = []
    a_appliquer = []
    vues = set()
    for index, entree in enumerate(entrees):
        cle = entree.get('cle') if isinstance(entree, dict) else None
        ligne = {'cle': cle if isinstance(cle, str) else '', 'index': index}
        if not isinstance(entree, dict):
            ligne.update(action='refusee',
                         erreurs={'entree': 'Objet JSON attendu.'})
            resultats.append(ligne)
            continue
        inconnues = sorted(set(entree) - set(CHAMPS_PORTABLES))
        if inconnues:
            ligne.update(action='refusee', erreurs={
                k: 'Clé non portable (refusée).' for k in inconnues})
            resultats.append(ligne)
            continue
        if cle in vues:
            ligne.update(action='refusee',
                         erreurs={'cle': 'Clé présente deux fois dans le '
                                         'document.'})
            resultats.append(ligne)
            continue
        vues.add(cle)
        existante = existantes.get(cle)
        serializer = MetricDefinitionSerializer(
            instance=existante, data=entree, partial=existante is not None,
            context=contexte or {})
        if not serializer.is_valid():
            ligne.update(action='refusee', erreurs=serializer.errors)
            resultats.append(ligne)
            continue
        action = _verdict(existante, serializer.validated_data)
        ligne.update(action=action, erreurs={})
        resultats.append(ligne)
        if action != 'identique':
            a_appliquer.append(serializer)

    refus = any(r['action'] == 'refusee' for r in resultats)
    applique = False
    if commit and not refus:
        with transaction.atomic():
            for serializer in a_appliquer:
                avant = services.derniere_version_id(serializer.instance)
                definition = serializer.save(company=company)
                services.attribuer_auteur(definition, avant, auteur)
        applique = True
    return {'commit': bool(commit), 'applique': applique,
            'resultats': resultats}
