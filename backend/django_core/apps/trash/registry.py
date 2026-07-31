"""NTUX7 — registre des RESTAURATEURS de la corbeille transverse.

La corbeille ne restaure JAMAIS un enregistrement en écrivant directement dans
le modèle d'une autre app (règle de frontière inter-apps, CLAUDE.md) : chaque
app cible enregistre ICI, depuis son propre `apps.py` `ready()`, la fonction de
son `services.py` qui sait remettre l'enregistrement en état.

    # apps/crm/apps.py
    def ready(self):
        from apps.trash.registry import enregistrer_restaurateur
        from apps.crm.services import restaurer_lead
        enregistrer_restaurateur('crm.lead', restaurer_lead)

La fonction reçoit l'``ElementSupprime`` et renvoie l'objet restauré (ou
``None`` s'il a disparu). Tant qu'aucune app n'a enregistré sa clé, la
restauration retombe sur le repli GÉNÉRIQUE de `services.restaurer` (bascule du
drapeau de soft-delete résolu DYNAMIQUEMENT par `content_type`, toujours sans
import de modèle étranger).
"""
_RESTAURATEURS: dict = {}


def _normaliser(cle):
    return str(cle).strip().lower()


def enregistrer_restaurateur(cle, fonction):
    """Enregistre le restaurateur de ``cle`` (ex. ``'crm.lead'``).

    Idempotent au re-``ready()`` (le dernier enregistrement gagne) — un
    ``ready()`` peut être rejoué en test.
    """
    _RESTAURATEURS[_normaliser(cle)] = fonction
    return fonction


def restaurateur(cle):
    """Restaurateur enregistré pour ``cle``, ou ``None``."""
    return _RESTAURATEURS.get(_normaliser(cle))


def cles_enregistrees():
    """Clés couvertes par un restaurateur dédié (triées) — utile au diagnostic."""
    return sorted(_RESTAURATEURS)
