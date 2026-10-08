"""Endpoint PUBLIC (sans login) pour le suivi client d'un ticket SAV (FG86).

Accès uniquement via le jeton share_token du ticket.  La réponse ne retourne
que trois champs non-sensibles : référence, statut, date_modification.

Données jamais exposées : cout, chatter (TicketActivity), informations client,
prix d'achat, marge, ou tout autre champ interne.

Protections : X-Robots-Tag noindex sur chaque réponse publique ; throttle
cache-based par IP (30 req/min) sans dépendance externe.
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Equipement, Ticket, TicketSatisfaction

MAX_PIECES_JOINTES_PORTAIL = 5
# ASAV24 — fenêtre de rejeu d'un signalement public identique (5 min).
FENETRE_REJEU_SIGNALEMENT_S = 300
# ASAV30 — motif posé par la fusion (``TicketViewSet.fusionner``).
PREFIXE_MOTIF_DOUBLON = 'Doublon de '


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


def _csat_detaille_actif(company_id):
    """NTSRV23 — la société collecte-t-elle les sous-notes détaillées ?

    LECTURE SEULE (jamais un ``get_or_create`` : une page publique ne crée
    pas de réglage). Société sans réglage enregistré → ``False``, donc
    formulaire public strictement inchangé."""
    from .models import SavSlaSettings

    if company_id is None:
        return False
    return bool(SavSlaSettings.objects
                .filter(company_id=company_id)
                .values_list('csat_detaille_actif', flat=True)
                .first())


def _valider_sous_notes(brut):
    """NTSRV23 — normalise ``sous_notes`` ou lève un message FRANÇAIS qui
    NOMME la sous-note fautive.

    Toutes les clés sont OPTIONNELLES ; la liste est FERMÉE (une clé inconnue
    est refusée, jamais stockée en silence) ; chaque valeur est un entier
    1-5. ``None``/absent/vide → ``None`` (aucune sous-note)."""
    from .models import TicketSatisfaction

    if brut in (None, '', {}):
        return None, None
    if not isinstance(brut, dict):
        return None, ('Sous-notes invalides : un objet '
                      '{rapidite, courtoisie, resolution} est attendu.')
    propre = {}
    for cle, valeur in brut.items():
        if cle not in TicketSatisfaction.SOUS_NOTES_CLES:
            return None, f'Sous-note inconnue : « {cle} ».'
        if valeur in (None, ''):
            continue
        libelle = TicketSatisfaction.SOUS_NOTES_LIBELLES.get(cle, cle)
        try:
            note = int(valeur)
        except (TypeError, ValueError):
            return None, (f'{libelle} : note invalide (entier de 1 à 5 '
                          'attendu).')
        if note < 1 or note > 5:
            return None, (f'{libelle} : note invalide (entier de 1 à 5 '
                          'attendu).')
        propre[cle] = note
    return (propre or None), None


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
            # ``company`` : NTSRV23 lit le drapeau d'affichage de la société ;
            # sans lui, l'accès déclencherait une requête différée par appel.
            'share_token', 'company', 'annule', 'motif_annulation',
            *_PUBLIC_FIELDS,
        ).get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    payload = {field: getattr(ticket, field) for field in _PUBLIC_FIELDS}
    # Statut human-readable (label FR) en complément du code machine.
    payload['statut_display'] = ticket.get_statut_display()
    # ASAV30 — un ticket ANNULÉ (drapeau, jamais une valeur de ``statut``) ne
    # s'affiche plus « Nouveau » : « Annulé », avec la référence du ticket
    # principal quand il a été fusionné (motif « Doublon de <référence> »).
    payload['annule'] = bool(ticket.annule)
    payload['fusionne_dans_reference'] = None
    if ticket.annule:
        payload['statut_display'] = 'Annulé'
        motif = (ticket.motif_annulation or '').strip()
        if motif.startswith(PREFIXE_MOTIF_DOUBLON):
            payload['fusionne_dans_reference'] = (
                motif[len(PREFIXE_MOTIF_DOUBLON):].strip() or None)
    # NTSRV23 — INDICATION D'AFFICHAGE (pas une donnée du ticket) : dit à la
    # page publique si elle doit proposer les trois sous-notes optionnelles.
    # False tant que la société ne l'a pas activé → formulaire inchangé.
    payload['csat_detaille_actif'] = _csat_detaille_actif(ticket.company_id)
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
            'id', 'company_id', 'statut', 'share_token', 'annule',
        ).get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    # ASAV30 — pas de note de satisfaction sur un ticket annulé / fusionné.
    if ticket.annule:
        return _noindex(Response(
            {'detail': 'Ce ticket a été annulé.'},
            status=status.HTTP_409_CONFLICT))

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

    # NTSRV23 — sous-notes détaillées, UNIQUEMENT si la société les a
    # activées. Flag OFF = elles sont simplement IGNORÉES (jamais un refus
    # nouveau sur un formulaire qui, lui, ne les propose pas) : le
    # comportement d'aujourd'hui reste strictement identique.
    sous_notes = None
    if _csat_detaille_actif(ticket.company_id):
        sous_notes, erreur = _valider_sous_notes(request.data.get('sous_notes'))
        if erreur:
            return _noindex(Response(
                {'detail': erreur}, status=status.HTTP_400_BAD_REQUEST))

    try:
        satisfaction = TicketSatisfaction.objects.create(
            company_id=ticket.company_id,
            ticket=ticket, note=note, commentaire=commentaire,
            sous_notes=sous_notes)
    except Exception:  # noqa: BLE001 — filet de course (OneToOne race)
        return _noindex(Response(
            {'detail': 'Une réponse a déjà été enregistrée pour ce ticket.'},
            status=status.HTTP_409_CONFLICT))

    return _noindex(Response(
        {'note': satisfaction.note, 'commentaire': satisfaction.commentaire,
         'sous_notes': satisfaction.sous_notes},
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

    # ASAV24 — idempotence : un rejeu identique (même équipement, même
    # description, fenêtre de quelques minutes) renvoie la référence du
    # ticket existant sans créer de ticket ni consommer de numéro.
    import hashlib
    import time

    from core.idempotency import dedupe_event
    empreinte = hashlib.sha256(description.encode('utf-8')).hexdigest()[:16]
    fenetre = int(time.time() // FENETRE_REJEU_SIGNALEMENT_S)
    if not dedupe_event(
            company=equipement.company, source='sav_signalement_qr',
            event_id=f'{equipement.pk}:{empreinte}:{fenetre}'):
        existant = (Ticket.objects
                    .filter(company=equipement.company,
                            equipement=equipement,
                            description__startswith=description)
                    .order_by('-date_creation').first())
        if existant is not None:
            return _noindex(Response(
                {'reference': existant.reference}, status=status.HTTP_200_OK))

    # ASAV28 — la photo est validée (format, taille) et stockée AVANT de
    # créer le ticket : un refus donne 400 sous ``photo``, sans ticket ni
    # numéro consommé (plus de pièce jointe jetée en silence).
    photo = request.FILES.get('photo')
    donnees_photo = None
    if photo is not None:
        from apps.records.storage import store_attachment

        donnees_photo, erreur_photo = store_attachment(photo)
        if donnees_photo is None:
            return _noindex(Response(
                {'photo': [erreur_photo]}, status=status.HTTP_400_BAD_REQUEST))

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
    if donnees_photo is not None:
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment

        Attachment.objects.create(
            company=equipement.company,
            content_type=ContentType.objects.get_for_model(Ticket),
            object_id=ticket.pk, **donnees_photo)

    return _noindex(Response(
        {'reference': ticket.reference}, status=status.HTTP_201_CREATED))


# ── NTSRV2 — Formulaire portail client → ticket SAV (public, tokenisé) ───────

# Noms de composants OpenAPI CONSERVÉS tels quels (snapshot PACT6 stable) :
# la route reste déclarée mais est dépréciée et répond 410.
@extend_schema(request=inline_serializer('PortailTicketRequete', {
    'sujet': drf_serializers.CharField(),
    'description': drf_serializers.CharField(required=False),
    'chantier': drf_serializers.IntegerField(required=False),
}), responses=inline_serializer('PortailCreerTicketReponse', {
    'reference': drf_serializers.CharField(required=False),
    'numero_suivi': drf_serializers.CharField(required=False),
    'suivi_token': drf_serializers.CharField(required=False),
    'detail': drf_serializers.CharField(required=False),
}), deprecated=True)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def portail_creer_ticket(request):
    """ASAV27 — second chemin portail → ticket RETIRÉ (aucun appelant).

    La route reste déclarée (contrat public) mais répond toujours 410, sans
    créer de ticket, sans consommer de numéro, sans stocker de pièce jointe,
    et SANS lire le jeton : un jeton invalide donne exactement la même
    réponse (aucune fuite d'existence). Le seul chemin client est « Mes
    demandes » du portail (priorité triée par le SAV)."""
    return _noindex(Response(
        {'detail': 'Formulaire retiré : utilisez « Mes demandes » de votre '
                   'espace client.'},
        status=status.HTTP_410_GONE))


# ── NTSRV3 — Webhook WhatsApp entrant (GATED, 404 sans clé) ─────────────────

@extend_schema(request=inline_serializer('WhatsappInboundRequete', {
    'entry': drf_serializers.ListField(required=False),
}), responses=inline_serializer('WhatsappInboundReponse', {
    'reference': drf_serializers.CharField(required=False),
    'cree': drf_serializers.BooleanField(required=False),
    'detail': drf_serializers.CharField(required=False),
}))
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def whatsapp_inbound_webhook(request):
    """NTSRV3 — Récepteur des messages WhatsApp Business entrants (canal SAV).

    GATED : sans ``WHATSAPP_BUSINESS_API_KEY`` configurée, l'endpoint répond
    404 — comme s'il n'existait pas — et AUCUN appel sortant n'est jamais
    tenté. Aucun crash au démarrage : la clé est lue à l'appel, jamais à
    l'import.

    ASEC36 — FERMÉ : la signature Meta ``X-Hub-Signature-256`` (HMAC-SHA256
    du corps brut avec ``SAV_WHATSAPP_APP_SECRET``) est EXIGÉE. Secret absent
    → 503 explicite et journalisé (fail-closed) ; signature absente ou
    fausse → 401, rien n'est lu ni écrit. Le tenant est résolu CÔTÉ SERVEUR
    par le NUMÉRO DESTINATAIRE (``value.metadata.phone_number_id``) déclaré
    dans ``SAV_WHATSAPP_NUMEROS`` — jamais « la première société », jamais le
    corps ; un numéro non rattaché reçoit la réponse neutre, sans écriture.
    Toute requête signée acceptée reçoit la MÊME réponse (200 « Reçu. »),
    que l'expéditeur soit un client connu ou non : aucun oracle « numéro
    client ».

    Le message est rattaché au ticket WhatsApp OUVERT du client (matché par
    NUMÉRO via ``crm.selectors.find_client_by_phone``), sinon un ticket est
    ouvert. Un numéro inconnu ne crée jamais de ticket orphelin. Idempotent
    par identifiant de message (``core.idempotency.dedupe_event``) : une
    redélivrance Meta ne duplique rien.

    Ce canal ne remplace PAS le WhatsApp manuel (liens wa.me) utilisé pour
    les devis/factures : il est réservé au SAV.
    """
    import logging

    from core.webhook_signature import signature_hub_sha256_valide

    from .services import (
        extraire_destinataire_whatsapp, extraire_message_whatsapp,
        societe_pour_numero_whatsapp, traiter_message_whatsapp,
        whatsapp_api_key, whatsapp_app_secret,
    )

    logger = logging.getLogger(__name__)

    if not whatsapp_api_key():
        return _not_found()

    secret = whatsapp_app_secret()
    if not secret:
        logger.error(
            'sav.whatsapp_inbound_webhook : SAV_WHATSAPP_APP_SECRET non '
            'configuré — requête REFUSÉE (fail-closed, ASEC36).')
        return _noindex(Response(
            {'detail': 'Canal WhatsApp SAV non configuré '
                       '(SAV_WHATSAPP_APP_SECRET absent).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE))
    # Corps brut lu AVANT ``request.data`` : la signature porte sur lui.
    if not signature_hub_sha256_valide(request, secret):
        logger.warning(
            'sav.whatsapp_inbound_webhook : signature absente ou invalide.')
        return _noindex(Response({'detail': 'Signature invalide.'},
                                 status=status.HTTP_401_UNAUTHORIZED))

    recu = _noindex(Response({'detail': 'Reçu.'}, status=status.HTTP_200_OK))

    message_id, telephone, texte = extraire_message_whatsapp(request.data)
    if not telephone:
        return _noindex(Response(
            {'detail': 'Aucun message exploitable dans la charge utile.'},
            status=status.HTTP_400_BAD_REQUEST))

    company = societe_pour_numero_whatsapp(
        extraire_destinataire_whatsapp(request.data))
    if company is None:
        logger.warning(
            'sav.whatsapp_inbound_webhook : numéro destinataire non rattaché '
            'à une société (SAV_WHATSAPP_NUMEROS) — message ignoré.')
        return recu

    if message_id:
        from core.idempotency import dedupe_event
        if not dedupe_event(company=company, source='sav_whatsapp_inbound',
                            event_id=message_id):
            return recu

    # Numéro expéditeur inconnu : aucun ticket orphelin, même réponse.
    traiter_message_whatsapp(
        company, message_id=message_id, telephone=telephone, texte=texte)
    return recu
