"""NTMOB30 — Transcription vocale SYNCHRONE et générique (notes de terrain).

Le pipeline Whisper self-hosted existe déjà (`apps.chat.tasks`, S10/S11) mais
n'était atteignable qu'ATTACHÉ à un mémo vocal de conversation. NTMOB30 a besoin
de dicter une note sur la chatter d'un LEAD ou d'un TICKET SAV : l'audio n'a
alors aucune pièce jointe à porter, seul le TEXTE compte (il part ensuite par
les endpoints `noter` déjà existants de chaque app).

Cet endpoint expose donc le MÊME appel de service (`tasks._call_transcribe`,
jamais un second client Whisper) en synchrone : audio en entrée, texte en
sortie, rien n'est stocké. Transcription désactivée (`CHAT_TRANSCRIPTION_ENABLED`
faux ou service muet) → `{'enabled': False}` et le front bascule sur la saisie
clavier, jamais une erreur.
"""
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import tasks

# Borne de taille : une note de terrain dictée, pas un enregistrement d'heure.
TAILLE_MAX_OCTETS = 10 * 1024 * 1024


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def transcrire(request):
    """``POST chat/transcrire/`` (multipart, champ ``file``) → ``{enabled, texte}``."""
    fichier = request.FILES.get('file')
    if fichier is None:
        return Response({'detail': 'Aucun fichier audio.'}, status=400)
    if fichier.size and fichier.size > TAILLE_MAX_OCTETS:
        return Response({'detail': 'Enregistrement trop long.'}, status=400)

    if not tasks._transcription_enabled():
        return Response({'enabled': False, 'texte': ''})

    try:
        resultat = tasks._call_transcribe(
            fichier.read(),
            filename=getattr(fichier, 'name', None) or 'note.webm',
            mime=getattr(fichier, 'content_type', None) or 'audio/webm',
            sender=request.user,
        )
    except Exception:
        # Panne réseau/service : ce n'est PAS un chemin bloquant — l'utilisateur
        # tape sa note au clavier comme avant.
        return Response({'enabled': False, 'texte': ''})

    if not resultat.get('enabled', True):
        return Response({'enabled': False, 'texte': ''})
    return Response({
        'enabled': True,
        'texte': (resultat.get('text') or '').strip(),
        'langue': resultat.get('lang') or '',
    })
