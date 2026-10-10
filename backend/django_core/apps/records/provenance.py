"""AMET22 (D-PROVENANCE) — primitive « saisi par un humain » partagée.

Généralise le motif ``Devis.overrides`` / ``prix_negocie`` à tout modèle
porteur d'un champ ``saisies_humaines`` (liste de noms de champs, triée, sans
doublon) : une valeur saisie par un humain n'est jamais écrasée par un
écrivain automatique. Aucun ``save()`` implicite : l'appelant sauve.

``records`` est une app de FONDATION : ce module ne connaît la cible que par
duck-typing (attribut ``saisies_humaines``), jamais par import d'une app métier.
Contrat partagé : ``apps/records/contract_samples/provenance.json``.
"""
from .models import Activity
from .services import log_activity

ATTRIBUT = 'saisies_humaines'
MESSAGE_REFUS = 'écriture automatique refusée'


def saisies_humaines(obj):
    """Liste triée, sans doublon, des champs saisis par un humain sur ``obj``."""
    return sorted({str(c) for c in (getattr(obj, ATTRIBUT, None) or [])})


def marquer_saisie_humaine(obj, champs):
    """Ajoute ``champs`` à ``obj.saisies_humaines`` (trié, sans doublon).

    Ne sauve pas : l'appelant appelle ``save()``. Renvoie la nouvelle liste.
    """
    valeurs = sorted(set(saisies_humaines(obj)) | {str(c) for c in champs})
    setattr(obj, ATTRIBUT, valeurs)
    return valeurs


def ecrire_si_libre(obj, champ, valeur, *, journal=True, user=None):
    """Écrit ``valeur`` dans ``obj.<champ>`` sauf si ce champ a été saisi
    par un humain.

    Returns:
        ``True`` si la valeur a été posée (sans ``save()``), ``False`` si le
        champ figure dans ``saisies_humaines`` — l'écriture est alors refusée
        et, si ``journal``, le refus est journalisé dans le chatter générique.
    """
    if champ in saisies_humaines(obj):
        if journal and getattr(obj, 'pk', None) is not None:
            log_activity(
                obj, Activity.Kind.MODIFICATION, user=user, field=champ,
                old_value=str(getattr(obj, champ, '') or ''),
                new_value='' if valeur is None else str(valeur),
                body=MESSAGE_REFUS)
        return False
    setattr(obj, champ, valeur)
    return True
