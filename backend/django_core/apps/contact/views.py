from django.core.mail import send_mail
from django.conf import settings
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle


class ContactThrottle(AnonRateThrottle):
    rate = '5/hour'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ContactThrottle])
def contact(request):
    # PARKED switch: when the contact form is disabled the endpoint is treated as
    # non-existent (404) and never accepts a submission or sends email.
    if not getattr(settings, 'CONTACT_FORM_ENABLED', False):
        raise Http404('Contact form is disabled.')

    nom = (request.data.get('nom', '') or '').strip()[:100]
    numero = (request.data.get('numero', '') or '').strip()[:20]
    societe = (request.data.get('societe', '') or '').strip()[:100]
    email = (request.data.get('email', '') or '').strip()[:150]
    message = (request.data.get('message', '') or '').strip()[:2000]

    if not all([nom, email, message]):
        return Response({'detail': 'Nom, email et message sont obligatoires.'}, status=400)

    if '@' not in email or '.' not in email.split('@')[-1]:
        return Response({'detail': 'Adresse email invalide.'}, status=400)

    sujet = f'[TAQINOR] Nouvelle demande — {nom}'
    corps = (
        f'Nom       : {nom}\n'
        f'Téléphone : {numero or "—"}\n'
        f'Société   : {societe or "—"}\n'
        f'Email     : {email}\n'
        f'\nMessage :\n{message}\n'
    )

    try:
        send_mail(
            subject=sujet,
            message=corps,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
            fail_silently=False,
        )
    except Exception:
        return Response(
            {'detail': 'Erreur lors de l\'envoi. Veuillez réessayer.'},
            status=500,
        )

    return Response({'detail': 'Message envoyé. Nous vous contacterons très bientôt.'})
