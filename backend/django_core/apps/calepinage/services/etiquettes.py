"""CALX343 — les ÉTIQUETTES LIBRES d'un calepinage, et leur filtre de liste.

LE CONSTAT
----------
Le seul tag posé sur un calepinage était le drapeau SYSTÈME
``calepinage:modele`` (``services/modeles.py``, CAL199), et
``selectors.appliquer_filtres_liste`` n'offrait aucun filtre d'étiquette —
alors que ``platform.py`` déclare déjà ``calepinage.calepinage`` cible des
enregistrements plateforme et que ``records`` sert ``tags``/``tagged-items``.
Parité : OpenSolar (https://www.opensolar.com/crm — recherche, filtres, vues
sauvegardées).

LA PRIMITIVE EST CELLE DE LA PLATEFORME
---------------------------------------
``records.Tag`` (vocabulaire PAR SOCIÉTÉ) et ``records.TaggedItem`` (le lien
générique) — AUCUN modèle d'étiquette maison, AUCUNE migration. ``records``
est une app de FONDATION : l'import direct est permis.

LES RÈGLES DURES (contrat ``contract_samples/calepinage_etiquettes.json``)
--------------------------------------------------------------------------
* **Vocabulaire contrôlé** : une étiquette se CHOISIT dans le vocabulaire de
  la société, elle ne se crée JAMAIS à la volée depuis un calepinage — un nom
  inconnu est refusé en nommant ``nom`` ;
* **Borné société** : une étiquette d'une AUTRE société (ou inexistante) est
  refusée en nommant ``tag_id`` — même message dans les deux cas ;
* **Le tag système est EXCLU** : ``calepinage:modele`` n'apparaît jamais comme
  étiquette libre et ne se pose ni ne se retire par cette porte ;
* **Idempotent** : poser deux fois la même étiquette ne crée ni seconde ligne
  ni seconde entrée de journal ; retirer une étiquette absente ne fait rien ;
* **Journalisé** : chaque pose/retrait EFFECTIF passe par
  ``services/journal.py::noter`` (chatter plateforme, auteur posé serveur).
"""
from __future__ import annotations

from .modeles import NOM_TAG_MODELE

__all__ = [
    'EtiquetteRefusee', 'etiquettes_du_calepinage', 'filtrer_par_etiquette',
    'poser_etiquette', 'retirer_etiquette',
]


class EtiquetteRefusee(ValueError):
    """Refus métier, message français, champ fautif NOMMÉ."""

    def __init__(self, message, *, champ='tag_id'):
        super().__init__(message)
        self.champ = champ


def _type_calepinage():
    from django.contrib.contenttypes.models import ContentType

    from ..models import Calepinage

    return ContentType.objects.get_for_model(Calepinage)


def _en_ligne(tag):
    return {'id': tag.pk, 'nom': tag.nom, 'couleur': tag.couleur or ''}


def etiquettes_du_calepinage(calepinage):
    """``{etiquettes: [{id, nom, couleur}]}`` — triées par nom, tag système
    EXCLU, étiquettes de la société du calepinage seulement. Lecture pure."""
    from apps.records.models import Tag, TaggedItem

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return {'etiquettes': []}
    poses = (TaggedItem.objects
             .filter(content_type=_type_calepinage(),
                     object_id=calepinage.pk)
             .values('tag_id'))
    tags = (Tag.objects
            .filter(company_id=calepinage.company_id, pk__in=poses)
            .exclude(nom=NOM_TAG_MODELE)
            .order_by('nom', 'id'))
    return {'etiquettes': [_en_ligne(tag) for tag in tags]}


def _identifiant(brut):
    if isinstance(brut, bool):
        return None
    if isinstance(brut, int):
        return brut if brut > 0 else None
    texte = str(brut).strip()
    if texte.isdigit() and int(texte) > 0:
        return int(texte)
    return None


def _resoudre(company, corps):
    """Le ``records.Tag`` désigné par ``{tag_id}`` ou ``{nom}``, ou refus.

    Ne CRÉE jamais de tag (vocabulaire contrôlé).
    """
    from apps.records.models import Tag

    corps = corps if isinstance(corps, dict) else {}
    brut_id = corps.get('tag_id')
    nom = str(corps.get('nom') or '').strip()
    if brut_id not in (None, ''):
        tag_id = _identifiant(brut_id)
        tag = (Tag.objects.filter(company=company, pk=tag_id).first()
               if tag_id is not None and company is not None else None)
        if tag is None:
            raise EtiquetteRefusee(
                'Étiquette introuvable dans le vocabulaire de cette société '
                '(tag_id : %s).' % (brut_id,), champ='tag_id')
        champ = 'tag_id'
    elif nom:
        tag = (Tag.objects.filter(company=company, nom=nom).first()
               if company is not None else None)
        if tag is None:
            raise EtiquetteRefusee(
                "Aucune étiquette « %s » dans le vocabulaire de la société : "
                "une étiquette ne se crée pas depuis un calepinage — "
                "ajoutez-la d'abord au vocabulaire des étiquettes." % nom,
                champ='nom')
        champ = 'nom'
    else:
        raise EtiquetteRefusee(
            "Indiquez l'étiquette à poser ou à retirer : « tag_id » "
            "(identifiant) ou « nom » (nom exact).", champ='tag_id')
    if tag.nom == NOM_TAG_MODELE:
        raise EtiquetteRefusee(
            '« %s » est le drapeau système des modèles réutilisables : il se '
            'pose depuis la bibliothèque, jamais comme étiquette libre.'
            % NOM_TAG_MODELE, champ=champ)
    return tag


def poser_etiquette(calepinage, corps, *, user=None):
    """Pose l'étiquette désignée — idempotent, journalisé s'il y a eu pose.

    Returns:
        La liste À JOUR (``etiquettes_du_calepinage``).

    Raises:
        EtiquetteRefusee: étiquette inconnue, d'une autre société, système,
            ou non désignée — le champ fautif est NOMMÉ.
    """
    from django.db import IntegrityError, transaction

    from apps.records.models import TaggedItem

    tag = _resoudre(getattr(calepinage, 'company', None), corps)
    # Idempotence portée par la BASE (``unique_together`` de TaggedItem) :
    # une seconde pose lève IntegrityError dans son point de sauvegarde et ne
    # crée rien — ni ligne, ni entrée de journal.
    try:
        with transaction.atomic():
            TaggedItem.objects.create(tag=tag,
                                      content_type=_type_calepinage(),
                                      object_id=calepinage.pk)
        posee = True
    except IntegrityError:
        posee = False
    if posee:
        from .journal import noter

        noter(calepinage, 'Étiquette « %s » posée.' % tag.nom, user=user)
    return etiquettes_du_calepinage(calepinage)


def retirer_etiquette(calepinage, corps, *, user=None):
    """Retire l'étiquette désignée — sans effet si elle n'était pas posée."""
    from apps.records.models import TaggedItem

    tag = _resoudre(getattr(calepinage, 'company', None), corps)
    retires, _detail = (TaggedItem.objects
                        .filter(tag=tag, content_type=_type_calepinage(),
                                object_id=calepinage.pk)
                        .delete())
    if retires:
        from .journal import noter

        noter(calepinage, 'Étiquette « %s » retirée.' % tag.nom, user=user)
    return etiquettes_du_calepinage(calepinage)


def filtrer_par_etiquette(lignes, valeurs):
    """Restreint ``lignes`` aux calepinages qui portent TOUTES les étiquettes.

    Args:
        lignes: le QuerySet de calepinages (déjà borné société).
        valeurs: les ``?etiquette=`` reçus (liste, RÉPÉTABLE). Vide ou absent
            ⇒ ``lignes`` inchangé (un filtre absent ne filtre rien).

    Raises:
        EtiquetteRefusee: une valeur non entière positive — champ
            ``etiquette`` nommé (un filtre ignoré ferait ouvrir le mauvais
            objet, leçon PV22).
    """
    from apps.records.models import TaggedItem

    identifiants = []
    for brut in valeurs or ():
        for morceau in str(brut).split(','):
            texte = morceau.strip()
            if not texte:
                continue
            valeur = _identifiant(texte)
            if valeur is None:
                raise EtiquetteRefusee(
                    'Filtre « etiquette » illisible : un identifiant entier '
                    'positif est attendu (reçu : « %s »).' % texte,
                    champ='etiquette')
            if valeur not in identifiants:
                identifiants.append(valeur)
    if not identifiants:
        return lignes
    type_calepinage = _type_calepinage()
    for tag_id in identifiants:
        # ET logique : un filtre par étiquette, chaînés.
        lignes = lignes.filter(pk__in=TaggedItem.objects.filter(
            tag_id=tag_id, content_type=type_calepinage,
        ).values('object_id'))
    return lignes
