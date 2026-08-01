"""ODY25 — ``records`` journalise les bascules d'applications (chatter ARC8).

Le JOURNAL D'INSTALLATION de la boutique (« qui a activé quoi, quand ») n'a PAS
de modèle dédié : il vit dans le chatter GÉNÉRIQUE ``records.Activity`` (ARC8),
dont c'est exactement la raison d'être — ARC8 existe pour faire CONVERGER les 13
modèles ``*Activity`` maison, pas pour en accueillir un 14ᵉ. Conséquences
voulues : **zéro migration**, et une isolation multi-tenant STRUCTURELLE (la
cible du chatter est le ``core.ModuleToggle``, qui porte déjà sa société — la
société du journal n'est donc jamais lue d'une requête).

POURQUOI L'ABONNÉ EST ICI ET PAS DANS ``core``. L'émetteur est
``core.feature_flags`` (les deux seuls sites qui écrivent un ``ModuleToggle``),
et le patron émetteur=abonné aurait voulu un ``core/receivers.py``. Impossible :
``records.services`` (le SEUL point d'écriture autorisé du chatter, ARC8)
importe les ``selectors`` de ``crm``/``ventes``/``stock`` pour VX210(c) — un
import ``core → records.services`` créerait donc la chaîne
``core → apps.crm`` que le contrat import-linter
``core-foundation-is-a-base-layer`` interdit. Poser l'abonné dans ``records``
respecte les DEUX invariants à la fois : ``core`` reste une couche de base, et
le chatter garde son point d'écriture unique. ``records`` n'importe rien de
``core.models`` en retour — le toggle arrive PAR LE SIGNAL, jamais par un
import.
"""
from django.dispatch import receiver

from core import events

from .models import Activity
from .services import log_activity


@receiver(events.module_toggled, dispatch_uid='records_ody25_journal_modules')
def journaliser_bascule_module(sender, **kwargs):
    """Historise une bascule de module dans le chatter générique (ARC8).

    Écrit UNE entrée ``kind=modification`` sur le ``ModuleToggle`` basculé :
    ``field='actif'``, ``old_value``/``new_value`` = « Installée » /
    « Désinstallée », ``body`` = le motif (``ModuleToggle.raison``), auteur =
    l'utilisateur passé par le service (toujours posé côté serveur, jamais lu
    d'un corps de requête). ``core.feature_flags`` n'émet que sur un
    FRANCHISSEMENT réel : ce récepteur n'a donc aucune bascule no-op à filtrer.
    """
    from core.feature_flags import ACTIF_DESINSTALLEE, ACTIF_INSTALLEE

    toggle = kwargs.get('toggle')
    if toggle is None or toggle.pk is None:
        return
    actif = bool(kwargs.get('actif'))
    nouveau = ACTIF_INSTALLEE if actif else ACTIF_DESINSTALLEE
    ancien = ACTIF_DESINSTALLEE if actif else ACTIF_INSTALLEE
    log_activity(
        toggle,
        Activity.Kind.MODIFICATION,
        user=kwargs.get('user'),
        field='actif',
        field_label='Application',
        old_value=ancien,
        new_value=nouveau,
        body=kwargs.get('raison') or '',
        # Explicite bien que ce soit aussi le défaut (``target.company``) : la
        # société du journal est celle du TOGGLE, jamais celle d'une requête.
        company=toggle.company,
    )
