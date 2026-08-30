"""Cycle de vie du devis — envoi, signature, acceptation, renouvellement.

Ce que le devis TRAVERSE entre sa composition et sa suite : l'envoi
(`mark_devis_sent`), l'OTP d'e-signature et l'OTP de LECTURE (demande,
validation, envois wa.me/e-mail), l'acceptation (`accept_devis`, dépôt,
e-mails, notification vendeur), l'attribution marketing et la Conversions
API Meta, les liens de partage (proposition, bon de commande,
installation), les clauses figées, le cliché de configuration et son diff,
l'activation d'une ligne optionnelle et le renouvellement.

AVERTISSEMENT DE LECTURE (R4-B1). Les corps e-signature / OTP /
`accept_devis` et la synchronisation Meta n'ont JAMAIS été audités : ce
module les DÉPLACE sans les avoir lus, à l'octet près. Leur audit est une
tâche à part (QJR79) — ne pas prendre ce déplacement pour une revue.

QJR70 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.

CIBLE DE ``mock.patch`` — LA RÈGLE, POUR TOUTE LA VAGUE M3. Un patch sur
l'attribut d'un module ne change QUE les lectures qui passent par CE module.
Le ré-export de ``services.py`` est une AFFECTATION, donc un cliché : il ne
suit pas un patch posé ici, et réciproquement. D'où la règle :

* un nom appelé depuis l'INTÉRIEUR de ce module se patche ICI
  (``apps.ventes.domain.cycle_vie.X``) — c'est le cas de ``_store_signed_pdf``,
  ``_send_acceptance_emails``, ``_notify_seller_accepted``, ``_send_otp_email``
  et ``_send_otp_whatsapp``, tous appelés par ``accept_devis`` /
  ``request_esign_otp`` ;
* un nom appelé seulement de l'EXTÉRIEUR, par un appelant qui l'importe depuis
  la façade au moment de l'appel (import fonction-local), continue de se patcher
  sur ``apps.ventes.services.X`` — inchangé.
"""
import logging
import os

logger = logging.getLogger("apps.ventes.services")


class AcceptError(Exception):
    """Raised when a devis cannot be accepted (wrong status / bad option)."""

    def __init__(self, message, conflict=False):
        super().__init__(message)
        self.message = message
        self.conflict = conflict  # True → 409, False → 400


def activate_optional_line(*, devis, ligne_id, user=None):
    """XSAL5 — active une ligne OPTIONNELLE d'un devis (self-service client sur
    la proposition, ou vendeur en interne).

    Bascule ``optionnelle=False`` sur la ligne existante : elle devient une
    ligne normale et entre alors dans les totaux (HT/TVA/TTC) et les documents
    avals. Ne CRÉE ni ne DUPLIQUE jamais de ligne. Company-scopé : la ligne doit
    appartenir au ``devis`` fourni (déjà borné à sa société par l'appelant / le
    jeton public). Idempotent : ré-activer une ligne déjà active est un no-op
    silencieux (aucun second chatter). Verrou anti-course (select_for_update).

    Seul un devis encore vivant (brouillon / envoyé) peut voir ses options
    activées — après acceptation, le contenu est figé (règle #4, chaîne de
    statuts préservée). Consigne le chatter du devis.

    Renvoie la ``LigneDevis`` mise à jour, ou lève ``AcceptError`` (statut
    figé) / renvoie None si la ligne est introuvable ou n'est pas optionnelle.
    """
    from django.db import transaction
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes import activity

    with transaction.atomic():
        try:
            ligne = (LigneDevis.objects
                     .select_for_update()
                     .select_related('devis')
                     .get(pk=ligne_id, devis=devis))
        except LigneDevis.DoesNotExist:
            return None

        # Devis figé (accepté/refusé/expiré) : les options ne sont plus
        # activables (le contenu est verrouillé — règle #4).
        if ligne.devis.statut not in (
                Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            raise AcceptError(
                'Ce devis est figé — ses options ne sont plus modifiables.',
                conflict=True)

        # Idempotent : ligne non optionnelle (jamais optionnelle, ou déjà
        # activée) → no-op silencieux, aucun second chatter.
        if not ligne.optionnelle:
            return ligne

        ligne.optionnelle = False
        ligne.save(update_fields=['optionnelle'])

    # Chatter (hors transaction — miroir de accept_devis).
    try:
        activity.log_devis_note(
            devis, user,
            f'Option activée par le client : « {ligne.designation} » '
            '— désormais incluse dans le total.')
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass
    return ligne


# ── QJ11 — OTP e-signature (toggle) ─────────────────────────────────────────
# Activé par la variable d'environnement ESIGN_OTP_ENABLED=1.
# Quand OFF (défaut) : comportement byte-identique à avant QJ11 — aucun OTP,
# aucun appel supplémentaire. Quand ON : le client reçoit un code à 6 chiffres
# (SMS wa.me / email) et doit le soumettre avant que l'acceptation soit acceptée.
# Le code est stocké dans le cache Django (TTL 10 min), jamais en base. Simple +
# sécurisé : pas de table supplémentaire, idempotent (re-demander régénère).

OTP_CACHE_TTL = 600  # 10 minutes


def _esign_otp_enabled():
    """True si ESIGN_OTP_ENABLED=1 dans l'environnement."""
    return os.getenv('ESIGN_OTP_ENABLED', '0').strip() == '1'


def _otp_cache_key(link_token):
    """Clé de cache pour l'OTP d'un lien de proposition."""
    return f'esign_otp:{link_token}'


def _generate_otp():
    """Génère un code OTP à 6 chiffres sécurisé (secrets.randbelow)."""
    import secrets as _secrets
    return f'{_secrets.randbelow(1000000):06d}'


# ── QJR147 / ES5 — PLAFOND CUMULATIF SUR LES DEMANDES D'OTP PUBLIQUES ───────
#
# CE QUI ÉTAIT FAUX. Les deux endpoints de DEMANDE sont ``AllowAny`` et leur
# seul frein était ``PublicLinkRateThrottle`` (30/minute par IP + jeton) : ni
# plafond journalier, ni plafond PAR JETON toutes IP confondues. Et chaque
# demande RÉINITIALISAIT le compteur d'échecs — le verrouillage à cinq
# tentatives n'était donc qu'un ralentisseur : cinq essais, on redemande un
# code, cinq essais de plus, indéfiniment.
#
# LE DOMMAGE LE PLUS DÉMONTRABLE N'EST PAS LE BRUTE-FORCE : chaque demande
# envoie un VRAI email au contact du devis. Un porteur de jeton pouvait donc
# bombarder le client de son propre fournisseur.
#
# DEUX GESTES, ET LEUR RAISON :
#   1. un compteur de DEMANDES par jeton, JOURNALIER, qui n'est JAMAIS remis à
#      zéro par une nouvelle demande (c'est tout l'intérêt) ;
#   2. le compteur d'ÉCHECS n'est plus effacé à la régénération — il expire de
#      lui-même avec la fenêtre du code (10 min), ce qui donne un verrouillage
#      TEMPOREL au lieu d'un verrou qu'un simple clic annule.
#
# ÉCHEC FERMÉ en cas de panne cache, comme tous les chemins OTP de ce module :
# sans compteur lisible, on refuse d'envoyer plutôt que d'ouvrir un robinet.

#: Nombre de DEMANDES de code tolérées par jeton et par jour, toutes IP
#: confondues. Large pour un client qui ne reçoit pas son mail du premier coup,
#: étroit pour qui voudrait s'en servir comme d'un canon à emails.
OTP_DEMANDES_MAX_PAR_JOUR = 10
#: TTL du compteur de demandes : 24 h glissantes à partir de la première.
OTP_DEMANDES_TTL = 86400


def _otp_demandes_key(prefixe, link_token, *, jour=None):
    """Clé du compteur de DEMANDES — DATÉE, donc le plafond est journalier et
    le compteur se périme tout seul (aucune purge à écrire)."""
    from django.utils import timezone
    jour = jour or timezone.now().strftime('%Y%m%d')
    return f'{prefixe}_demandes:{jour}:{link_token}'


#: Le message FR servi quand le plafond journalier est atteint. Il nomme le
#: geste qui débloque (attendre, ou passer par le conseiller) plutôt que de
#: laisser le client devant une erreur muette.
OTP_PLAFOND_MESSAGE = (
    "Trop de demandes de code pour ce lien aujourd'hui. Réessayez demain, ou "
    "contactez votre conseiller pour recevoir votre code autrement.")


def _plafond_demandes_otp_atteint(prefixe, link_token):
    """QJR147 — compte CETTE demande et dit si le plafond est dépassé.

    Le compteur est incrémenté À CHAQUE APPEL et n'est remis à zéro par
    AUCUNE demande : c'est précisément ce que le compteur d'échecs ne faisait
    pas. Rend ``True`` quand il faut refuser.
    """
    from django.core.cache import cache
    cle = _otp_demandes_key(prefixe, link_token)
    try:
        # ``add`` ne pose la valeur que si la clé n'existe pas : la fenêtre de
        # 24 h part de la PREMIÈRE demande et n'est pas repoussée par les
        # suivantes (un TTL repoussé serait un plafond qui ne finit jamais).
        cache.add(cle, 0, timeout=OTP_DEMANDES_TTL)
        compte = cache.incr(cle)
    except Exception:  # noqa: BLE001 — cache absent/illisible ⇒ échec FERMÉ
        logger.warning(
            'QJR147: compteur de demandes OTP illisible (%s) — demande '
            'refusée par précaution.', cle, exc_info=True)
        return True
    return compte > OTP_DEMANDES_MAX_PAR_JOUR


def request_esign_otp(link):
    """QJ11 — Génère et envoie un OTP au contact du devis (wa.me ou email).

    Idempotent : un appel sur un lien dont l'OTP est déjà en cache régénère
    simplement le code (nouvelle fenêtre de 10 min). Retourne None (succès)
    ou un message d'erreur FR lisible.

    Sans toggle ON : retourne None immédiatement (no-op, comportement inchangé).
    """
    if not _esign_otp_enabled():
        return None

    # QJR147 — plafond JOURNALIER par jeton, compté AVANT toute génération et
    # tout envoi : c'est l'email au client qu'il s'agit de plafonner.
    if _plafond_demandes_otp_atteint('esign_otp', link.token):
        return OTP_PLAFOND_MESSAGE

    from django.core.cache import cache
    code = _generate_otp()
    cache_key = _otp_cache_key(link.token)
    cache.set(cache_key, code, timeout=OTP_CACHE_TTL)
    # QJR147 — le compteur d'ÉCHECS N'EST PLUS EFFACÉ ICI. Le remettre à zéro
    # à chaque nouveau code faisait du verrouillage à cinq tentatives un simple
    # ralentisseur (cinq essais, on redemande, cinq essais de plus…). Il expire
    # désormais tout seul avec la fenêtre du code : un verrou TEMPOREL, qu'un
    # clic n'annule pas.

    devis = link.devis
    client = getattr(devis, 'client', None)
    phone = (getattr(client, 'telephone', '') or '').strip()
    email = (getattr(client, 'email', '') or '').strip()

    sent = False
    # Préférer WhatsApp / SMS (wa.me), puis email. QX10 — le repli email est
    # TOUJOURS tenté quand WhatsApp échoue, même si le client n'a pas d'email
    # renseigné : sinon un client téléphone-seul (stub WhatsApp figé à False)
    # ne recevrait JAMAIS son code, verrouillé hors de la signature. Un email
    # vide/absent échoue simplement (best-effort, cf. _send_otp_email).
    if phone:
        sent = _send_otp_whatsapp(phone=phone, code=code, devis_ref=devis.reference)
    if not sent:
        sent = _send_otp_email(email=email, code=code, devis_ref=devis.reference,
                               company=devis.company)

    if not sent:
        logger.warning(
            'QJ11: OTP généré pour %s mais aucun canal disponible (phone=%s, email=%s)',
            devis.reference, bool(phone), bool(email))
    else:
        logger.info('QJ11: OTP envoyé pour devis %s', devis.reference)
    return None


#: QX10 — nombre de tentatives OTP erronées avant verrouillage temporaire.
OTP_MAX_ATTEMPTS = 5


def _otp_attempts_key(link_token):
    """QX10 — clé de cache du compteur de tentatives OTP erronées par jeton."""
    return f'esign_otp_attempts:{link_token}'


def validate_esign_otp(link, otp_code):
    """QJ11 — Valide l'OTP soumis contre le cache.

    Sans toggle ON : retourne None (pas d'erreur, comportement inchangé).
    Avec toggle ON :
      - otp_code absent / vide → message d'erreur (OTP requis)
      - otp_code incorrect ou expiré → message d'erreur
      - otp_code correct → None (la validation réussit), le code est consommé.

    QX10 — protection brute-force : un compteur par jeton (cache) verrouille
    la validation après ``OTP_MAX_ATTEMPTS`` échecs (l'espace 6 chiffres est
    trivial à balayer sans limite). Une validation réussie remet le compteur
    à zéro.

    QJR147 — LE VERROU EST TEMPOREL, PAS ANNULABLE D'UN CLIC. Redemander un
    code n'efface PLUS le compteur d'échecs (c'est ce qui faisait du
    verrouillage un simple ralentisseur) : il expire de lui-même avec la
    fenêtre du code.
    """
    if not _esign_otp_enabled():
        return None

    if not otp_code:
        return 'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».'

    from django.core.cache import cache
    attempts_key = _otp_attempts_key(link.token)
    attempts = cache.get(attempts_key, 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        # QJR147 — le message ne promet PLUS qu'un nouveau code débloque :
        # le compteur d'échecs n'est plus effacé à la régénération. Le
        # verrou est TEMPOREL (il expire avec la fenêtre du code).
        return ('Trop de tentatives incorrectes. Ce lien est « gelé » '
                'quelques minutes ; patientez, puis redemandez un code.')

    cache_key = _otp_cache_key(link.token)
    stored = cache.get(cache_key)
    if stored is None:
        return 'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.'
    if stored != otp_code.strip():
        # QX10 — incrémente le compteur d'échecs (TTL = fenêtre du code).
        cache.set(attempts_key, attempts + 1, timeout=OTP_CACHE_TTL)
        restantes = max(0, OTP_MAX_ATTEMPTS - (attempts + 1))
        if restantes == 0:
            return ('Trop de tentatives incorrectes. Ce lien est '
                    '« gelé » quelques minutes ; patientez, puis '
                    'redemandez un code.')
        return 'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.'

    # Code valide : on le consomme (one-time use) et on réinitialise le compteur.
    cache.delete(cache_key)
    cache.delete(attempts_key)
    return None


# ── L-NIV (24/08/2026) — OTP de LECTURE, par lien (``ShareLink.otp_lecture``)
# ─────────────────────────────────────────────────────────────────────────
# Distinct de l'OTP de SIGNATURE ci-dessus (QJ11/QX10, gouverné par le toggle
# ``ESIGN_OTP_ENABLED``) : ``otp_lecture`` est un réglage PAR LIEN, posé par le
# commercial (action share-link), jamais un toggle société — donc actif dès
# que ``link.otp_lecture`` vaut True, SANS dépendre d'``ESIGN_OTP_ENABLED``.
# Réutilise EXACTEMENT la même mécanique (code à 6 chiffres, cache Django TTL
# 10 min, compteur anti-brute-force) sous un espace de clés SÉPARÉ — jamais
# de collision avec l'OTP de signature d'un même lien, et la « vérification »
# de lecture pose en plus un DRAPEAU vérifié (TTL 1 h) que ``proposal_data``
# relit à chaque GET, puisque la lecture n'est pas un formulaire ponctuel
# (POST) comme l'acceptation — c'est une page consultée plusieurs fois.
OTP_LECTURE_VERIFIED_TTL = 3600  # 1 heure


def _otp_lecture_cache_key(link_token):
    return f'otp_lecture:{link_token}'


def _otp_lecture_attempts_key(link_token):
    return f'otp_lecture_attempts:{link_token}'


def _otp_lecture_verified_key(link_token):
    return f'otp_lecture_verified:{link_token}'


def request_otp_lecture(link):
    """L-NIV — génère et envoie un OTP de LECTURE au contact du devis.

    Toujours actif (pas de toggle société) : l'appelant (vue publique)
    n'appelle cette fonction QUE quand ``link.otp_lecture`` est True. Retourne
    None (succès) ou un message d'erreur FR lisible — même contrat que
    ``request_esign_otp``."""
    # QJR147 — même plafond journalier par jeton que l'OTP de signature, et
    # pour la même raison : chaque demande envoie un VRAI email au client.
    if _plafond_demandes_otp_atteint('otp_lecture', link.token):
        return OTP_PLAFOND_MESSAGE

    from django.core.cache import cache
    code = _generate_otp()
    cache.set(_otp_lecture_cache_key(link.token), code, timeout=OTP_CACHE_TTL)
    # QJR147 — le compteur d'ÉCHECS n'est plus effacé à la régénération (voir
    # ``request_esign_otp``).

    devis = link.devis
    client = getattr(devis, 'client', None)
    phone = (getattr(client, 'telephone', '') or '').strip()
    email = (getattr(client, 'email', '') or '').strip()

    sent = False
    if phone:
        sent = _send_otp_whatsapp(phone=phone, code=code, devis_ref=devis.reference)
    if not sent:
        sent = _send_otp_email(email=email, code=code, devis_ref=devis.reference,
                               company=devis.company)
    if not sent:
        logger.warning(
            'L-NIV: OTP lecture généré pour %s mais aucun canal disponible '
            '(phone=%s, email=%s)', devis.reference, bool(phone), bool(email))
    else:
        logger.info('L-NIV: OTP lecture envoyé pour devis %s', devis.reference)
    return None


def validate_otp_lecture(link, otp_code):
    """L-NIV — valide l'OTP de lecture soumis contre le cache.

    Succès → pose le drapeau ``otp_lecture_verified`` (TTL 1 h) et retourne
    None ; échec → message d'erreur FR, même discipline anti-brute-force que
    ``validate_esign_otp`` (QX10, ``OTP_MAX_ATTEMPTS`` tentatives)."""
    if not otp_code:
        return 'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».'

    from django.core.cache import cache
    attempts_key = _otp_lecture_attempts_key(link.token)
    attempts = cache.get(attempts_key, 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        # QJR147 — le message ne promet PLUS qu'un nouveau code débloque :
        # le compteur d'échecs n'est plus effacé à la régénération. Le
        # verrou est TEMPOREL (il expire avec la fenêtre du code).
        return ('Trop de tentatives incorrectes. Ce lien est « gelé » '
                'quelques minutes ; patientez, puis redemandez un code.')

    cache_key = _otp_lecture_cache_key(link.token)
    stored = cache.get(cache_key)
    if stored is None:
        return 'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.'
    if stored != otp_code.strip():
        cache.set(attempts_key, attempts + 1, timeout=OTP_CACHE_TTL)
        restantes = max(0, OTP_MAX_ATTEMPTS - (attempts + 1))
        if restantes == 0:
            return ('Trop de tentatives incorrectes. Ce lien est '
                    '« gelé » quelques minutes ; patientez, puis '
                    'redemandez un code.')
        return 'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.'

    # Code valide : consommé (one-time use), compteur remis à zéro, la
    # LECTURE reste déverrouillée pendant OTP_LECTURE_VERIFIED_TTL (la page
    # est consultée plusieurs fois, contrairement à l'acceptation ponctuelle).
    cache.delete(cache_key)
    cache.delete(attempts_key)
    cache.set(_otp_lecture_verified_key(link.token), True,
              timeout=OTP_LECTURE_VERIFIED_TTL)
    return None


def otp_lecture_verified(link):
    """True si la lecture de ``link`` a déjà été déverrouillée par un OTP
    valide dans la dernière heure. Toujours True si ``link.otp_lecture`` est
    False (rien à déverrouiller — comportement d'aujourd'hui)."""
    if not getattr(link, 'otp_lecture', False):
        return True
    from django.core.cache import cache
    return bool(cache.get(_otp_lecture_verified_key(link.token)))


def _send_otp_whatsapp(phone, code, devis_ref):
    """Envoie le code OTP via WhatsApp. Best-effort → bool.

    QX10 — CORRECTIF : ce canal est un STUB (aucune API WhatsApp live n'est
    câblée — GATÉ derrière QXG1/le BSP). Il renvoie désormais ``False`` au lieu
    de ``True`` : sinon un client SANS email (téléphone seul) ne recevait
    JAMAIS son code (le stub prétendait l'avoir envoyé et coupait le repli
    email), le verrouillant hors de la signature quand ``ESIGN_OTP_ENABLED``
    est actif. En renvoyant False, ``request_esign_otp`` retombe sur l'email.
    Quand le BSP WhatsApp sera disponible, envoyer réellement ici et renvoyer
    True."""
    logger.info(
        'QJ11 OTP WhatsApp NON envoyé (stub, aucun BSP câblé) pour devis %s '
        '— repli email', devis_ref)
    return False


def _send_otp_email(email, code, devis_ref, company=None):
    """Envoie le code OTP par email. Best-effort → bool.

    N100(c) white-label : la signature vient de la société du devis
    (``email_service._signature`` — BrandedTemplate ou « L'équipe {nom} »),
    jamais d'une marque codée en dur."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from ..email_service import _signature
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        sujet = f'Code de confirmation — devis {devis_ref}'
        corps = (
            f'Votre code de confirmation pour le devis {devis_ref} est :\n\n'
            f'    {code}\n\n'
            f'Ce code est valable 10 minutes.\n\n'
            f'Si vous n\'avez pas demandé ce code, ignorez ce message.\n\n'
            f"Cordialement,\n{_signature(company)}"
        )
        send_mail(sujet, corps, from_email, [email], fail_silently=False)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ11: email OTP échec : %s', exc)
        return False


def _create_esign_record(*, devis, nom, ip, user_agent='', consentement=True,
                         signature_image='', signed_at_client=None,
                         on_behalf_of='', lignes=None):
    """QJ10 — Crée le DevisSignature IMMUABLE si aucun n'existe encore.

    Idempotent : un enregistrement existant n'est jamais écrasé (la première
    signature fait foi). Best-effort : une exception ne remonte jamais —
    l'acceptation (statut + chatter) est déjà écrite avant cet appel.

    QX9 — persiste désormais la vraie preuve de signature (image manuscrite,
    consentement e-signature explicite, horodatage client, « au nom de ») que
    le front envoie et qui était auparavant jetée.

    WIR138 — CE N'EST PAS UN SOCLE E-SIGNATURE CONCURRENT. ``DevisSignature``
    est la PREUVE d'une acceptation faite EN LIGNE sur notre proposition (loi
    53-05) ; ``core.esign``, le socle canonique désigné, gère les DEMANDES
    envoyées à un prestataire externe (Yousign/DocuSign), aujourd'hui parquées
    faute de compte provisionné. Les deux ne fusionnent pas : ce chemin ne
    migrera jamais vers ``core.esign``. Voir ``core/esign.py`` et
    ``docs/esign-socle.md``.
    """
    try:
        from django.utils import timezone
        from apps.ventes.models import DevisSignature
        if DevisSignature.objects.filter(devis=devis).exists():
            return
        # NPLUS1 — lignes déjà chargées par l'appelant quand il les a (le hash
        # est identique : elles sont retriées par ``id`` côté modèle).
        content_hash = DevisSignature.compute_content_hash(devis, lignes=lignes)
        # ``signature_image`` peut être une data-URL volumineuse — on la borne
        # raisonnablement (les payloads canvas font ~quelques Ko).
        img = (signature_image or '')
        if len(img) > 200000:
            img = img[:200000]
        DevisSignature.objects.create(
            company=devis.company,
            devis=devis,
            signataire_nom=(nom or '')[:150],
            consentement_explicite=bool(consentement),
            ip_address=ip or None,
            user_agent=(user_agent or '')[:512],
            content_hash=content_hash,
            signed_at=timezone.now(),
            signature_image=img,
            consent_esign=bool(consentement),
            signed_at_client=signed_at_client or None,
            on_behalf_of=(on_behalf_of or '')[:150],
        )
        logger.info(
            'QJ10: DevisSignature créée pour devis %s (hash=%s…)',
            devis.reference, content_hash[:16])
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('QJ10: échec DevisSignature pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def verifier_empreinte_signature(devis, *, lignes=None):
    """QJR144 — LE VÉRIFICATEUR du sceau d'un devis signé.

    ``DevisSignature.content_hash`` existait depuis QJ10 mais AUCUN code du
    dépôt ne savait le recomparer : il était écrit une fois et relu seulement
    par des tests — un sceau que personne ne pouvait vérifier. Ce service est
    la porte de lecture, exposée en cross-app par ``apps.ventes.services``.

    Rend un dict FRANÇAIS, affichable tel quel :

    * ``signee`` — ce devis porte-t-il une signature électronique ;
    * ``intacte`` — ``True`` (le contenu reproduit l'empreinte), ``False`` (il
      a changé depuis la signature), ``None`` (aucune empreinte scellée : « on
      ne sait pas » n'est pas « falsifié ») ;
    * ``version`` — la version du payload qui concorde (2 = sceau étendu de
      QJR144 ; 1 = sceau d'origine, qui ne couvrait NI le taux de TVA par
      ligne, NI les lignes optionnelles, NI l'option retenue) ;
    * ``message`` — la phrase à montrer.

    LECTURE PURE : ne touche ni statut, ni ligne, ni total (règle #4).
    """
    from apps.ventes.models import DevisSignature

    signature = DevisSignature.objects.filter(devis=devis).first()
    if signature is None:
        return {
            'signee': False, 'intacte': None, 'version': None,
            'message': "Ce devis ne porte aucune signature électronique.",
        }
    intacte, version = signature.verifier_contenu(lignes=lignes)
    if intacte is None:
        return {
            'signee': True, 'intacte': None, 'version': None,
            'message': ("Cette signature ne porte aucune empreinte de "
                        "contenu : elle est antérieure au scellement, son "
                        "contenu ne peut donc pas être vérifié."),
        }
    if not intacte:
        return {
            'signee': True, 'intacte': False, 'version': None,
            'message': ("Le contenu de ce devis NE correspond PLUS à ce qui a "
                        "été signé : l'empreinte scellée ne se reproduit pas."),
        }
    if version == DevisSignature.CONTENT_HASH_V1:
        return {
            'signee': True, 'intacte': True, 'version': version,
            'message': ("Empreinte conforme (sceau d'origine). Portée : ce "
                        "sceau ne couvre ni le taux de TVA par ligne, ni les "
                        "lignes optionnelles, ni l'option retenue."),
        }
    return {
        'signee': True, 'intacte': True, 'version': version,
        'message': "Empreinte conforme : le contenu signé n'a pas changé.",
    }


def _store_signed_pdf(*, devis):
    """QJ22 — Génère et stocke le PDF de la proposition SIGNÉE dans MinIO.

    Réutilise le moteur premium existant (``generate_premium_devis_pdf`` +
    ``persist=True``) sans forker le moteur. La clé MinIO est ensuite stockée
    sur le ``DevisSignature`` lié pour qu'elle soit retrouvable sans ambiguïté.
    Ne rend PAS un nouveau PDF si le ``DevisSignature`` possède déjà une clé
    (idempotent). Best-effort : une exception ne remonte jamais ; l'acceptation
    est déjà écrite avant cet appel.
    """
    try:
        from apps.ventes.models import DevisSignature
        try:
            sig = DevisSignature.objects.get(devis=devis)
        except DevisSignature.DoesNotExist:
            return  # no signature record yet (shouldn't happen in normal flow)
        if sig.signed_pdf_key:
            return  # already stored — idempotent
        from apps.ventes.quote_engine import clean_pdf_options, generate_premium_devis_pdf
        key = generate_premium_devis_pdf(
            devis.id, clean_pdf_options({}), persist=True)
        DevisSignature.objects.filter(pk=sig.pk).update(signed_pdf_key=key)
        logger.info(
            'QJ22: PDF signé stocké pour devis %s → %s',
            devis.reference, key)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'QJ22: échec stockage PDF signé pour devis %s : %s',
            getattr(devis, 'reference', '?'), exc)


def _acceptance_deposit_block(devis, lignes=None):
    """QX33be — bloc texte « acompte + RIB » pour l'email de confirmation.

    Acompte = 1ʳᵉ tranche de l'échéancier (sur le TTC REMISÉ, chaîne QX1). RIB
    depuis ``settings.COMPANY_RIB`` si configuré. Chaîne VIDE quand rien n'est
    configurable (pas de tranche, pas de RIB) → email inchangé. Best-effort."""
    from decimal import Decimal
    try:
        from ..utils.echeancier import next_tranche
        # NPLUS1 — ``lignes`` déjà chargées par l'acceptation (elles ne bougent
        # pas pendant l'acceptation) ; absent ⇒ requête d'hier.
        tr = next_tranche(devis, lignes=lignes)
        if tr is None:
            return ''
        acompte = Decimal(str(tr['ttc']))
        montant_str = f'{acompte:,.2f}'.replace(',', ' ') + ' MAD'
        from django.conf import settings
        rib = (getattr(settings, 'COMPANY_RIB', '') or '').strip()
        lignes = [
            f"Pour démarrer votre installation, un acompte de {montant_str} "
            f"est à régler.",
        ]
        if rib:
            lignes.append(
                f"Vous pouvez l'effectuer par virement sur : {rib}")
            lignes.append(
                "Une fois le virement effectué, signalez-le depuis votre "
                "espace proposition pour informer votre conseiller.")
        return '\n'.join(lignes) + '\n\n'
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return ''


def _send_acceptance_emails(*, devis, user, lignes=None):
    """QJ10 — Envoie un email de confirmation de signature au client + au vendeur.

    Best-effort : une exception ne remonte jamais (l'acceptation est déjà écrite).
    Le PDF joint est récupéré depuis MinIO si disponible ; sinon l'email part
    sans pièce jointe (comportement réseau conforme à email_service.py).
    Jamais de prix_achat / marge dans les emails (règle #4).
    """
    try:
        from apps.ventes.email_service import send_document_email
        from apps.ventes.email_service import _signature as _signature_societe
        client = getattr(devis, 'client', None)
        dest = (getattr(client, 'email', '') or '').strip()
        nom_client = ''
        if client is not None:
            nom_client = (
                f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
            )
        salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
        # QX33be — bloc acompte (tranche 1 sur le TTC REMISÉ per QX1) + RIB si
        # configuré. Vide (aucune ligne) quand rien n'est configurable → texte
        # de confirmation inchangé.
        acompte_bloc = _acceptance_deposit_block(devis, lignes=lignes)
        # ── QJR134 / ES11 — L'EMAIL NE PROMET QUE CE QUI EXISTE ────────────
        #
        # CE QUI ÉTAIT FAUX. ``_create_esign_record`` est best-effort : son
        # échec est avalé en WARNING, ``_store_signed_pdf`` sort alors
        # silencieusement, et cet email affirmait INCONDITIONNELLEMENT « Votre
        # signature électronique a été enregistrée » — au client, par écrit,
        # alors qu'il pouvait n'exister ni image, ni IP, ni empreinte, ni PDF
        # scellé. Le devis étant gelé à l'édition après acceptation, la
        # situation n'était même pas rattrapable.
        #
        # La phrase (et la mention de l'exemplaire signé joint) ne part
        # désormais que si l'enregistrement de signature EXISTE vraiment. Sur
        # le chemin nominal — celui de toutes les signatures en ligne — il
        # existe, et l'email est byte-identique à celui d'hier.
        preuve = False
        try:
            from apps.ventes.models import DevisSignature
            preuve = DevisSignature.objects.filter(devis=devis).exists()
        except Exception:  # noqa: BLE001 — dans le doute, on ne promet rien
            preuve = False
        bloc_signature = (
            "Votre signature électronique a été enregistrée conformément "
            "à la loi 43-20 relative à l'échange électronique de données "
            "juridiques.\n\n"
        ) if preuve else ''
        bloc_exemplaire = (
            "Vous trouverez ci-joint votre exemplaire signé pour vos "
            "archives.\n\n"
        ) if preuve else ''
        corps = (
            f"{salut}\n\n"
            f"Nous avons bien reçu votre acceptation du devis "
            f"{devis.reference}.\n\n"
            f"{bloc_signature}"
            f"{acompte_bloc}"
            f"{bloc_exemplaire}"
            f"Merci pour votre confiance.\n\n"
            f"Cordialement,\n{_signature_societe(devis.company)}"
        )
        if dest:
            send_document_email(
                devis,
                to_email=dest,
                sujet=f'Proposition acceptée — {devis.reference}',
                corps=corps,
                user=user,
                attach_pdf=True,
                log_activity=False,  # l'acceptation a déjà son propre chatter
            )
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: email client échec pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    # Notification vendeur (in-app via notifications.services.notify).
    try:
        _notify_seller_accepted(devis=devis, user=user)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: notif vendeur échec pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _notify_seller_accepted(*, devis, user):
    """QJ10 / QJ2 (c) — Notification in-app + wa.me au vendeur (créateur du
    devis) lors de l'acceptation.

    Réutilise notifications.services.notify (N75). Best-effort : appelé
    dans un bloc except de l'appelant. Pas de notification si le devis n'a
    pas de créateur ou si le créateur est l'utilisateur courant (in-app
    pour soi-même serait du bruit). QJ2 ajoute un lien wa.me « répondre
    maintenant » vers le client dans le corps de la notification.
    """
    vendeur = getattr(devis, 'created_by', None)
    if vendeur is None:
        return
    # Éviter de notifier l'utilisateur qui effectue l'action lui-même.
    if user is not None and getattr(user, 'pk', None) == getattr(vendeur, 'pk', None):
        return
    from apps.notifications.services import notify
    client_nom = ''
    client = getattr(devis, 'client', None)
    if client is not None:
        client_nom = getattr(client, 'nom', '') or ''
    # QJ2 (c) — lien wa.me vers le client (via son téléphone sur le lead ou le
    # client). Best-effort : on préfère le numéro WhatsApp du lead d'origine.
    wa_url = _build_acceptance_wa_url(devis=devis)
    body_lines = [
        (
            f'Le client {client_nom} a accepté le devis {devis.reference}.'
        ) if client_nom else f'Le devis {devis.reference} a été accepté.',
    ]
    if wa_url:
        body_lines.append(f'Répondre maintenant : {wa_url}')
    notify(
        user=vendeur,
        event_type='devis_accepted',
        title=f'Devis {devis.reference} accepté',
        body='\n'.join(body_lines),
        link=f'/ventes/devis/{devis.pk}',
        company=getattr(devis, 'company', None),
    )


def _build_acceptance_wa_url(*, devis):
    """QJ2 (c) — Construit le lien wa.me « répondre maintenant » au client.

    Cherche d'abord le numéro WhatsApp du lead lié au devis, puis le numéro
    du client (champ telephone). Renvoie l'URL ou None. Best-effort — jamais
    d'exception remontée. Les prix d'achat ne sont JAMAIS exposés (règle #4).
    """
    try:
        import urllib.parse
        # Prefer lead WhatsApp, then lead telephone, then client telephone.
        phone_raw = ''
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            phone_raw = (
                getattr(lead, 'whatsapp', None)
                or getattr(lead, 'telephone', None)
                or ''
            )
        if not phone_raw:
            client = getattr(devis, 'client', None)
            if client is not None:
                phone_raw = getattr(client, 'telephone', '') or ''
        digits = ''.join(c for c in (phone_raw or '') if c.isdigit())
        if not digits:
            return None
        # Format international marocain (wa.me exige l'indicatif pays).
        if digits.startswith('00'):
            digits = digits[2:]
        if digits.startswith('0'):
            digits = '212' + digits[1:]
        elif not digits.startswith('212'):
            digits = '212' + digits
        nom = ''
        if lead is not None:
            nom = (getattr(lead, 'nom', '') or '').strip()
        if not nom and devis.client_id:
            client = getattr(devis, 'client', None)
            if client is not None:
                nom = (getattr(client, 'nom', '') or '').strip()
        nom = nom or 'votre client'
        text = urllib.parse.quote(
            f'Bonjour {nom}, votre proposition {devis.reference} a bien été '
            f'confirmée. Merci pour votre confiance !'
        )
        return f'https://wa.me/{digits}?text={text}'
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ2: _build_acceptance_wa_url échoué : %s', exc)
        return None


# ── QJ9 — Attribution first-touch + Meta CAPI hook ───────────────────────────

#: Champs UTM/fbclid copiés du Lead vers etude_params du Devis à l'acceptation.
_ATTRIBUTION_FIELDS = (
    'fbclid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
)


def _persist_attribution(*, devis):
    """QJ9 — Copie les champs d'attribution first-touch du lead vers le devis.

    À l'acceptation, les UTM/fbclid du Lead d'origine sont snapshottés dans
    ``devis.etude_params['attribution']`` (JSONField déjà sur le modèle — aucune
    migration). Cette copie est LOSSLESS : l'attribution reste disponible même si
    le lead est fusionné, archivé ou supprimé plus tard.

    Idempotent : ne ré-écrit pas si une attribution est déjà présente.
    Aucun impact sur les statuts (règle #4 — pure donnée dérivée en lecture seule).
    Ne lève jamais : l'appelant attrape toute exception.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return  # Devis sans lead — aucune attribution à copier.

    params = dict(devis.etude_params or {})
    if 'attribution' in params:
        return  # Déjà présent — idempotent.

    attribution = {}
    for field in _ATTRIBUTION_FIELDS:
        val = getattr(lead, field, None)
        if val:
            attribution[field] = val

    if not attribution:
        return  # Lead sans données d'attribution — rien à copier.

    params['attribution'] = attribution
    devis.etude_params = params
    devis.save(update_fields=['etude_params'])
    logger.info('QJ9: attribution copiée pour devis %s → %s',
                getattr(devis, 'reference', '?'), list(attribution.keys()))


def _fire_capi_signed_quote(*, devis, ip=None, user_agent=''):
    """QJ9 — Émet un événement « SignedQuote » vers l'API Conversions Meta (CAPI).

    Gate : si ``META_CAPI_ACCESS_TOKEN`` est absent (ou vide) dans les settings
    ou l'environnement, on dégrade en no-op silencieux (log uniquement). Cela
    permet de pré-câbler l'intégration sans créer de dépendance sur un token
    absent en dev/staging.

    Conformité règle #4 : ne touche jamais les statuts Devis/Facture.
    Conformité règle #3 (CLAUDE.md) : le call HTTP CAPI est server-side — jamais
    de création de campagne (interdit par règle #3).
    Ne lève jamais : l'appelant attrape toute exception.

    L'événement CAPI inclut les données d'attribution (fbclid/UTM) snapshottées
    dans etude_params (QJ9 _persist_attribution) pour un matching maximal.

    Env var attendue : ``META_CAPI_ACCESS_TOKEN`` (token de page Meta / CAPI).
    Var optionnelle : ``META_CAPI_PIXEL_ID`` (Pixel ID — peut être vide).
    """
    import os
    from django.conf import settings

    token = (
        getattr(settings, 'META_CAPI_ACCESS_TOKEN', None)
        or os.environ.get('META_CAPI_ACCESS_TOKEN', '')
        or ''
    ).strip()
    if not token:
        logger.info(
            'QJ9: CAPI SignedQuote ignoré pour devis %s — META_CAPI_ACCESS_TOKEN absent',
            getattr(devis, 'reference', '?'))
        return

    pixel_id = (
        getattr(settings, 'META_CAPI_PIXEL_ID', None)
        or os.environ.get('META_CAPI_PIXEL_ID', '')
        or ''
    ).strip()

    # Récupère l'attribution snapshottée (QJ9) ou tente le lead directement.
    attribution = {}
    params = devis.etude_params or {}
    if 'attribution' in params:
        attribution = params['attribution']
    else:
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            for field in _ATTRIBUTION_FIELDS:
                val = getattr(lead, field, None)
                if val:
                    attribution[field] = val

    import hashlib
    import time
    # QJR147 — ``urllib.parse`` n'est plus nécessaire : le jeton ne part plus
    # en query string (il est dans le corps JSON, voir plus bas).
    import urllib.request
    import json as _json

    # Données de l'événement CAPI (hachage SHA-256 pour le PII).
    def _sha256(val):
        return hashlib.sha256((val or '').strip().lower().encode()).hexdigest()

    event_time = int(time.time())
    client = getattr(devis, 'client', None)
    email_hash = _sha256(getattr(client, 'email', '') or '') if client else ''
    phone_raw = ''
    if client:
        phone_raw = getattr(client, 'telephone', '') or ''
    # ── QJR136 / ES9 — LE TÉLÉPHONE PART EN E.164, PAS EN CHIFFRES NUS ──────
    #
    # CE QUI ÉTAIT FAUX. Le hash portait ``''.join(c for c in phone_raw if
    # c.isdigit())`` — donc « 0600000000 » SANS indicatif pays, alors que Meta
    # apparie sur un numéro E.164. L'appariement ``ph`` échouait donc
    # SYSTÉMATIQUEMENT et l'EMQ chutait. La MÊME app expose déjà la règle
    # (``utils/phone.normalize_phone_e164``), ``apps/adsengine/audiences.py``
    # l'utilise pour ses uploads Meta, et ce fichier savait le faire cent
    # lignes plus haut pour le lien wa.me : une quatrième dérivation locale
    # n'avait aucune raison d'exister.
    #
    # Un numéro NON normalisable (local ambigu, saisie incomplète) ne produit
    # plus un hash faux : il ne produit AUCUNE clé ``ph``.
    from apps.ventes.utils.phone import normalize_phone_e164
    phone_e164 = normalize_phone_e164(phone_raw)
    phone_hash = _sha256(phone_e164) if phone_e164 else ''

    # ── QJR136 / ES8 — AUCUNE VALEUR N'EST ENVOYÉE SI ELLE N'EST PAS SÛRE ───
    #
    # Valeur de conversion : TTC REMISÉ de l'option acceptée (QX2 — chaîne
    # canonique QX1), jamais le TTC brut du devis. Le repli sur
    # ``Devis.total_ttc`` était précisément ce TTC BRUT (``models.Devis`` ne
    # déduit jamais ``remise_globale``) et la SOMME des deux options — le
    # motif brut-vs-net (QJR22/23/24) survivant dans un repli, et corrompant le
    # ROAS et l'optimisation d'enchères de la campagne.
    #
    # On ne devine plus : quand la chaîne canonique échoue, on N'ENVOIE RIEN.
    # Un événement manquant se rattrape ; un montant faux entraîne durablement
    # l'algorithme d'enchères.
    try:
        from apps.ventes.utils.options import option_totaux
        value = float(option_totaux(devis)['ttc'])
    except Exception:  # noqa: BLE001 — CAPI ne casse jamais l'acceptation
        logger.warning(
            'QJR136: CAPI SignedQuote NON envoyé pour devis %s — la valeur de '
            "conversion canonique est indisponible (aucun montant n'est "
            'deviné).', getattr(devis, 'reference', '?'), exc_info=True)
        return

    user_data = {}
    if email_hash:
        user_data['em'] = [email_hash]
    if phone_hash:
        user_data['ph'] = [phone_hash]
    fbclid = attribution.get('fbclid', '')
    if fbclid:
        user_data['fbc'] = f'fb.1.{int(time.time() * 1000)}.{fbclid}'
    # ADSENG2 — EMQ (Event Match Quality) : ip + user_agent NON hachés (Meta les
    # recommande tels quels). Déjà disponibles au point d'acceptation (accept_devis
    # les reçoit), auparavant abandonnés ici. Aucune nouvelle collecte de donnée.
    if ip:
        user_data['client_ip_address'] = str(ip)
    if user_agent:
        user_data['client_user_agent'] = str(user_agent)

    custom_data = {
        'currency': 'MAD',
        'value': value,
        'order_id': str(getattr(devis, 'reference', '')),
    }
    utm_source = attribution.get('utm_source', '')
    if utm_source:
        custom_data['utm_source'] = utm_source
    utm_campaign = attribution.get('utm_campaign', '')
    if utm_campaign:
        custom_data['utm_campaign'] = utm_campaign

    # ADSENG2 — event_id DÉTERMINISTE (dedup) : Meta dé-duplique deux événements
    # de même event_name + event_id dans une fenêtre de 48 h. La référence du
    # devis est unique et déjà la clé d'idempotence naturelle ailleurs — la
    # réutiliser ferme d'avance tout double-comptage si un Pixel navigateur est
    # un jour ajouté sur /proposal.
    event_id = f'signedquote:{getattr(devis, "reference", "") or devis.pk}'

    event = {
        'event_name': 'SignedQuote',
        'event_time': event_time,
        'event_id': event_id,
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data,
    }

    # ADSENG2 — version depuis la SOURCE UNIQUE partagée (v25 courante), jamais
    # la v19.0 codée en dur (expirée 02/2025 → 400 garanti dès qu'un pixel est
    # configuré). Constante plain (aucun modèle adsengine importé dans ventes).
    from apps.adsengine.api_version import GRAPH_BASE_URL
    api_url = f'{GRAPH_BASE_URL}/{pixel_id}/events' if pixel_id else None

    if not api_url:
        logger.info(
            'QJ9: CAPI SignedQuote prêt pour devis %s (pixel non configuré — log seul) '
            'fbclid=%s utm_source=%s value=%.2f MAD',
            getattr(devis, 'reference', '?'), fbclid, utm_source, value)
        return

    # ── QJR147 / ES7 — LE JETON VOYAGE DANS LE CORPS, PAS EN QUERY STRING ───
    # L'API Conversions accepte ``access_token`` dans le corps JSON. En query
    # string, il finit dans les journaux d'accès et les proxys traversés —
    # risque ENVIRONNEMENTAL (vérifié : ce code ne le journalise pas lui-même,
    # le ``logger.warning`` du bloc HTTP ne formate que l'exception).
    payload = _json.dumps(
        {'data': [event], 'access_token': token}).encode('utf-8')
    req = urllib.request.Request(
        api_url, data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_body = resp.read().decode('utf-8', errors='replace')
            logger.info(
                'QJ9: CAPI SignedQuote envoyé pour devis %s — status %s body %.200s',
                getattr(devis, 'reference', '?'), resp.status, resp_body)
    except Exception as exc:
        logger.warning('QJ9: CAPI SignedQuote HTTP échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _effondrer_soeurs_et_publier(*, devis, user, date_acc, ancien,
                                 groupe=None):
    """QJR134 — L'AVAL D'UNE ACCEPTATION, dans la transaction de l'appelant.

    YDOCF3 — variantes (QJ15 dupliquer-variante) : accepter l'une d'elles doit
    effondrer ses SŒURS (même groupe ``version_parent``=racine) plutôt que de
    les laisser ``is_active=True`` et elles-mêmes acceptables (double comptage
    du funnel). Ne touche jamais un devis d'un autre groupe ni les révisions
    déjà terminales. Un devis sans variante est inchangé.

    M6 — puis PUBLIE ``devis_accepted`` : c'est cet événement qui déclenche la
    chaîne bon-commande / facture / chantier. Il vit ici, avec l'effondrement,
    parce que les deux forment UNE seule vente : les séparer, c'est exactement
    l'état partiel qu'ES3 décrit.

    ``groupe`` — les devis du groupe DÉJÀ verrouillés par l'appelant (il les a
    lus sous ``select_for_update``, dans l'ordre des ``pk``). Absent, ils sont
    relus et verrouillés ici, dans le même ordre : la fonction est donc
    utilisable seule, sans jamais relâcher la garantie anti-course.

    N'ATTRAPE RIEN : une exception remonte, donc la transaction de l'appelant
    est annulée en bloc. C'est le point de QJR134.
    """
    from django.db.models import Q
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_accepted

    racine = devis.version_parent_id or devis.pk
    if groupe is None:
        groupe = list(
            Devis.objects
            .select_for_update(of=('self',))
            .filter(Q(pk=racine) | Q(version_parent_id=racine))
            .order_by('pk'))
    for soeur in groupe:
        # Le filtre est celui d'hier, mot pour mot — mais appliqué aux lignes
        # DÉJÀ VERROUILLÉES plutôt que par une seconde requête non verrouillée.
        if soeur.pk == devis.pk or not soeur.is_active:
            continue
        if soeur.company_id != devis.company_id:
            continue
        if soeur.statut not in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            continue
        soeur.statut = Devis.Statut.REFUSE
        soeur.date_refus = date_acc
        soeur.motif_refus = 'variante non retenue'
        soeur.is_active = False
        soeur.save(update_fields=[
            'statut', 'date_refus', 'motif_refus', 'is_active'])
        activity.log_devis_refusal(
            soeur, user, 'variante non retenue', date_acc)

    devis_accepted.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)


def accept_devis(*, devis, user, nom='', date_acceptation=None, option='',
                 ip=None, user_agent='', consentement=True,
                 signature_image='', signed_at_client=None, on_behalf_of='',
                 idempotent_reaccept=True, rejouer_aval=False):
    """Q7 — flip a Devis to « accepté » through the ONE acceptance path.

    Shared by the in-app viewset action (N25) and the tokenized web proposal
    (Q7): records the stamp (typed name + date [+ IP in the chatter]), sets the
    accepted option, writes the acceptance activity and emits the
    ``devis_accepted`` domain event — so the downstream BonCommande/Facture
    chain is preserved 1:1 (rule #4). The engine only RENDERS elsewhere; this
    is the single place a quote document changes status to accepté.

    With ``idempotent_reaccept=True`` (default) a re-submit on an
    already-accepted devis is returned unchanged (no second stamp, no second
    event) so a double e-signature submit on the tokenized web proposal (Q7)
    is a no-op. With ``idempotent_reaccept=False`` (the in-app viewset action)
    an already-accepted devis raises ``AcceptError(conflict=True)`` → 409,
    preserving the ERR33 re-accept guard.

    QJR134 — TOUT CE QUI ÉCRIT EN BASE EST DANS UNE SEULE TRANSACTION, sous un
    verrou pris sur le GROUPE DE VARIANTES entier : statut, chatter, preuve de
    signature, attribution, effondrement des sœurs et ``devis_accepted``
    tombent ou tiennent ENSEMBLE. Le PDF scellé, les emails et l'événement Meta
    restent APRÈS le commit (entrées-sorties best-effort). ``rejouer_aval=True``
    rejoue l'aval d'un devis DÉJÀ accepté — le geste de réparation d'un devis
    accepté AVANT ce lot, quand le statut pouvait être commité seul.

    Raises ``AcceptError`` on a non-acceptable status or an invalid option.
    """
    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity

    # QX41 — verrou anti-course sur le chemin public d'acceptation : deux POST
    # concurrents (double-clic / rejeu) pouvaient tous deux passer le contrôle
    # de statut et double-émettre ``devis_accepted`` (effets aval doublés). On
    # relit le devis VERROUILLÉ (select_for_update) et on recontrôle son statut
    # SOUS le verrou : le second appel voit ACCEPTE et devient un no-op.
    valid = {c.value for c in Devis.OptionAcceptee}
    option = (option or '').strip()
    if option and option not in valid:
        raise AcceptError(
            'Option invalide (attendu « sans_batterie » ou « avec_batterie »).')

    # QX41 — TOUT le contrôle-puis-bascule de statut se fait SOUS le même verrou
    # (select_for_update) : deux acceptations concurrentes ne peuvent plus
    # toutes deux voir « envoyé » et double-basculer/double-émettre l'événement.
    date_acc = date_acceptation or timezone.now().date()
    with transaction.atomic():
        # ── QJR134 / ES14 — LE GROUPE DE VARIANTES EST VERROUILLÉ EN ENTIER ──
        #
        # CE QUI ÉTAIT FAUX. Le verrou ne portait que sur LA ligne du devis
        # accepté (``of=('self',)``), et l'effondrement des sœurs s'exécutait
        # hors de lui, sans ``select_for_update`` : deux POST concurrents sur
        # DEUX jetons du MÊME groupe de variantes basculaient TOUS DEUX en
        # « accepté » — deux événements, deux chaînes bon-commande/facture pour
        # une seule vente.
        #
        # On verrouille donc TOUT le groupe (la racine et ses variantes), et
        # dans un ORDRE DÉTERMINISTE (``order_by('pk')``) : deux acceptations
        # concurrentes sur deux sœurs prennent les verrous dans le MÊME ordre,
        # donc l'une attend l'autre au lieu de s'inter-bloquer. La seconde
        # relit alors des sœurs déjà refusées et son propre devis déjà accepté.
        #
        # NPLUS1 (27/08/2026, préservé) — les trois relations sont jointes ici
        # plutôt que relues paresseusement plus bas (``_create_esign_record``
        # → ``devis.company``, ``_send_acceptance_emails``/
        # ``_notify_seller_accepted`` → ``devis.client``,
        # ``_persist_attribution`` → ``devis.lead``).
        # ``of=('self',)`` reste OBLIGATOIRE : ``company`` et ``lead`` sont
        # nullables, donc joints en LEFT OUTER JOIN — et PostgreSQL refuse
        # « FOR UPDATE » sur le côté nullable d'une jointure externe.
        racine = devis.version_parent_id or devis.pk
        groupe = list(
            Devis.objects
            .select_related('client', 'company', 'lead')
            .select_for_update(of=('self',))
            .filter(Q(pk=racine) | Q(version_parent_id=racine))
            .order_by('pk'))
        courant = next((d for d in groupe if d.pk == devis.pk), None)
        if courant is None:
            raise AcceptError('Devis introuvable.', conflict=True)
        devis = courant

        # Re-submit on an already-accepted devis: a no-op for the tokenized
        # web proposal, but rejected (409) for the in-app action (ERR33 guard).
        if devis.statut == Devis.Statut.ACCEPTE:
            # QJR134 — LE REJEU DE L'AVAL. Depuis ce lot, « accepté » SIGNIFIE
            # que tout l'aval a été commité avec le statut (voir ci-dessous) :
            # c'est LE drapeau de complétion. Un devis accepté AVANT ce lot
            # peut, lui, porter un état partiel (statut commité seul, puis un
            # abonné en échec) que la garde d'idempotence rendait
            # définitivement irréparable — ``rejouer_aval=True`` rejoue cet
            # aval sans retoucher ni le statut, ni le tampon, ni la signature.
            if rejouer_aval:
                _effondrer_soeurs_et_publier(
                    devis=devis, user=user, date_acc=date_acc,
                    # Un devis accepté vient TOUJOURS de brouillon/envoyé
                    # (garde ERR33) et le SEUL récepteur qui lit
                    # ``ancien_statut`` s'en sert pour avancer un funnel qui ne
                    # recule jamais : le rejeu est donc idempotent.
                    ancien=Devis.Statut.ENVOYE, groupe=groupe)
                return devis
            if idempotent_reaccept:
                return devis
            raise AcceptError('Ce devis est déjà accepté.', conflict=True)

        # ERR33 — only a live devis (brouillon / envoyé) can be accepted.
        if devis.statut not in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            raise AcceptError(
                'Seul un devis en cours (brouillon ou envoyé) peut être '
                f'accepté ; statut actuel : « {devis.get_statut_display()} ».',
                conflict=True)

        # Resolve the option exactly like the viewset (two-option devis require
        # an explicit choice; single-option devis deduce it from the scenario).
        #
        # ── QJR133 / ES2 (audit du 30/08/2026) — ON NE DEVINE PLUS L'OPTION ──
        #
        # CE QUI ÉTAIT FAUX. ``build_quote_data`` était le SEUL détecteur
        # consulté, et son ``except Exception: nb_options, scenario = 1, ''``
        # faisait disparaître le garde-fou « deux options → choix explicite »
        # PUIS retombait sur un repli FIXE (« sans_batterie »). Or l'option
        # acceptée est AUTORITATIVE en aval (``utils/echeancier`` : « on facture
        # UNIQUEMENT les lignes de l'option retenue ») : le client se retrouvait
        # engagé, facturé et approvisionné sur un périmètre qu'il n'avait pas
        # choisi, sans qu'aucune erreur ne soit levée. Chemin d'atteinte : un
        # POST public sur ``/proposal/<token>/accept`` sans champ ``option``.
        #
        # LA RÈGLE. Quand la détection est INDISPONIBLE et que l'appelant n'a
        # pas dit l'option, on REFUSE (``AcceptError`` → 400) au lieu d'en
        # figer une. Le prédicat LÉGER ``deux_options_declarees`` (QJR55 : LE
        # prédicat du dépôt, deux requêtes, AUCUN rendu de document) sert alors
        # à formuler le bon refus — « précisez l'option » quand il voit deux
        # options, sinon « le document n'a pas pu être construit ».
        #
        # LE MOTEUR RESTE LE DÉTECTEUR QUAND IL RÉPOND, délibérément : c'est
        # lui qui a produit le document que le CLIENT a sous les yeux. Faire
        # trancher le prédicat léger PAR-DESSUS un moteur qui a répondu
        # « une option » exigerait un choix que l'écran client n'offre pas.
        #
        # Un appelant qui a DÉJÀ passé ``option`` n'est jamais bloqué : il n'y
        # a plus rien à deviner.
        detection_sure = True
        try:
            from apps.ventes.quote_engine.builder import build_quote_data
            qd = build_quote_data(devis, {'pdf_mode': 'onepage'})
            nb_options = qd.get('nb_options', 1)
            scenario = qd.get('scenario', '')
        except Exception:  # noqa: BLE001 — l'acceptation ne doit jamais casser
            logger.exception(
                'QJR133 : détection des options indisponible sur le devis %s '
                "— l'acceptation sans option explicite est refusée.",
                getattr(devis, 'reference', '?'))
            detection_sure = False
            nb_options, scenario = 1, ''
        if not detection_sure and not option:
            from apps.ventes.utils.options import deux_options_declarees
            if deux_options_declarees(devis):
                raise AcceptError(
                    'Ce devis comporte deux options — précisez celle choisie '
                    'par le client (« sans_batterie » ou « avec_batterie »).')
            raise AcceptError(
                "Le récapitulatif de ce devis n'a pas pu être construit : "
                "l'option retenue ne peut donc pas être déterminée. "
                "L'acceptation est refusée plutôt que d'engager le client sur "
                "un périmètre qu'il n'a pas choisi. Réessayez, ou précisez "
                'l\'option (« sans_batterie » ou « avec_batterie »).')
        if nb_options == 2 and not option:
            raise AcceptError(
                'Ce devis comporte deux options — précisez celle choisie par '
                'le client (« sans_batterie » ou « avec_batterie »).')
        if not option:
            option = (Devis.OptionAcceptee.AVEC_BATTERIE
                      if scenario == 'Avec batterie'
                      else Devis.OptionAcceptee.SANS_BATTERIE)

        ancien = devis.statut
        devis.statut = Devis.Statut.ACCEPTE
        devis.date_acceptation = date_acc
        devis.accepte_par_nom = (nom or '')[:150]
        devis.option_acceptee = option
        devis.save(update_fields=[
            'statut', 'date_acceptation', 'accepte_par_nom', 'option_acceptee'])

        # ── QJR134 / ES3 — L'AVAL EST DANS LA MÊME TRANSACTION ─────────────
        #
        # CE QUI ÉTAIT FAUX. Le ``with transaction.atomic()`` se refermait
        # ICI : le statut était commité SEUL, puis chatter, signature,
        # attribution, effondrement des sœurs et ``devis_accepted.send``
        # s'exécutaient hors transaction et hors verrou, sans
        # ``ATOMIC_REQUESTS`` (vérifié : absent des settings). Un échec chez
        # UN abonné (``send()`` propage la première exception) laissait un
        # devis « accepté » SANS bon de commande ni facture — et la garde
        # d'idempotence rendait le rejeu impossible : l'état partiel était
        # PERMANENT et SILENCIEUX.
        #
        # Tout ce qui écrit en BASE est donc remonté ici : soit la vente
        # entière est enregistrée, soit RIEN ne l'est et le client peut
        # simplement re-signer. « accepté » redevient ainsi un drapeau de
        # complétion qui dit la vérité.
        #
        # CE QUI RESTE DEHORS, et pourquoi : le PDF scellé, les emails et
        # l'événement Meta sont des ENTRÉES-SORTIES. Les exécuter dans la
        # transaction tiendrait les verrous pendant un rendu de document et un
        # appel réseau — et surtout, un email annonçant une vente qui vient
        # d'être annulée par un rollback serait pire que pas d'email du tout.
        activity.log_devis_acceptance(devis, user, nom, date_acc, option)
        if ip:
            # Trace the e-signature origin IP in the chatter (Q7) without a new
            # column — kept beside the acceptance stamp for the audit trail.
            activity.log_devis_note(
                devis, user, f'Signature en ligne acceptée — IP {ip}')

        # NPLUS1 (27/08/2026) — LES LIGNES DU DEVIS, CHARGÉES UNE SEULE FOIS.
        # Le statut vient d'être basculé sous verrou : les lignes ne changent
        # plus pendant la suite de l'acceptation. Elles alimentent l'empreinte
        # de signature (``compute_content_hash``) ET l'acompte de l'email
        # (``_acceptance_deposit_block`` → ``next_tranche`` →
        # ``option_totaux``), qui refaisaient chacun leur propre requête
        # lignes+produit. Best-effort : un échec de chargement rend ``None`` et
        # chaque appelé requête comme avant — jamais une acceptation cassée
        # pour une optimisation.
        try:
            lignes_devis = list(devis.lignes.select_related('produit').all())
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            lignes_devis = None

        # QJ10 — Enregistrement IMMUABLE de signature (loi 53-05).
        # Idempotent : si un DevisSignature existe déjà (re-submit idempotent)
        # on ne crée pas de second enregistrement — la signature d'origine fait
        # foi.
        _create_esign_record(
            devis=devis, nom=nom, ip=ip,
            user_agent=user_agent, consentement=consentement,
            signature_image=signature_image, signed_at_client=signed_at_client,
            on_behalf_of=on_behalf_of, lignes=lignes_devis,
        )
        # QJ9 — Attribution first-touch : copie UTM/fbclid du lead vers
        # etude_params du devis pour que l'attribution reste lossless même si
        # le lead est fusionné.
        try:
            _persist_attribution(devis=devis)
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'QJ9: _persist_attribution échoué pour devis %s : %s',
                getattr(devis, 'reference', '?'), exc)

        # YDOCF3 + M6 — l'effondrement des sœurs ET la publication de
        # l'événement, sous le verrou du groupe pris plus haut.
        _effondrer_soeurs_et_publier(
            devis=devis, user=user, date_acc=date_acc, ancien=ancien,
            groupe=groupe)

    # ── APRÈS LE COMMIT — entrées-sorties best-effort, jamais bloquantes ────
    # QJ22 — Stockage de l'artefact PDF signé (proposition verrouillée).
    # Appelé APRÈS _create_esign_record pour que le DevisSignature existe déjà.
    _store_signed_pdf(devis=devis)
    # QX9 — le PDF signé est persisté sur une AUTRE instance (via le moteur) ;
    # on rafraîchit ``fichier_pdf`` sur l'instance courante pour que la pièce
    # jointe de l'email ne parte pas sur un état périmé (bug de l'exemplaire
    # signé manquant).
    try:
        devis.refresh_from_db(fields=['fichier_pdf'])
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # QJ10 — Email de confirmation PDF verrouillé au client + au vendeur.
    try:
        _send_acceptance_emails(devis=devis, user=user, lignes=lignes_devis)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: _send_acceptance_emails échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)

    # QJ9 — CAPI SignedQuote event (gated on META_CAPI_ACCESS_TOKEN).
    # ADSENG2 — thread ip/user_agent (EMQ) déjà reçus par accept_devis.
    try:
        _fire_capi_signed_quote(devis=devis, ip=ip, user_agent=user_agent)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ9: _fire_capi_signed_quote échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    return devis


def share_link_for_bcf(bcf):
    """QS3 — Point d'entrée cross-app : crée (ou réutilise) le lien tokenisé
    vers le PDF d'un Bon de Commande FOURNISSEUR (stock).

    L'app ``stock`` appelle CE service plutôt que d'importer ``ventes.models``
    (règle de modularité). La société vient du BCF (jamais du corps). Renvoie
    l'objet ShareLink (porte ``token`` + ``expires_at``)."""
    from apps.ventes.models import ShareLink
    return ShareLink.for_bon_commande_fournisseur(bcf)


# ── PUB69 — Carte de partage client trackable (« mon installation ») ────────
# Canal UTM dédié, remonte dans l'attribution existante comme canal DISTINCT
# (`apps.adsengine.attribution.referral_share_channel_summary`).
INSTALLATION_SHARE_UTM_CAMPAIGN = 'parrainage_whatsapp'


def installation_share_link(devis, *, base_url=''):
    """PUB69 — Réutilise l'infra ``ShareLink``/UTM EXISTANTE de ventes
    (``ShareLink.for_devis``, QJ1 — RÉUTILISÉE, aucun nouveau modèle) pour
    générer (ou récupérer) le lien « mon installation » du client APRÈS
    SIGNATURE — un devis ACCEPTÉ seulement (avant signature, ce n'est pas
    encore « son installation »). ``None`` si le devis n'est pas accepté.

    Renvoie ``(ShareLink, url)`` ; ``url`` porte les UTM canal
    ``parrainage_whatsapp`` (bouche-à-oreille organique mesuré) — remonte
    dans l'attribution existante comme canal DISTINCT, sans toucher le
    canal Meta."""
    from django.conf import settings

    from ..models import Devis, ShareLink
    from ..utils.client_links import chemin_proposition

    if devis is None or devis.statut != Devis.Statut.ACCEPTE:
        return None, ''
    link = ShareLink.for_devis(devis)
    base = base_url or getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    query = (
        'utm_source=client&utm_medium=whatsapp'
        f'&utm_campaign={INSTALLATION_SHARE_UTM_CAMPAIGN}')
    path = f'{chemin_proposition(devis, link.token)}?{query}'
    url = (base.rstrip('/') + path) if base else path
    return link, url


def bcf_share_url(bcf, request=None):
    """QS3 — URL publique absolue vers le PDF tokenisé d'un BCF fournisseur.

    Réutilise la construction d'URL publique existante. Renvoie ``(url, token)``.
    Le lien reste imprévisible + expirant ; il est destiné au FOURNISSEUR et
    n'est jamais surfacé dans l'UI client."""
    from django.conf import settings
    link = share_link_for_bcf(bcf)
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    path = f'/api/django/public/bcf/{link.token}/'
    if base:
        url = base.rstrip('/') + path
    elif request is not None:
        url = request.build_absolute_uri(path)
    else:
        url = path
    return url, link.token


def contexte_clauses_devis(devis):
    """NTCPQ11 — Contexte plat servant à évaluer les clauses/CGV dynamiques.

    Clés exposées : ``type_deal`` (= ``mode_installation``), ``montant``
    (= total TTC), ``total_ht``, ``total_ttc``, ``remise_globale``,
    ``puissance_kwc``, ``devise``. Aucun prix d'achat / aucune marge (donnée
    interne — jamais dans un texte destiné au client).

    QJR54 (29/08/2026) — LE MONTANT QUI CHOISIT LA TRANCHE EST LE **NET**. Ces
    clauses sont sélectionnées par tranche de montant PUIS IMPRIMÉES sur le PDF
    client : alimenter le moteur avec un total non remisé pouvait figer un
    devis remisé avec le jeu de CGV d'une tranche SUPÉRIEURE. La lecture passe
    donc par la vue NET NOMMÉE de ``domain.argent`` — remise globale honorée et
    option effective — au lieu de dépendre de ce que ``Devis.total_*`` veut
    dire ce mois-ci.
    """
    from decimal import Decimal, InvalidOperation

    from apps.ventes.domain.argent import Vue, totaux as totaux_argent

    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    try:
        kwc = float(etude.get('puissance_kwc') or 0)
    except (TypeError, ValueError):
        kwc = 0.0
    try:
        vue = totaux_argent(devis, vue=Vue.NET)
        total_ht = float(vue.ht_net or 0)
        total_ttc = float(vue.ttc or 0)
    except (TypeError, ValueError, InvalidOperation):
        total_ht = total_ttc = 0.0
    return {
        'type_deal': devis.mode_installation or '',
        'mode_installation': devis.mode_installation or '',
        'montant': total_ttc,
        'total_ht': total_ht,
        'total_ttc': total_ttc,
        'remise_globale': float(devis.remise_globale or Decimal('0')),
        'puissance_kwc': kwc,
        'devise': devis.devise or 'MAD',
    }


def figer_clauses_devis(devis):
    """NTCPQ11 — FIGE les clauses/CGV applicables sur le devis (snapshot).

    Appelé au passage brouillon → envoyé. Idempotent et WRITE-ONCE : si
    ``clauses_appliquees`` porte déjà une valeur (même une liste vide figée),
    rien n'est recalculé — modifier une clause plus tard n'altère jamais un
    devis déjà envoyé. Lecture cross-app cpq via import LOCAL (selectors).
    Ne lève jamais : un incident de configuration ne doit pas bloquer un envoi.
    Renvoie la liste figée."""
    if devis.clauses_appliquees is not None:
        return devis.clauses_appliquees
    try:
        from apps.cpq.selectors import clauses_applicables
        clauses = clauses_applicables(
            company=devis.company, context=contexte_clauses_devis(devis))
    except Exception:  # noqa: BLE001 — un envoi ne casse jamais sur les CGV
        logger.exception(
            'NTCPQ11 : figeage des clauses ignoré (devis %s)', devis.pk)
        return None
    devis.clauses_appliquees = clauses
    devis.save(update_fields=['clauses_appliquees'])
    return clauses


def configuration_devis_contenu(devis):
    """NTCPQ20 — Représentation JSON-safe de la configuration d'un devis.

    Uniquement des données de configuration (ligne, désignation, quantité,
    P.U., remise) — JAMAIS de prix d'achat ni de marge."""
    return {
        'lignes': [{
            'ligne_id': li.id,
            'produit_id': li.produit_id,
            'designation': li.designation,
            'quantite': str(li.quantite) if li.quantite is not None else None,
            'prix_unitaire': (str(li.prix_unitaire)
                              if li.prix_unitaire is not None else None),
            'remise': str(li.remise) if li.remise is not None else None,
        } for li in devis.lignes.all().order_by('ordre', 'id')],
    }


def capturer_configuration_devis(devis, *, user=None):
    """NTCPQ20 — Enregistre un instantané de configuration si le devis est
    BROUILLON et que la configuration a RÉELLEMENT changé.

    No-op (renvoie ``None``) hors brouillon ou quand le contenu est identique
    au dernier instantané — un simple re-save ne pollue pas l'historique.
    Ne lève jamais : l'historique ne doit jamais bloquer une écriture."""
    from apps.ventes.models import ConfigurationDevisSnapshot, Devis

    if devis is None or devis.pk is None:
        return None
    if devis.statut != Devis.Statut.BROUILLON:
        return None
    try:
        contenu = configuration_devis_contenu(devis)
        dernier = ConfigurationDevisSnapshot.objects.filter(
            devis_id=devis.pk).order_by('-date_creation', '-id').first()
        if dernier is not None and dernier.contenu == contenu:
            return None
        return ConfigurationDevisSnapshot.objects.create(
            company=devis.company, devis=devis, contenu=contenu, auteur=user)
    except Exception:  # noqa: BLE001 — l'historique n'est jamais bloquant
        logger.exception(
            'NTCPQ20 : instantané de configuration ignoré (devis %s)',
            devis.pk)
        return None


def diff_configurations_devis(snapshot_a, snapshot_b):
    """NTCPQ20 — Diff des LIGNES entre deux instantanés de configuration.

    Renvoie ``{ajoutees, retirees, modifiees}`` : ``modifiees`` porte, pour
    chaque ligne présente des deux côtés, les champs qui ont changé
    (``{champ: [avant, apres]}``)."""
    def _index(snap):
        contenu = (snap or {}).get('lignes') or []
        return {li.get('ligne_id'): li for li in contenu}

    avant = _index(getattr(snapshot_a, 'contenu', snapshot_a))
    apres = _index(getattr(snapshot_b, 'contenu', snapshot_b))
    modifiees = []
    for ligne_id, ligne in apres.items():
        precedente = avant.get(ligne_id)
        if precedente is None:
            continue
        champs = {
            champ: [precedente.get(champ), ligne.get(champ)]
            for champ in ('designation', 'quantite', 'prix_unitaire', 'remise')
            if precedente.get(champ) != ligne.get(champ)}
        if champs:
            modifiees.append({'ligne_id': ligne_id, 'champs': champs})
    return {
        'ajoutees': [li for lid, li in apres.items() if lid not in avant],
        'retirees': [li for lid, li in avant.items() if lid not in apres],
        'modifiees': modifiees,
    }


def renouveler_devis(devis, *, user=None):
    """NTCPQ13 — Renouvelle un devis déjà ACCEPTÉ (ou expiré/clos).

    Crée un NOUVEAU ``Devis`` en ``brouillon`` reprenant les lignes actuelles
    avec les prix COURANTS recalculés (``prix_applicable`` — jamais une simple
    copie figée), lié au devis source par ``devis_origine`` (racine de chaîne)
    et portant ``numero_renouvellement`` = source + 1.

    DISTINCT de ``reviser`` (T10) : celui-ci corrige un devis non encore
    accepté et supersède l'original ; ``renouveler`` laisse le devis source
    strictement intact (statut, chaîne BC/Facture, historique).

    Lève ``ValidationError`` si le devis n'est pas dans un état renouvelable.
    Renvoie le nouveau devis."""
    from rest_framework.exceptions import ValidationError
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from apps.ventes.utils.company_settings import create_numbered

    RENOUVELABLES = (Devis.Statut.ACCEPTE, Devis.Statut.EXPIRE)
    if devis.statut not in RENOUVELABLES:
        raise ValidationError({'statut': (
            'Seul un devis accepté ou expiré peut être renouvelé '
            '(un devis en cours se corrige avec « réviser »).')})

    company = devis.company
    racine = devis.devis_origine or devis
    cree = {}

    def _save(ref):
        cree['obj'] = Devis.objects.create(
            company=company, reference=ref, client=devis.client,
            lead=devis.lead, statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva, remise_globale=devis.remise_globale,
            note=devis.note, mode_installation=devis.mode_installation,
            # QJR117 / CS6 — le renouvellement RE-TARIFE les lignes au
            # catalogue courant : garder l'étude chiffrée aux ANCIENS prix
            # servait au client un devis dont les lignes disent un prix et
            # dont le payback en dit un autre. La CONFIGURATION reste.
            etude_params=etude_params_pour_copie(devis.etude_params),
            prix_cible_kwc=devis.prix_cible_kwc,
            echeancier=devis.echeancier, devise=devis.devise,
            taux_change=devis.taux_change, entite=devis.entite,
            created_by=user, devis_origine=racine,
            numero_renouvellement=(devis.numero_renouvellement or 0) + 1)
        return cree['obj']

    create_numbered(Devis, company, 'devis', _save)
    nouveau = cree['obj']

    def _prix_courant(ligne):
        """Le prix que CE renouvellement pose sur la ligne clonée.

        QJR84 / D12 — un prix TAPÉ par le commercial n'est pas re-tarifé,
        même par un renouvellement : c'est un prix NÉGOCIÉ, pas une valeur de
        catalogue périmée. Sans cette garde, le marqueur ``prix_manuel``
        cloné protégerait une valeur qui vient d'être réécrite.
        """
        if ligne.produit_id is None or ligne.prix_manuel:
            return ligne.prix_unitaire
        try:
            return prix_applicable(
                produit=ligne.produit, client=devis.client,
                quantite=ligne.quantite)['prix']
        except Exception:  # noqa: BLE001 — repli sur le prix historique
            logger.exception(
                'NTCPQ13 : prix courant indisponible (ligne %s)', ligne.pk)
            return ligne.prix_unitaire

    # QJR116 — le renouvellement clone par le MÊME cloneur unique que le
    # duplicata et la gamme sœur (``domain/lignes.cloner_lignes``) ; il n'y
    # ajoute que sa re-tarification. C'est là que la liste maintenue à la
    # main avait le plus divergé : elle clonait ``optionnelle`` sans
    # ``variante``, et aucune des trois ne clonait ``lot``.
    cloner_lignes(devis, nouveau, prix_unitaire=_prix_courant)
    # QJR117 — les études du RENOUVELLEMENT sont recalculées sur ses lignes
    # RE-TARIFÉES (force : le dimensionnement se court-circuite sinon sur
    # empreinte concordante, et l'édition de ligne ne rattrape pas).
    rafraichir_etudes_du_devis(nouveau, force=True)

    activity.log_devis_note(
        nouveau, user,
        f'Renouvellement n° {nouveau.numero_renouvellement} du devis '
        f'{devis.reference} — prix catalogue actuels appliqués.')
    activity.log_devis_note(
        devis, user,
        f'Renouvelé par le devis {nouveau.reference} '
        f'(renouvellement n° {nouveau.numero_renouvellement}).')
    return nouveau


def mark_devis_sent(*, devis, user=None):
    """U4 — flip a Devis to « envoyé » through the ONE status-change path.

    Called when a quote is shared with the client (e.g. the lead WhatsApp
    action builds a wa.me link). It is the single place that moves a quote
    document from « brouillon » to « envoyé » outside the viewset's own
    perform_update, so rule #4 status semantics + the chatter log are
    preserved (no raw ``.statut =`` write elsewhere).

    Behaviour:

    * a ``brouillon`` devis flips to ``envoye``, stamps ``date_envoi`` once,
      writes the « envoyé » chatter entry, and emits the ``devis_sent`` domain
      event so ``crm`` advances the lead funnel to QUOTE_SENT — without
      ventes importing crm directly (mirror of ``accept_devis``) ;
    * idempotent — an already-``envoye`` devis is returned unchanged (no second
      stamp, no second event, no duplicate chatter line) ;
    * NEVER regresses a further-along devis: ``accepte`` / ``refuse`` /
      ``expire`` are left exactly as-is (returned untouched).

    Returns the (possibly unchanged) Devis. Tenant scoping is the caller's
    responsibility — the devis is always passed already company-resolved.
    """
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_sent

    # Already sent (or beyond): never re-stamp, never downgrade. Only a live
    # brouillon advances — accepté/refusé/expiré are terminal-or-further and
    # must stay put (the guard the test pins).
    if devis.statut != Devis.Statut.BROUILLON:
        return devis

    # NTCPQ7 — bloque l'envoi tant qu'une étape d'approbation de remise reste
    # en attente (matrice à paliers, remplace/étend le seuil unique T17).
    verifier_devis_envoyable(devis)

    # NTCPQ11 — fige les clauses/CGV dynamiques AVANT le basculement (snapshot
    # write-once ; jamais recalculé après envoi).
    figer_clauses_devis(devis)

    ancien = devis.statut
    devis.statut = Devis.Statut.ENVOYE
    devis.date_envoi = timezone.now()
    devis.save(update_fields=['statut', 'date_envoi'])
    # QX23be — fige la marge interne au moment de l'envoi (manager-only).
    refresh_marge_snapshot(devis)
    activity.log_devis_sent(devis, user)
    devis_sent.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)
    return devis


# ── QJR76 : la garde d'envoi et le courriel fournisseur ─────────────────────
# `verifier_devis_envoyable` garde `mark_devis_sent` (plus haut) — ce module
# l'importait par un pont. `log_supplier_email` est l'autre envoi de document
# du domaine : il rejoint les e-mails d'acceptation et les OTP.
def log_supplier_email(
        *, company, to_email, sujet, corps, attachment=None,
        attachment_name=None, reference='', user=None):
    """QS3 — Envoie un email FOURNISSEUR (PDF joint) et le consigne dans EmailLog.

    Point d'entrée cross-app pour ``stock`` (qui n'importe pas ``ventes.models``
    ni ``ventes.email_service``). Le fil EmailLog n'a pas de FK fournisseur : on
    consigne company + destinataire + référence (client/devis/facture restent
    nuls). NO-OP réseau sans clé configurée (backend console) — l'entrée est tout
    de même écrite. Renvoie ``(ok, log)``."""
    from apps.ventes.models import EmailLog
    from apps.ventes.email_service import _send, _from_email
    dest = (to_email or '').strip()
    log = EmailLog(
        company=company,
        direction=EmailLog.Direction.SORTANT,
        to_email=dest[:254], from_email=_from_email(),
        sujet=(sujet or '')[:300], corps=corps or '',
        reference=(reference or '')[:80],
        piece_jointe=(attachment_name or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return False, log
    ok, err = _send(dest, sujet, corps, attachment, attachment_name)
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return ok, log


def verifier_devis_envoyable(devis):
    """NTCPQ7 — lève ``ValidationError`` si une étape d'approbation de remise
    est encore ``en_attente`` (blocage envoi/génération PDF).

    Lecture cross-app cpq via import LOCAL (aucun cycle au niveau module).
    Aucune étape en attente ⇒ ne lève rien (comportement inchangé)."""
    from rest_framework.exceptions import ValidationError
    from apps.cpq.selectors import premiere_etape_en_attente
    etape = premiere_etape_en_attente(devis)
    if etape is not None:
        raise ValidationError({'statut': (
            f"Approbation de remise en attente (étape {etape.niveau}) : "
            "l'envoi est bloqué tant qu'elle n'est pas approuvée.")})


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (voir la docstring) : ils s'exécutent après toutes
# les définitions de ce module, donc l'ordre de chargement ne peut jamais faire
# lire un module à moitié construit. Chacun vise le module qui PORTE le corps —
# jamais la façade, dont les ré-exports s'exécutent dans l'ordre des tâches.
from apps.ventes.domain.etudes import (  # noqa: E402,F401
    etude_params_pour_copie,
    rafraichir_etudes_du_devis,
    refresh_marge_snapshot,
)
# QJR84 — l'écrivain unique des lignes (le seul constructeur de LigneDevis).
from apps.ventes.domain.lignes import cloner_lignes  # noqa: E402,F401
from apps.ventes.domain.tarification import prix_applicable  # noqa: E402,F401
