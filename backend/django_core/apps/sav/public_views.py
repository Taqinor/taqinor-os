"""Endpoint PUBLIC (sans login) pour le suivi client d'un ticket SAV (FG86).

Accès uniquement via le jeton share_token du ticket.  La réponse ne retourne
que trois champs non-sensibles : référence, statut, date_modification.

Données jamais exposées : cout, chatter (TicketActivity), informations client,
prix d'achat, marge, ou tout autre champ interne.

Protections : X-Robots-Tag noindex sur chaque réponse publique ; throttle
cache-based par IP (30 req/min) sans dépendance externe.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Equipement, Ticket, TicketSatisfaction

MAX_PIECES_JOINTES_PORTAIL = 5


# ── Throttle ─────────────────────────────────────────────────────────────────

class SavPublicThrottle(SimpleRateThrottle):
    """Limite le débit des liens publics SAV par IP (cache-based, sans dépendance)."""
    scope = 'sav_public_link'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien de suivi est invalide ou n'existe pas."},
        status=status.HTTP_404_NOT_FOUND,
    ))


# ── Vue publique ──────────────────────────────────────────────────────────────

# Champs publics autorisés — liste exhaustive (défense en profondeur).
# Tout ajout doit être délibéré ; cout et chatter sont EXCLUS par conception.
_PUBLIC_FIELDS = ('reference', 'statut', 'date_modification')


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def ticket_public_status(request, token):
    """FG86 — Statut public d'un ticket SAV (lecture seule, sans login).

    Résout le ticket par son share_token uniquement (pas de company depuis la
    requête).  Renvoie UNIQUEMENT : reference, statut, date_modification.
    Jamais : cout, chatter, informations client, ou tout champ interne.
    Un token inconnu ou absent retourne 404 sans fuite de données.
    """
    if not token:
        return _not_found()
    try:
        ticket = Ticket.objects.only(
            'share_token', *_PUBLIC_FIELDS,
        ).get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    payload = {field: getattr(ticket, field) for field in _PUBLIC_FIELDS}
    # Statut human-readable (label FR) en complément du code machine.
    payload['statut_display'] = ticket.get_statut_display()
    return _noindex(Response(payload))


# ── XSAV10 — Enquête de satisfaction (CSAT) publique ───────────────────────────

_CLOTURE_STATUTS = (Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def ticket_public_satisfaction(request, token):
    """XSAV10 — Enregistre la satisfaction (CSAT) via le lien client public.

    Résout le ticket par son ``share_token`` uniquement. Refuse : token
    inconnu (404, sans fuite), ticket pas encore résolu/clôturé (400), une
    seconde réponse pour le même ticket (409 — une seule réponse par ticket).
    Aucune donnée interne (chatter, coût, informations client) n'est jamais
    exposée ou requise par cet endpoint — seuls ``note`` (1-5) et
    ``commentaire`` (optionnel) sont acceptés."""
    if not token:
        return _not_found()
    try:
        ticket = Ticket.objects.only(
            'id', 'company_id', 'statut', 'share_token').get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    if ticket.statut not in _CLOTURE_STATUTS:
        return _noindex(Response(
            {'detail': "Ce ticket n'est pas encore résolu — "
                       "l'enquête de satisfaction n'est pas disponible."},
            status=status.HTTP_400_BAD_REQUEST))

    if TicketSatisfaction.objects.filter(ticket=ticket).exists():
        return _noindex(Response(
            {'detail': 'Une réponse a déjà été enregistrée pour ce ticket.'},
            status=status.HTTP_409_CONFLICT))

    try:
        note = int(request.data.get('note'))
    except (TypeError, ValueError):
        return _noindex(Response(
            {'detail': 'Note invalide (entier de 1 à 5 attendu).'},
            status=status.HTTP_400_BAD_REQUEST))
    if note < 1 or note > 5:
        return _noindex(Response(
            {'detail': 'Note invalide (entier de 1 à 5 attendu).'},
            status=status.HTTP_400_BAD_REQUEST))
    commentaire = (request.data.get('commentaire') or '').strip()[:4000]

    try:
        satisfaction = TicketSatisfaction.objects.create(
            company_id=ticket.company_id,
            ticket=ticket, note=note, commentaire=commentaire)
    except Exception:  # noqa: BLE001 — filet de course (OneToOne race)
        return _noindex(Response(
            {'detail': 'Une réponse a déjà été enregistrée pour ce ticket.'},
            status=status.HTTP_409_CONFLICT))

    return _noindex(Response(
        {'note': satisfaction.note, 'commentaire': satisfaction.commentaire},
        status=status.HTTP_201_CREATED))


# ── XSAV19 — Page publique « Signaler un problème » via QR équipement ────────

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def equipement_public_signaler(request, token):
    """XSAV19 — Crée un ticket correctif depuis la page publique de
    l'équipement (scan QR), SANS login.

    Résout l'équipement par son ``public_token`` UNIQUEMENT (distinct du
    jeton interne ``equipement_token`` — celui-ci reste deviné/interne, ne
    doit jamais être utilisé pour créer un ticket public). Un token inconnu
    ou absent renvoie 404 sans fuite de données. Le ticket créé est lié à
    l'équipement/client résolus côté serveur — jamais depuis le corps.

    Anti-spam : honeypot (``site_web`` — un bot qui remplit ce champ caché
    voit un 201 factice sans qu'aucun ticket ne soit créé) + throttle DRF
    (30 req/min/IP, même limite que les autres endpoints publics SAV).

    Aucune donnée interne (cout, chatter, autres tickets, informations
    société) n'est jamais exposée sur cette page — seuls description,
    téléphone et une photo optionnelle sont acceptés en entrée."""
    if not token:
        return _not_found()
    try:
        equipement = Equipement.objects.select_related(
            'installation', 'installation__client', 'client_vente',
        ).get(public_token=token)
    except Equipement.DoesNotExist:
        return _not_found()

    # Honeypot : un champ caché que seuls les bots remplissent. Réponse 201
    # factice (aucune trace du piège pour l'appelant) sans rien créer.
    if (request.data.get('site_web') or '').strip():
        return _noindex(Response(
            {'detail': 'Signalement enregistré.'},
            status=status.HTTP_201_CREATED))

    description = (request.data.get('description') or '').strip()[:4000]
    if not description:
        return _noindex(Response(
            {'detail': 'Merci de décrire le problème.'},
            status=status.HTTP_400_BAD_REQUEST))
    telephone = (request.data.get('telephone') or '').strip()[:40]

    installation = equipement.installation
    # AUD520 — un équipement vendu au comptoir (XPOS9 : `installation` vide,
    # `client_vente` renseigné) porte son client sur `client_vente`. Avant ce
    # correctif, le client n'était résolu QUE via `installation.client` : tout
    # le parc vendu au comptoir renvoyait 404 au scan de son QR — alors que
    # les actions `etiquettes`/`partage_qr` génèrent bien cette étiquette
    # publique pour lui.
    client = (getattr(installation, 'client', None)
              if installation is not None else equipement.client_vente)
    if client is None:
        # Défense en profondeur : un équipement sans chantier NI client de
        # vente n'a personne à qui rattacher le ticket — filet de sécurité.
        return _noindex(Response(
            {'detail': 'Équipement introuvable.'}, status=status.HTTP_404_NOT_FOUND))

    corps = description
    if telephone:
        corps += f'\n\nTéléphone communiqué : {telephone}'

    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Ticket.objects.create(
            reference=ref, company=equipement.company, client=client,
            installation=installation, equipement=equipement,
            type=Ticket.Type.CORRECTIF, description=corps,
            date_ouverture=timezone.localdate(),
        )
    # AUD519 — le signalement QR public porte la même échéance SLA que le
    # chemin manuel (sans quoi il était exclu des scans quotidiens).
    from .services import poser_sla_due_at

    ticket = poser_sla_due_at(create_with_reference(
        Ticket, 'SAV', equipement.company, _create))

    # Photo optionnelle — pièce jointe MinIO (apps.records, foundation app).
    photo = request.FILES.get('photo')
    if photo is not None:
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment

        data, err = store_attachment(photo)
        if data is not None:
            Attachment.objects.create(
                company=equipement.company,
                content_type=ContentType.objects.get_for_model(Ticket),
                object_id=ticket.pk, **data)

    return _noindex(Response(
        {'reference': ticket.reference}, status=status.HTTP_201_CREATED))


# ── NTSRV2 — Formulaire portail client → ticket SAV (public, tokenisé) ───────

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def portail_creer_ticket(request):
    """NTSRV2 — Crée un ticket SAV depuis le formulaire du portail client.

    Le client est résolu CÔTÉ SERVEUR par le jeton d'accès de son compte
    portail (``portail.ComptePortailClient.token_acces``, lu via
    ``apps.portail.selectors`` — jamais un import de ses modèles, jamais une
    2ᵉ table cliente) : la société n'est donc JAMAIS lue du corps. Un jeton
    inconnu, vide ou révoqué renvoie 404 sans fuite d'information (aucune
    distinction entre « inexistant » et « révoqué »).

    Renvoie un numéro de suivi : la ``reference`` du ticket + le jeton public
    de suivi (``share_token``, FG86) pour que le client suive l'avancement
    sans compte.

    Anti-spam : honeypot ``site_web`` (201 factice, rien créé) + throttle DRF
    (30 req/min/IP, même limite que les autres endpoints publics SAV).
    """
    from apps.portail.selectors import client_par_token_acces

    token = (request.data.get('token') or '').strip()
    resolu = client_par_token_acces(token)
    if resolu is None:
        return _not_found()
    company_id, client_id = resolu
    if not client_id:
        return _not_found()

    # Honeypot : réponse 201 factice, aucune trace du piège pour l'appelant.
    if (request.data.get('site_web') or '').strip():
        return _noindex(Response(
            {'reference': '', 'detail': 'Demande enregistrée.'},
            status=status.HTTP_201_CREATED))

    from .serializers import PortailTicketCreateSerializer

    serializer = PortailTicketCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return _noindex(Response(serializer.errors,
                                 status=status.HTTP_400_BAD_REQUEST))
    donnees = serializer.validated_data

    from apps.crm.models import Client
    from apps.ventes.utils.references import create_with_reference
    from authentication.models import Company

    company = Company.objects.filter(pk=company_id).first()
    client = Client.objects.filter(pk=client_id, company_id=company_id).first()
    if company is None or client is None:
        return _not_found()

    sujet = donnees['sujet'].strip()
    description = (donnees.get('description') or '').strip()
    priorite = donnees.get('priorite') or Ticket.Priorite.NORMALE
    corps = f'{sujet}\n\n{description}' if description else sujet

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
            priorite=priorite,
            canal_ouverture=Ticket.CanalOuverture.PORTAIL,
            date_ouverture=timezone.localdate(),
            description=corps[:4000])

    from .services import poser_sla_due_at

    ticket = poser_sla_due_at(
        create_with_reference(Ticket, 'SAV', company, _create))

    # Note initiale au chatter (acteur = None : la demande vient du client).
    from . import activity

    libelle_priorite = dict(Ticket.Priorite.choices).get(priorite, priorite)
    activity.log_note(
        ticket, None,
        f'Demande déposée depuis le portail client — « {sujet} »'
        + (f'\n\n{description}' if description else '')
        + f'\n\nPriorité déclarée par le client : {libelle_priorite}')

    # Pièces jointes optionnelles — magasin MinIO existant (apps.records).
    fichiers = list(request.FILES.getlist('pieces_jointes') or [])
    photo = request.FILES.get('photo')
    if photo is not None:
        fichiers.append(photo)
    if fichiers:
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import store_attachment

        for fichier in fichiers[:MAX_PIECES_JOINTES_PORTAIL]:
            data, _err = store_attachment(fichier)
            if data is not None:
                Attachment.objects.create(
                    company=company,
                    content_type=ContentType.objects.get_for_model(Ticket),
                    object_id=ticket.pk, **data)

    return _noindex(Response({
        'reference': ticket.reference,
        'numero_suivi': ticket.reference,
        'suivi_token': ticket.ensure_share_token(),
    }, status=status.HTTP_201_CREATED))
