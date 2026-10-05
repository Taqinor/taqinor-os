"""SPL134 — les 3 gardes partagées de ``DevisViewSet`` (déplacement pur
depuis ``views/devis.py``, corps octet-identiques).

Vivent dans leur propre module parce que les mixins d'actions
(``views/devis_*.py``) les appellent et ne peuvent pas importer
``views/devis.py`` (qui importe les mixins en tête : cycle). Leurs imports
function-locaux (``..domain.modifiabilite``, ``..domain.verrou_devis``)
gardent la même profondeur de paquet.

ACAL278 y ajoute ``_pourcentage_saisi`` : la règle UNIQUE de ``taux_tva`` /
``remise_globale`` partagée par ``from-layout`` (``devis_calepinage.py``) et
``auto`` (``devis.py``) — ici, et non dans ``devis.py``, parce que
``devis_calepinage.py`` ne peut pas importer ``devis.py`` (cycle).
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


def _pourcentage_saisi(donnees, champ, defaut):
    """ACAL278 (C-ACAL-142) — lit un pourcentage du corps (``taux_tva``,
    ``remise_globale``) : ``(Decimal, None)`` si valide, ``(None, {champ:
    message})`` sinon — l'appelant répond 400 NOMMÉ, jamais un 500.

    Remplace les deux ``def _dec`` imbriqués de ``from-layout`` et ``auto``,
    qui laissaient passer ``'150'``, ``'NaN'`` ou ``'1e999'`` jusqu'à la
    contrainte ``ck_devis_remise_globale_0_100`` (IntegrityError → 500).
    Règle : absent/vide → ``defaut`` ; sinon fini, entre 0 et 100, au plus
    2 décimales (``DecimalField(max_digits=5, decimal_places=2)``)."""
    from decimal import Decimal, InvalidOperation
    brut = donnees.get(champ)
    if brut in (None, ''):
        return defaut, None
    try:
        valeur = Decimal(str(brut))
    except (InvalidOperation, ValueError, TypeError):
        valeur = None
    if valeur is None or not valeur.is_finite():
        return None, {champ: f'« {champ} » doit être un nombre fini.'}
    if valeur < 0 or valeur > 100:
        return None, {champ: f'« {champ} » doit être compris entre 0 et 100.'}
    if valeur != valeur.quantize(Decimal('0.01')):
        return None, {champ: f'« {champ} » : au plus 2 décimales.'}
    return valeur, None
