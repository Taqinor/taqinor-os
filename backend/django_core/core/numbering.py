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


def _reserver_monotone(model, prefix, company, plancher, field):
    """Réserve le prochain numéro d'un compteur PERSISTANT (mode monotone).

    Le scan « plus-haut-utilisé + 1 » ne COLLISIONNE jamais, mais il RECULE :
    supprimer le document qui porte le plus haut numéro libère ce numéro, et
    le suivant le réutilise. Pour un registre dont la numérotation doit être
    non réversible (un dossier juridique, une note d'honoraires : le numéro a
    été communiqué à un avocat, à une partie adverse, à un tribunal), on
    persiste le dernier numéro RÉSERVÉ dans ``core.SequenceCounter``
    (primitive NTPLT41, déjà en base) et on repart de là.

    Le compteur est un PLANCHER, jamais la seule source : on prend
    ``max(dernier_réservé, plus_haut_utilisé) + 1``, de sorte qu'une ligne
    insérée hors de ce chemin (reprise de données, fixture) ne puisse jamais
    être écrasée. ``select_for_update`` sur la ligne de compteur rend deux
    créations simultanées sérielles — même garantie que le savepoint + retry
    de ``create_with_reference``, qui reste en place au-dessus. Les TROUS sont
    assumés (un numéro réservé puis abandonné n'est pas rendu) : c'est le prix
    de « ne recule jamais ».
    """
    from django.db import transaction

    from .models import SequenceCounter

    cle = f'ref:{model._meta.label_lower}:{field}:{prefix}'[:100]
    with transaction.atomic():
        ligne, _ = SequenceCounter.objects.select_for_update().get_or_create(
            company=company, cle=cle, defaults={'dernier': 0})
        numero = max(int(ligne.dernier or 0), plancher) + 1
        ligne.dernier = numero
        ligne.save(update_fields=['dernier', 'updated_at'])
    return numero


def next_reference(model, doc_prefix, company, *, padding=4, period='monthly',
                   field='reference', monotonic=False):
    """Prochaine référence libre pour cette société/période.

    Les défauts (padding 4, remise à zéro mensuelle) reproduisent EXACTEMENT
    l'historique 'DEV-202606-0003'. `period` ∈ {'monthly','yearly','none'} pilote
    le seau de remise à zéro ; `padding` la largeur de zéro-padding. La règle
    plus-haut-utilisé+1 (sans trou, race-safe) est inchangée — seuls le radical
    du seau et la largeur de padding varient. `field` nomme le champ porteur de
    la référence (défaut 'reference' — rétro-compatible ; un modèle dont le
    numéro vit ailleurs, ex. `Patient.numero_dossier`, le passe explicitement).

    `monotonic=False` par défaut : comportement historique BIT-IDENTIQUE pour
    les ~53 importeurs existants (fonction PURE, aucune écriture). À `True`,
    le numéro est RÉSERVÉ dans un compteur persistant (cf.
    `_reserver_monotone`) et ne recule donc jamais après une suppression —
    pour un registre dont un numéro déjà communiqué ne doit jamais être
    réattribué. Dans ce mode la fonction ÉCRIT (elle consomme un numéro).
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
    numero = (_reserver_monotone(model, prefix, company, highest, field)
              if monotonic else highest + 1)
    return f"{prefix}-{numero:0{width}d}"


def create_with_reference(model, doc_prefix, company, save_fn, *,
                          padding=4, period='monthly', monotonic=False):
    """Exécute save_fn(reference) dans un savepoint, en réessayant sur les courses de référence.

    save_fn reçoit la référence générée et doit effectuer la création réelle
    (serializer.save(...) ou Model.objects.create(...)) et retourner l'instance.
    Les IntegrityError non liées à la référence sont re-levées immédiatement.
    `padding`/`period`/`monotonic` sont transmis à next_reference (défauts =
    historique).
    """
    last_exc = None
    for _ in range(MAX_ATTEMPTS):
        reference = next_reference(
            model, doc_prefix, company, padding=padding, period=period,
            monotonic=monotonic)
        try:
            with transaction.atomic():
                return save_fn(reference)
        except IntegrityError as exc:
            if 'reference' not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc
