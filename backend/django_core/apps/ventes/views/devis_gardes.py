"""SPL134 — les 3 gardes partagées de ``DevisViewSet`` (déplacement pur
depuis ``views/devis.py``, corps octet-identiques).

Vivent dans leur propre module parce que les mixins d'actions
(``views/devis_*.py``) les appellent et ne peuvent pas importer
``views/devis.py`` (qui importe les mixins en tête : cycle). Leurs imports
function-locaux (``..domain.modifiabilite``, ``..domain.verrou_devis``)
gardent la même profondeur de paquet.
"""
from rest_framework import status
from rest_framework.response import Response


def _refus_modifiabilite(devis, geste):
    """QJR516 — la garde d'édition UNIQUE des vues : ``True`` si le geste
    est REFUSÉ sur ce devis (prédicat ``domain/modifiabilite``). L'appelant
    répond alors ``_reponse_non_modifiable`` (409). Lit le statut, ne
    l'écrit jamais (règle #4)."""
    from ..domain.modifiabilite import est_modifiable
    return not est_modifiable(devis, geste)


def _reponse_non_modifiable(devis, geste, message_statut=None):
    """QJR516 — la réponse 409 ``{detail, statut, revision_possible}`` d'un
    geste refusé. ``message_statut`` (avec ``%s`` = statut affiché) conserve
    le texte historique d'une garde existante pour un devis ACTIF ; un devis
    remplacé ou archivé reçoit la raison du prédicat."""
    from ..domain.modifiabilite import verdict
    v = verdict(devis, geste)
    if message_statut and devis.is_active:
        detail = message_statut % devis.get_statut_display()
    else:
        detail = v['raison_non_modifiable']
    return Response(
        {'detail': detail, 'statut': devis.statut,
         'revision_possible': v['revision_possible']},
        status=status.HTTP_409_CONFLICT)


def _refus_verrou(devis, request):
    """QJR545 — ``Response`` 409 si ``expected_updated_at`` est fourni et
    diffère du jeton en base ; ``None`` sinon (champ absent ⇒ inchangé)."""
    from ..domain.verrou_devis import verifier_jeton
    charge = verifier_jeton(devis, request.data)
    if charge is None:
        return None
    return Response(charge, status=status.HTTP_409_CONFLICT)
