"""Contact, OTP et signature de la proposition publique (SPL253, déplacé de ``public_views.py``).

Demande de rappel, OTP de signature, OTP de lecture (demande + vérification),
acceptation électronique du devis et activation d'une ligne optionnelle. Le
suffixe ``_views.py`` est obligatoire : ces six vues sont AllowAny et doivent
rester vues par les scanners (cliquet de throttle YRBAC9). Les imports
``from ..services import …`` restent TARDIFS (dans les corps) : les patchs de
``apps.ventes.services.<nom>`` continuent d'intercepter. Déplacement pur :
corps octet-identiques (seule la profondeur des imports relatifs locaux
change), prouvé par ``tests/golden/split_pv_signature.json``.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import (
    authentication_classes, api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .noyau import (
    PublicLinkRateThrottle, _client_ip, _noindex, _not_found,
    _parse_client_ts, _refus_apercu_interne, _refus_brouillon,
    _resolve_proposal_link, _texte_du_corps,
)
from .paiement_views import _deposit_success_payload


#: ADEV51 — le refus 409 du contrat ``proposal_accept.json``
#: (``reponses_409.empreinte_perimee``), mot pour mot.
EMPREINTE_PERIMEE = ('La proposition a changé depuis votre lecture : '
                     'rechargez la page avant de signer.')


def empreinte_contenu(devis):
    """ADEV51 (C-ADEV-018) — empreinte du CONTENU signable de ce devis :
    SHA-256 de ``modifiabilite.empreinte_visible`` (lignes, en-tête, note,
    option, conception — relus en base). Une correction SUR PLACE d'un envoyé
    (D-QJR5-1) la change ; rien d'autre ne la change."""
    import hashlib
    import json

    from ..domain.modifiabilite import empreinte_visible
    brut = json.dumps(empreinte_visible(devis), sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode('utf-8')).hexdigest()


def signable_au_jeton(devis):
    """ADEV51 — le devis peut-il être signé au jeton client MAINTENANT ?
    Envoyé, version en vigueur (pas remplacée), offre non expirée (ADEV52).
    Hors de ce cas, aucune empreinte n'est servie ni exigée : les gardes
    d'``accept_devis`` disent elles-mêmes pourquoi (``version_remplacee``,
    ``expiree``, ``statut``…)."""
    from ..domain.modifiabilite import ACCEPTER, geste_cycle_permis
    from ..models import Devis
    from ..utils.expiry import is_expired
    if devis is None or devis.statut != Devis.Statut.ENVOYE:
        return False
    if is_expired(devis):
        return False
    permis, _message = geste_cycle_permis(devis, ACCEPTER)
    return permis


def _refus_empreinte(request, devis):
    """ADEV51 — 409 ``empreinte_perimee`` quand le client signe un contenu
    autre que celui qu'il a lu (empreinte absente ou différente de
    l'empreinte courante) ; ``None`` sinon. Rien n'est écrit."""
    if not signable_au_jeton(devis):
        return None
    recue = request.data.get('empreinte_contenu')
    if isinstance(recue, str) and recue.strip() == empreinte_contenu(devis):
        return None
    return _noindex(Response(
        {'detail': EMPREINTE_PERIMEE, 'code': 'empreinte_perimee'},
        status=status.HTTP_409_CONFLICT))


def _refus_aucun_canal(err):
    """ADEV20 (C-ADEV-021) — « Code envoyé. » seulement si un code est
    réellement parti : quand le service rend ``OTP_AUCUN_CANAL``, 409
    ``{detail, code: "aucun_canal"}`` (contrat ``proposal_accept.json``, bloc
    ``otp``) ; ``None`` sinon."""
    from ..domain.cycle_vie import OTP_AUCUN_CANAL
    if err != OTP_AUCUN_CANAL:
        return None
    return _noindex(Response(
        {'detail': OTP_AUCUN_CANAL, 'code': 'aucun_canal'},
        status=status.HTTP_409_CONFLICT))


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_contact_request(request, token):
    """QJ27/QW5 — Le client demande à être contacté (« Être rappelé » côté
    client, ou une question/révision structurée avant signature).

    Endpoint PUBLIC tokenisé (même jeton ShareLink que la proposition — long,
    imprévisible, expirant). Consigne la demande dans le chatter du lead lié
    (via les services crm — jamais d'import de ``crm.models``) et notifie le
    RESPONSABLE du lead ET son SUPÉRIEUR (repli : managers « Commercial
    responsable » / « Directeur » de la société) via ``notify()``. Sans lead,
    le créateur du devis + son supérieur sont notifiés et la demande est
    consignée dans le chatter du devis.

    QW5 — le site poste ``channel`` (pas ``canal`` — ``proposition.ts``/
    ``proposition-contact.ts``, vocabulaire ``rappel``/``whatsapp``/
    ``question``/``voice``/``revision``) : lu ici en ALIAS de ``canal``
    (rétro-compat : ``canal`` reste accepté). ``revision_kind`` (WJ54,
    ``kwc``/``batterie``/``autre``) est relayé au service crm. Le message est
    tronqué à 2000 caractères — ALIGNÉ sur la troncature côté site
    (``buildContactBody`` — ``proposition.ts``), plus que les 500 d'avant qui
    coupaient silencieusement un message légitime.

    Idempotent / rate-sane : en plus du throttle par IP+jeton, une même
    demande n'est transmise qu'une fois par heure PAR LIEN **ET PAR CANAL**
    (QW5 — avant, une "question" transmise verrouillait tout le lien pendant
    1 h, empêchant un "rappel" distinct posé juste après d'être transmis) —
    un double clic sur le MÊME canal répond « déjà transmise » sans
    re-notifier ; un canal différent passe toujours.
    """
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # R4 — l'aperçu interne ne demande pas de rappel au nom du client (chatter
    # du lead + notification du responsable ET de son supérieur).
    if link.via_interne:
        return _refus_apercu_interne()
    # ADEV11 — un brouillon (jamais envoyé) n'engage rien au jeton client.
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus

    canal = (str(
        request.data.get('channel') or request.data.get('canal') or ''
    )).strip()[:20]
    message = (str(request.data.get('message') or '')).strip()[:2000]
    revision_kind = (str(request.data.get('revision_kind') or '')).strip()[:20]

    # Verrou idempotence (1 h par lien ET PAR CANAL) — cache.add est
    # atomique : False si CETTE combinaison lien+canal a déjà été transmise
    # récemment. Scopé par canal (QW5) pour qu'un canal distinct (ex. un
    # "rappel" après une "question") ne soit jamais bloqué par l'autre.
    already = False
    try:
        from django.core.cache import cache
        cache_key = f'qj27-contact:{link.pk}:{canal or "default"}'
        already = not cache.add(cache_key, True, 3600)
    except Exception:  # noqa: BLE001 — un cache indisponible ne bloque rien
        already = False
    if already:
        return _noindex(Response({
            'detail': ('Votre demande a déjà été transmise. '
                       'Nous vous recontactons très vite.'),
            'already_sent': True,
        }))

    devis = link.devis
    try:
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            from apps.crm.services import notify_client_contact_request
            notify_client_contact_request(
                devis.reference, lead, canal=canal, message=message,
                revision_kind=revision_kind)
        else:
            # Pas de lead : chatter devis + notification créateur + supérieur.
            from apps.crm.services import user_and_superior_recipients
            from apps.notifications.services import notify_many
            from .. import activity
            note = f'Le client demande à être contacté ({devis.reference})'
            if message:
                note += f' : « {message} »'
            activity.log_devis_note(devis, None, note)
            recipients = user_and_superior_recipients(
                getattr(devis, 'created_by', None), devis.company)
            if recipients:
                client_nom = str(devis.client) if devis.client_id else 'Le client'
                body = (f'{client_nom} demande à être contacté au sujet du '
                        f'devis {devis.reference}.')
                if message:
                    body += f'\nMessage : « {message} »'
                notify_many(
                    recipients, 'client_contact_request',
                    f'Le client demande à être contacté — {devis.reference}',
                    body=body,
                    link='/ventes/devis',
                    company=devis.company,
                )
    except Exception:  # noqa: BLE001 — jamais d'erreur interne exposée
        pass

    return _noindex(Response({
        'detail': ('Votre demande a bien été transmise. '
                   'Nous vous recontactons très vite.'),
        'already_sent': False,
    }))


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_request_otp(request, token):
    """QJ11 — Demande l'envoi d'un OTP au contact du devis (toggle ESIGN_OTP_ENABLED).

    No-op quand le toggle est OFF (retourne succès immédiatement — comportement
    byte-identique à aujourd'hui). Quand ON : génère un code, l'envoie via
    WhatsApp (wa.me draft) ou email et le stocke en cache (10 min)."""
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # R4 — un aperçu interne ne fait PAS partir un code de signature sur le
    # téléphone (ou dans la boîte mail) du client.
    if link.via_interne:
        return _refus_apercu_interne()
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus
    from ..services import request_esign_otp
    err = request_esign_otp(link)
    refus = _refus_aucun_canal(err)
    if refus is not None:
        return refus
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code envoyé.'}))


# L-NIV — formes déclarées des deux vues otp-lecture (le compteur R2 de
# check_openapi_shapes est un plafond gelé : toute vue publique nouvelle
# DOIT déclarer sa forme au lieu de laisser le générateur deviner).
_OTP_LECTURE_DETAIL_RESPONSE = inline_serializer('PublicOtpLectureDetail', {
    'detail': drf_serializers.CharField(),
})


_OTP_LECTURE_VERIFY_REQUEST = inline_serializer('PublicOtpLectureVerifyRequest', {
    'otp_code': drf_serializers.CharField(),
})


@extend_schema(request=None, responses={200: _OTP_LECTURE_DETAIL_RESPONSE})
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_request_otp_lecture(request, token):
    """L-NIV (24/08/2026) — Demande l'envoi d'un OTP de LECTURE.

    Distinct de ``proposal_request_otp`` (QJ11, OTP de SIGNATURE, gouverné par
    le toggle société ``ESIGN_OTP_ENABLED``) : ici le gate est
    ``link.otp_lecture``, un réglage PAR LIEN posé par le commercial — actif
    dès que ce booléen est vrai, sans dépendre d'aucun toggle. Un lien dont
    ``otp_lecture`` est False renvoie 200 immédiatement (rien à demander,
    comportement inchangé — la lecture n'est de toute façon pas gatée)."""
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # R4 — même règle que l'OTP de signature : aucun code ne part vers le
    # client depuis un aperçu. Rien n'est perdu — le jeton interne DISPENSE
    # déjà de l'OTP de lecture (voir ``proposal_data``).
    if link.via_interne:
        return _refus_apercu_interne()
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus
    if not link.otp_lecture:
        return _noindex(Response({'detail': 'Aucun code requis pour ce lien.'}))
    from ..services import request_otp_lecture
    err = request_otp_lecture(link)
    refus = _refus_aucun_canal(err)
    if refus is not None:
        return refus
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code envoyé.'}))


@extend_schema(request=_OTP_LECTURE_VERIFY_REQUEST, responses={200: _OTP_LECTURE_DETAIL_RESPONSE})
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_verify_otp_lecture(request, token):
    """L-NIV (24/08/2026) — Vérifie l'OTP de LECTURE soumis.

    Succès → la LECTURE de ce lien reste déverrouillée pendant
    ``OTP_LECTURE_VERIFIED_TTL`` (1 h) : ``proposal_data``/``proposal_pdf``
    relisent ce drapeau à chaque appel plutôt que d'exiger un code par GET
    (contrairement à l'acceptation, la lecture est consultée plusieurs
    fois)."""
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # R4 — vérifier un code depuis l'aperçu DÉVERROUILLERAIT la lecture du
    # lien PUBLIC pendant une heure (état client), avec un code envoyé au
    # client. L'aperçu n'en a aucun besoin : il lit sans OTP.
    if link.via_interne:
        return _refus_apercu_interne()
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus
    if not link.otp_lecture:
        return _noindex(Response({'detail': 'Aucun code requis pour ce lien.'}))
    from ..services import validate_otp_lecture
    # QJR413 (b) — garde de type sur le corps public (voir _texte_du_corps).
    otp_code, refus = _texte_du_corps(request, 'otp_code')
    if refus is not None:
        return refus
    err = validate_otp_lecture(link, otp_code)
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code vérifié.'}))


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_accept(request, token):
    """Q7 — e-signature : le client accepte la proposition via le jeton.

    Enregistre nom saisi + horodatage + IP dans le tampon d'acceptation
    existant (``accepte_par_nom``/``date_acceptation``) et bascule le devis en
    « accepté » À TRAVERS le service d'acceptation unique — la chaîne
    bon-commande/facture est donc préservée 1:1 (règle #4). Idempotent : un
    double envoi ne re-signe pas. Pas de login : le jeton authentifie."""
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # L-INTPREV (25/08/2026) — le jeton interne ne peut JAMAIS signer : un
    # aperçu commercial ne peut pas engager le client. Même 404 générique que
    # tout autre refus de ce endpoint (jamais un message qui distinguerait le
    # jeton interne d'un jeton simplement invalide).
    if link.via_interne:
        return _not_found()
    # ADEV11 — un brouillon (jamais envoyé) ne se signe pas au jeton client :
    # 409 ``brouillon`` du contrat ``proposal_accept.json``, rien n'est écrit.
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus
    # ── QJR132 / ES1 (audit du 30/08/2026) — SIGNER EST AU MOINS AUSSI GARDÉ
    #    QUE LIRE. Ce endpoint n'appelait JAMAIS ``otp_lecture_verified``,
    #    contrairement aux TROIS routes de LECTURE de la même proposition
    #    (``proposal_data``, la page et ``proposal_pdf``). Sur un lien où le
    #    commercial a activé l'OTP de lecture, quiconque détenait le jeton
    #    pouvait donc ENGAGER le client sans jamais fournir de code : le geste
    #    le plus lourd du parcours était le moins gardé.
    #
    #    INDÉPENDANT DU TOGGLE DE SIGNATURE. L'OTP de SIGNATURE
    #    (``validate_esign_otp``, plus bas) est gouverné par
    #    ``ESIGN_OTP_ENABLED``, dont l'audit a vérifié qu'il n'apparaît dans
    #    AUCUN ``.env.example``, settings ou ``docker-compose`` — il vaut donc
    #    '0' en production et ce contrôle-là est un no-op. La garde ci-dessous
    #    ne dépend d'aucun réglage : elle suit ce que LE LIEN porte
    #    (``ShareLink.otp_lecture``), exactement comme les trois lectures.
    #
    #    NO-OP SUR UN LIEN SANS OTP DE LECTURE : ``otp_lecture_verified``
    #    répond True quand ``link.otp_lecture`` est faux — aucun lien
    #    d'aujourd'hui ne change de comportement. Le jeton interne, lui, est
    #    déjà refusé au-dessus (il ne signe jamais).
    #
    #    Posée AVANT toute lecture du corps et tout effet de bord, et sur le
    #    MÊME contrat que les lectures (403 ``otp_required``) pour que l'écran
    #    client sache redemander le code au lieu d'afficher une erreur nue.
    from ..services import otp_lecture_verified
    if not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))
    devis = link.devis
    # QJR413 (b) — garde de type sur le corps public (voir _texte_du_corps).
    nom, refus = _texte_du_corps(request, 'nom', 'name')
    if refus is not None:
        return refus
    if not nom:
        return _noindex(Response(
            {'detail': 'Votre nom est requis pour signer la proposition.'},
            status=status.HTTP_400_BAD_REQUEST))
    option, refus = _texte_du_corps(request, 'option')
    if refus is not None:
        return refus
    # QX9 — consentement explicite requis (loi 43-20). Le front envoie
    # ``consent_esign`` (booléen) ; on accepte aussi l'ancien ``consentement``
    # en repli. Le consentement ne défaute PLUS silencieusement à True : une
    # acceptation sans consentement explicite est refusée (400).
    consent_raw = request.data.get('consent_esign')
    if consent_raw is None:
        consent_raw = request.data.get('consentement')
    consentement = consent_raw in (True, 'true', 'True', '1', 1, 'on')
    if not consentement:
        return _noindex(Response(
            {'detail': 'Votre consentement explicite à la signature '
                       'électronique est requis pour accepter la '
                       'proposition.'},
            status=status.HTTP_400_BAD_REQUEST))
    # QX9 — preuve de signature réelle envoyée par le front.
    signature_image = (request.data.get('signature_data_url') or '')
    signed_at_client = _parse_client_ts(
        request.data.get('signed_at_client'))
    # QJR413 (b) — gardes de type sur le corps public (voir _texte_du_corps).
    on_behalf_of, refus = _texte_du_corps(request, 'on_behalf_of')
    if refus is not None:
        return refus
    on_behalf_of = on_behalf_of[:150]
    # CIQ319 (D-CIQ-11) — devis commercial / industriel : raison sociale,
    # qualité du signataire et ICE OBLIGATOIRES en ligne (400 qui nomme le
    # champ) ; ignorés pour tout autre segment.
    from ..domain.cycle_vie import (
        EntrepriseInvalide, lire_entreprise_acceptation,
        signature_entreprise,
    )
    try:
        entreprise = lire_entreprise_acceptation(
            devis, request.data.get('entreprise'), obligatoire=True)
    except EntrepriseInvalide as exc:
        return _noindex(Response(
            {'detail': exc.detail, 'champ': exc.champ},
            status=status.HTTP_400_BAD_REQUEST))
    # QJ11 — code OTP si le toggle est actif (service gère la validation).
    otp_code, refus = _texte_du_corps(request, 'otp_code')
    if refus is not None:
        return refus
    from ..services import accept_devis, AcceptError, validate_esign_otp
    # QJ11 — validation OTP avant l'acceptation (no-op quand toggle OFF).
    otp_err = validate_esign_otp(link=link, otp_code=otp_code)
    if otp_err:
        return _noindex(Response(
            {'detail': otp_err},
            status=status.HTTP_400_BAD_REQUEST))
    # ADEV51 (C-ADEV-018) — ce que le client signe = ce qu'il a lu : le corps
    # renvoie l'``empreinte_contenu`` servie à la lecture ; un devis corrigé
    # depuis (ou une empreinte absente) ⇒ 409 ``empreinte_perimee``.
    refus = _refus_empreinte(request, devis)
    if refus is not None:
        return refus
    try:
        # ── QJR135 / ES4 — L'ÉCRAN DE CONFIRMATION LIT CE QUI VIENT D'ÊTRE
        #    ÉCRIT. ``accept_devis`` REBIND son nom local sur la relecture
        #    VERROUILLÉE ; l'objet de CETTE fonction restait celui d'AVANT.
        #    La réponse sérialisait donc une instance périmée :
        #    ``option_acceptee`` y valait '', donc ``option_effective``
        #    retombait sur AVEC_BATTERIE (``utils/options``) et un client qui
        #    venait de signer « sans batterie » voyait l'acompte de l'option
        #    AVEC — plus élevé — pendant que l'email, qui reçoit l'instance
        #    FRAÎCHE, annonçait le bon montant. ``statut`` renvoyé valait
        #    « envoye » et ``accepte_par_nom`` '' juste après une signature
        #    réussie. On reprend donc la VALEUR DE RETOUR du service.
        devis = accept_devis(
            devis=devis, user=None, nom=nom, option=option,
            ip=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
            consentement=consentement,
            signature_image=signature_image,
            signed_at_client=signed_at_client,
            on_behalf_of=on_behalf_of,
            entreprise=entreprise,
        )
    except AcceptError as exc:
        corps = {'detail': exc.message}
        # ADEV11 — un refus qui porte un code du contrat (``codes_409`` de
        # ``proposal_accept.json``) le renvoie ; les autres restent inchangés.
        if exc.code:
            corps['code'] = exc.code
        return _noindex(Response(
            corps,
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    # QX33be — état de succès post-signature : acompte (tranche 1 sur le TTC
    # REMISÉ per QX1) + instructions de virement (RIB) + slot lien carte si un
    # PSP est configuré. Aucun changement de comportement si rien n'est
    # configuré (RIB vide, pas de PSP) — l'objet ``paiement`` est alors minimal.
    return _noindex(Response({
        'detail': 'Proposition acceptée. Merci !',
        'reference': devis.reference,
        'statut': devis.statut,
        'accepte_par_nom': devis.accepte_par_nom,
        'paiement': _deposit_success_payload(devis, token),
        # CIQ319 — l'identité d'entreprise RELUE sur la signature enregistrée
        # (la première fait foi), même forme que le corps ; null hors C&I.
        'entreprise': _entreprise_relue(signature_entreprise(devis)),
    }))


def _entreprise_relue(bloc):
    if not bloc:
        return None
    return {'raison_sociale': bloc.get('raison_sociale') or '',
            'signataire_qualite': bloc.get('signataire_qualite') or '',
            'ice': bloc.get('ice') or ''}


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_activate_option(request, token):
    """XSAL5 — le client active une LIGNE OPTIONNELLE de sa proposition.

    Endpoint PUBLIC tokenisé (même jeton ShareLink que la proposition — long,
    imprévisible, expirant ; il BORNE le devis à une seule société, donc
    company-scopé par construction). Corps : ``{"ligne_id": <int>}``. Bascule la
    ligne d'``optionnelle`` à effective (elle entre dans les totaux/documents
    avals) via le service unique ``activate_optional_line`` — idempotent, ne
    crée/duplique jamais de ligne. Ne touche AUCUN statut de devis (règle #4) :
    seule l'acceptation (``proposal_accept``) fige le document. Jeton
    invalide/expiré → 404 amical ; devis figé → 409."""
    link = _resolve_proposal_link(token, refuser_brouillon=False)
    if link is None:
        return _not_found()
    # R4 — activer une option CHANGE le périmètre facturé du devis : c'est une
    # décision du client, jamais un geste d'aperçu.
    if link.via_interne:
        return _refus_apercu_interne()
    refus = _refus_brouillon(link)
    if refus is not None:
        return refus
    # ── QJR418 (DR2, actions) — SIGNER EST AU MOINS AUSSI GARDÉ QUE LIRE, ET
    # ACTIVER UNE OPTION PAYANTE AUSSI. Ce endpoint ne consultait JAMAIS
    # ``otp_lecture_verified`` : quiconque détenait le jeton pouvait CHANGER LE
    # PÉRIMÈTRE FACTURÉ d'un devis sans franchir la garde que la lecture, elle,
    # exige (QJR132/QJR417). Le raisonnement de QJR132 ne leur avait jamais été
    # appliqué. DR2 tranche : la garde couvre les actions clientes,
    # ``activate_option`` étant le minimum absolu.
    # C'est LA garde de QJR417, jamais une seconde formulation, posée AVANT
    # toute mutation (et même avant la lecture du corps). NO-OP sur un lien
    # sans OTP de lecture : la garde répond True — aucun lien d'aujourd'hui ne
    # change. Même contrat de refus que les lectures (403 ``otp_required``)
    # pour que l'écran client sache redemander le code.
    from ..services import otp_lecture_verified
    if not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))
    try:
        ligne_id = int(request.data.get('ligne_id'))
    except (TypeError, ValueError):
        return _noindex(Response(
            {'detail': 'Option invalide.'},
            status=status.HTTP_400_BAD_REQUEST))
    from ..services import activate_optional_line, AcceptError
    try:
        ligne = activate_optional_line(
            devis=link.devis, ligne_id=ligne_id, user=None)
    except AcceptError as exc:
        return _noindex(Response(
            {'detail': exc.message},
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    if ligne is None:
        return _not_found()
    return _noindex(Response({
        'detail': 'Option activée. Elle est désormais incluse dans votre total.',
        'ligne_id': ligne.id,
        'designation': ligne.designation,
    }))
