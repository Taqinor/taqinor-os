"""Services (écriture/orchestration) de l'app `apps.transport`.

Comme `selectors.py` (lecture), destiné à être importé PAR D'AUTRES APPS en
LOCAL/FONCTION (jamais au niveau module) — toute référence à un document
d'une autre app passe par une FK par chaîne ou par le sélecteur/service dédié
de cette app cible, jamais par un import direct de ses `models`.

Framework-agnostic : ces fonctions ne lèvent JAMAIS d'exception DRF — elles
renvoient `None`/une valeur ou un message d'erreur texte ; c'est à la vue
(`views.py`) de traduire en `rest_framework.exceptions.ValidationError` (400).
Une `django.core.exceptions.ValidationError` levée depuis `Model.save()` ne
serait PAS rattrapée par DRF et retomberait en 500 — piège déjà payé
ailleurs dans ce dépôt.
"""


def attribuer_numero(ordre):
    """NTLOG1 — pose `ordre.numero` (anti-collision, plus-haut-utilisé+1 par
    société) via `core.numbering.next_reference` — JAMAIS un `count()+1`
    (ARC6). No-op si déjà posé (idempotent)."""
    if ordre.numero:
        return ordre
    from core.numbering import next_reference

    from .models import OrdreTransport

    ordre.numero = next_reference(
        OrdreTransport, 'OT', ordre.company, field='numero')
    ordre.save(update_fields=['numero'])
    return ordre
