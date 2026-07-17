"""Service de numérotation de documents anti-collision (fondation — ARC6).

Radical de fondation `core.numbering` : la fabrique de références race-safe
(DEV-/BC-/FAC-YYYYMM-NNNN) longtemps logée dans `apps/ventes/utils/references.py`
alors que ~15 apps l'importent en travers des frontières d'apps — l'équivalent
d'`ir.sequence` d'Odoo qui vivrait dans le module Sales. L'algorithme (max-utilisé
+1 par société+période, savepoint+retry) est relogé ICI, dans la couche fondation
(`core` ne dépend d'aucune app métier — la fonction reçoit en paramètre le modèle /
préfixe / société dont elle a besoin, elle n'importe donc aucune app domaine) ;
`apps.ventes.utils.references` devient un shim de ré-export bit-identique pour que
les importeurs existants continuent de marcher sans édit.

L'ancienne logique comptait les lignes existantes puis `count+1`, ce qui entre en
collision dès qu'un document est supprimé ou que les numéros ne correspondent pas
au compte (le compte rétrécit mais le plus haut numéro utilisé reste). À la place :

  1. on prend le plus haut numéro de queue réellement utilisé pour cette société
     et ce préfixe de période, puis on ajoute 1 — les trous et les lignes
     préexistantes sont toujours résolus ;
  2. on réessaie quelques fois sur une IntegrityError de référence dupliquée pour
     que deux sauvegardes concurrentes ne puissent jamais planter — le perdant de
     la course prend simplement le numéro suivant.

Les références restent par société (scopées par locataire) ; la contrainte d'unicité
en base (company, reference) est l'arbitre final.
"""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

_SUFFIX_RE = re.compile(r'-(\d+)$')
MAX_ATTEMPTS = 5


def _period_segment(period):
    """Segment de date pour la période de remise à zéro. Défaut mensuel (historique)."""
    if period == 'yearly':
        return timezone.now().strftime('%Y')
    if period == 'none':
        return ''
    # 'monthly' (et toute valeur inconnue) = comportement historique YYYYMM.
    return timezone.now().strftime('%Y%m')


def _bucket_prefix(doc_prefix, period):
    """Radical de recherche/affichage : 'DEV-202606', 'DEV-2026' ou 'DEV'."""
    seg = _period_segment(period)
    return f"{doc_prefix}-{seg}" if seg else str(doc_prefix)


def next_reference(model, doc_prefix, company, *, padding=4, period='monthly',
                   field='reference'):
    """Prochaine référence libre pour cette société/période.

    Les défauts (padding 4, remise à zéro mensuelle) reproduisent EXACTEMENT
    l'historique 'DEV-202606-0003'. `period` ∈ {'monthly','yearly','none'} pilote
    le seau de remise à zéro ; `padding` la largeur de zéro-padding. La règle
    plus-haut-utilisé+1 (sans trou, race-safe) est inchangée — seuls le radical
    du seau et la largeur de padding varient. `field` nomme le champ porteur de
    la référence (défaut 'reference' — rétro-compatible ; un modèle dont le
    numéro vit ailleurs, ex. `Patient.numero_dossier`, le passe explicitement).
    """
    prefix = _bucket_prefix(doc_prefix, period)
    refs = model.objects.filter(
        company=company, **{f'{field}__startswith': prefix},
    ).values_list(field, flat=True)
    highest = 0
    for ref in refs:
        m = _SUFFIX_RE.search(ref)
        if m:
            highest = max(highest, int(m.group(1)))
    try:
        width = max(1, int(padding))
    except (TypeError, ValueError):
        width = 4
    return f"{prefix}-{highest + 1:0{width}d}"


def create_with_reference(model, doc_prefix, company, save_fn, *,
                          padding=4, period='monthly'):
    """Exécute save_fn(reference) dans un savepoint, en réessayant sur les courses de référence.

    save_fn reçoit la référence générée et doit effectuer la création réelle
    (serializer.save(...) ou Model.objects.create(...)) et retourner l'instance.
    Les IntegrityError non liées à la référence sont re-levées immédiatement.
    `padding`/`period` sont transmis à next_reference (défauts = historique).
    """
    last_exc = None
    for _ in range(MAX_ATTEMPTS):
        reference = next_reference(
            model, doc_prefix, company, padding=padding, period=period)
        try:
            with transaction.atomic():
                return save_fn(reference)
        except IntegrityError as exc:
            if 'reference' not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc
