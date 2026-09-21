"""Vues PUBLIQUES du portail client (PROJ37, ZPRJ7).

Endpoints non authentifiés, accédés par jeton :
* ``portail_avancement`` (``PortailProjetToken``) — expose UNIQUEMENT
  l'avancement non financier d'un projet (phases, jalons, avancement global).
* ``evaluation_projet`` (``EvaluationProjet``, ZPRJ7) — enquête de
  satisfaction client (CSAT) : GET affiche le formulaire, POST enregistre la
  note (UN SEUL dépôt).

AUCUN coût, budget, marge, P&L ni ``facturation_pct`` ne traverse jamais ces
frontières — voir ``selectors.portail_avancement_client``.
"""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import selectors
from .models import EvaluationProjet, PortailProjetToken


@api_view(['GET'])
@permission_classes([AllowAny])
def portail_avancement(request, token):
    """Avancement client d'un projet par JETON public (PROJ37) — sans coûts.

    Le jeton doit exister ET être ``actif`` (sinon 404 — on ne distingue pas un
    jeton inconnu d'un jeton révoqué, pour ne rien divulguer). La société est
    portée par le jeton (jamais lue d'un paramètre). Lecture seule, données
    strictement non financières.
    """
    token_obj = PortailProjetToken.objects.filter(
        token=token, actif=True).select_related('projet').first()
    if token_obj is None:
        return Response({'detail': 'Lien invalide ou expiré.'}, status=404)
    return Response(
        selectors.portail_avancement_client(token_obj.projet))


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def evaluation_projet(request, token):
    """Enquête de satisfaction client (CSAT) par JETON public (ZPRJ7).

    GET — affiche le formulaire : ``projet`` (code/nom, AUCUNE donnée
    interne), ``deja_soumis`` (booléen), et la note/commentaire DÉJÀ soumis le
    cas échéant (relecture, jamais une réécriture possible). POST — enregistre
    ``note`` (1-5, obligatoire) et ``commentaire`` (optionnel) : REFUSÉ (400)
    si une note a déjà été soumise (dépôt UNIQUE) ou si ``note`` est absente/
    hors [1, 5]. ``soumis_le`` est posé CÔTÉ SERVEUR. Jeton inconnu → 404
    (on ne distingue pas un jeton révoqué — il n'y a pas de révocation ici,
    contrairement au portail d'avancement). AUCUN coût/budget/marge n'est
    jamais exposé sur cette vue publique.
    """
    evaluation = EvaluationProjet.objects.filter(
        token=token).select_related('projet').first()
    if evaluation is None:
        return Response({'detail': 'Lien invalide.'}, status=404)

    if request.method == 'GET':
        return Response({
            'projet': {
                'code': evaluation.projet.code,
                'nom': evaluation.projet.nom,
            },
            'deja_soumis': evaluation.soumis_le is not None,
            'note': evaluation.note,
            'commentaire': evaluation.commentaire,
        })

    # POST — dépôt unique.
    if evaluation.soumis_le is not None:
        return Response(
            {'detail': 'Une évaluation a déjà été soumise pour ce projet.'},
            status=400)

    note_raw = request.data.get('note')
    try:
        note = int(note_raw)
    except (TypeError, ValueError):
        return Response(
            {'note': 'La note (1 à 5) est obligatoire.'}, status=400)
    if note < 1 or note > 5:
        return Response(
            {'note': 'La note doit être comprise entre 1 et 5.'}, status=400)

    commentaire = request.data.get('commentaire', '') or ''
    evaluation.note = note
    evaluation.commentaire = str(commentaire)[:5000]
    evaluation.soumis_le = timezone.now()
    evaluation.save(update_fields=['note', 'commentaire', 'soumis_le'])
    return Response({
        'note': evaluation.note, 'commentaire': evaluation.commentaire,
        'soumis_le': evaluation.soumis_le,
    })
