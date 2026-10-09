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
# QJR146 (i) — comparaison d'OTP à temps constant (``compare_digest``).
import secrets

logger = logging.getLogger("apps.ventes.services")


class AcceptError(Exception):
    """Raised when a devis cannot be accepted (wrong status / bad option)."""

    def __init__(self, message, conflict=False, code=None):
        super().__init__(message)
        self.message = message
        self.conflict = conflict  # True → 409, False → 400
        # ADEV11 — code machine du 409 (liste FERMÉE ``codes_409`` du contrat
        # ``proposal_accept.json``) ; ``None`` = refus historique sans code.
        self.code = code


#: ADEV13 — message NEUTRE du 409 ``validation_requise`` (contrat
#: ``proposal_accept.json``, ``reponses_409.validation_requise`` — ADEV2) :
#: aucun motif interne (crédit, avertissement) n'est exposé au client.
VALIDATION_REQUISE_REFUS = (
    'Cette proposition attend une validation interne avant de pouvoir être '
    'signée.')


class AcceptationBloquee(AcceptError):
    """ADEV13 (C-ADEV-005) — acceptation refusée par un blocage crédit
    (XFAC28) ou un avertissement de vente bloquant (ZSAL9).

    Sous-classe d'``AcceptError`` : la signature publique et le portail
    (qui attrapent ``AcceptError``) répondent donc 409 avec le message NEUTRE
    et ``code = "validation_requise"`` ; la vue interne l'attrape AVANT et
    garde son 403 détaillé (``motif``, ``nature`` = ``credit_hold`` |
    ``sale_warning``)."""

    def __init__(self, nature, motif):
        super().__init__(VALIDATION_REQUISE_REFUS, conflict=True,
                         code='validation_requise')
        self.nature = nature
        self.motif = motif


def peut_passer_outre(user):
    """ADEV14 (C-ADEV-006) — seul un Administrateur ou un Responsable (palier
    ``menu_tier`` faisant autorité, dérivé du rôle) peut passer outre un
    blocage crédit ou un avertissement de vente bloquant. Porter
    ``ventes_valider`` (rôle « Commercial ») ne suffit PAS. Sans utilisateur
    (signature publique) : jamais."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return getattr(user, 'menu_tier', None) in ('admin', 'responsable')


def _garde_blocages_acceptation(devis, *, user, override_credit=False,
                                override_avertissement=False):
    """ADEV13 — LA garde unique des trois portes d'acceptation (interne,
    signature publique, portail) : blocage crédit dur (XFAC28) puis
    avertissement de vente bloquant (ZSAL9). Lève ``AcceptationBloquee`` ;
    un override n'est honoré que s'il est demandé (les portes client ne le
    demandent jamais) ET que ``peut_passer_outre(user)`` (ADEV14) — un
    drapeau posé par un Commercial est ignoré, le refus tombe."""
    from apps.ventes.domain.recouvrement import (
        CreditHoldError, SaleWarningError, verifier_credit_hold,
        verifier_sale_warnings,
    )
    autorise = peut_passer_outre(user)
    override_credit = bool(override_credit) and autorise
    override_avertissement = bool(override_avertissement) and autorise
    if devis.client_id is not None:
        try:
            verifier_credit_hold(
                devis.client, override=bool(override_credit), user=user,
                chatter_target=devis, contexte='acceptation devis')
        except CreditHoldError as exc:
            raise AcceptationBloquee('credit_hold', exc.motif) from exc
    try:
        verifier_sale_warnings(
            devis, override=bool(override_avertissement), user=user,
            chatter_target=devis)
    except SaleWarningError as exc:
        raise AcceptationBloquee('sale_warning', exc.motif) from exc


#: ADEV11 — message du 409 ``brouillon`` (contrat ``proposal_accept.json``,
#: ``reponses_409.brouillon`` — ADEV2), repris tel quel ; partagé par la
#: garde du service et celle du résolveur public (``public/noyau.py``).
BROUILLON_REFUS = (
    "Cette proposition n'a pas encore été envoyée : elle ne peut pas être "
    'signée.')

#: ADEV52 — le refus 409 ``expiree`` du contrat ``proposal_accept.json``.
EXPIREE_REFUS = ('Cette offre a expiré : contactez votre conseiller pour une '
                 'nouvelle proposition.')


def _acceptation_par_le_client(user):
    """ADEV52 — l'acceptation vient-elle du CLIENT (lien public : ``user``
    absent ; portail client : utilisateur de portée « portail client ») ?
    L'acceptation INTERNE (un commercial) reste libre d'enregistrer une
    acceptation tardive."""
    if user is None:
        return True
    from authentication.models import CustomUser
    return (getattr(user, 'portee', None)
            == CustomUser.PORTEE_PORTAIL_CLIENT)


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
    from apps.ventes.models import LigneDevis
    from apps.ventes import activity

    with transaction.atomic():
        try:
            ligne = (LigneDevis.objects
                     .select_for_update()
                     .select_related('devis')
                     .get(pk=ligne_id, devis=devis))
        except LigneDevis.DoesNotExist:
            return None

        # Devis figé (accepté/refusé/expiré) ou remplacé : les options ne
        # sont plus activables (le contenu est verrouillé — règle #4).
        # QJR516 — le prédicat UNIQUE (geste OPTIONS), message CONSERVÉ.
        from apps.ventes.domain.modifiabilite import OPTIONS, est_modifiable
        if not est_modifiable(ligne.devis, OPTIONS):
            raise AcceptError(
                'Ce devis est figé — ses options ne sont plus modifiables.',
                conflict=True)

        # Idempotent : ligne non optionnelle (jamais optionnelle, ou déjà
        # activée) → no-op silencieux, aucun second chatter.
        if not ligne.optionnelle:
            return ligne

        # ADEV19 (C-ADEV-012) — l'activation par le client est un GESTE DE
        # LIGNE comme un autre : état vu par le client capturé AVANT
        # l'écriture (instantané « avant correction », envoyé seulement).
        from apps.ventes.domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis,
        )
        avant_geste = debut_de_geste_devis(ligne.devis, user)

        ligne.optionnelle = False
        ligne.save(update_fields=['optionnelle'])

    # ADEV19 — après la transaction (best-effort, comme ``LigneDevisViewSet``) :
    # rafraîchissement (MODE_RAFRAICHIR : études, kWc, marge), instantané du
    # geste, trace « corrigé après envoi — option client » et AVANCE du jeton
    # d'édition (``updated_at``) — un écran interne ouvert avant l'activation
    # reçoit alors 409 ``devis_modifie`` au lieu d'effacer le choix du client.
    _geste_option_client(devis, user=user, avant=avant_geste,
                         fin_de_geste=fin_de_geste_devis)

    # Chatter (hors transaction — miroir de accept_devis).
    try:
        activity.log_devis_note(
            devis, user,
            f'Option activée par le client : « {ligne.designation} » '
            '— désormais incluse dans le total.')
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass
    return ligne


def _geste_option_client(devis, *, user, avant, fin_de_geste):
    """ADEV19 — la moitié « après écriture » du geste d'option client, dans
    l'ordre du jumeau interne (``views/ligne_devis.py``) : rafraîchir, puis
    instantané, puis trace d'envoi, puis jeton. Chaque étape est best-effort :
    l'option est déjà activée, rien ne doit l'annuler."""
    try:
        from apps.ventes.domain.pipeline import (
            MODE_RAFRAICHIR, ORIGINE_ECRAN, IntentionDevis, appliquer,
        )
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR,
            company=devis.company))
    except Exception:  # noqa: BLE001 — best-effort
        logger.exception('ADEV19 : rafraîchissement ignoré (devis %s)',
                         devis.pk)
    try:
        from apps.ventes.domain.historique_config import instantane_de_geste
        instantane_de_geste(devis, user=user)
    except Exception:  # noqa: BLE001 — best-effort
        logger.exception('ADEV19 : instantané ignoré (devis %s)', devis.pk)
    fin_de_geste(devis, user, avant=avant, objet='option client')
    from apps.ventes.domain.verrou_devis import toucher
    toucher(devis)


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


#: ADEV20 (C-ADEV-021) — message du 409 ``aucun_canal`` (contrat
#: ``proposal_accept.json``, bloc ``otp.reponse_409`` — ADEV2), rendu par les
#: deux demandes d'OTP quand AUCUN code n'est réellement parti.
OTP_AUCUN_CANAL = "Aucun moyen d'envoyer le code : contactez votre conseiller."


def canal_otp_disponible(client):
    """ADEV20 — vrai si un code peut réellement partir vers ``client``.

    Le seul canal câblé est l'e-mail : WhatsApp est un STUB (QX10,
    ``_send_otp_whatsapp`` rend toujours False tant qu'aucun BSP n'est
    branché). Sert à refuser ``otp_lecture`` au ``share-link`` d'un client
    injoignable — sinon le lien serait illisible pour toujours."""
    return bool((getattr(client, 'email', '') or '').strip())


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
        # ADEV20 — aucun code n'est parti : aucun code ne reste en cache, et
        # la vue répond 409 ``aucun_canal`` au lieu de « Code envoyé. ».
        cache.delete(cache_key)
        return OTP_AUCUN_CANAL
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
    # QJR146 (i) — COMPARAISON À TEMPS CONSTANT. ``!=`` sur des chaînes
    # sort au premier caractère différent : le temps de réponse fuit la
    # longueur du préfixe correct. Le plafond de tentatives (QX10) borne
    # le brute-force, il ne ferme pas ce canal-là.
    # Passe Fable finale (30/08/2026) — comparer en BYTES :
    # `compare_digest(str, str)` leve TypeError sur tout caractere non-ASCII
    # (un U+200B colle depuis un email survivait a .strip()) — hier un 400
    # << code incorrect >>, sinon un 500 public. En bytes, tout octet compare.
    if not secrets.compare_digest(str(stored).encode('utf-8'),
                                  otp_code.strip().encode('utf-8')):
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
        # ADEV20 — même règle que l'OTP de signature (jumeau).
        cache.delete(_otp_lecture_cache_key(link.token))
        return OTP_AUCUN_CANAL
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
    # QJR146 (i) — COMPARAISON À TEMPS CONSTANT. ``!=`` sur des chaînes
    # sort au premier caractère différent : le temps de réponse fuit la
    # longueur du préfixe correct. Le plafond de tentatives (QX10) borne
    # le brute-force, il ne ferme pas ce canal-là.
    # Passe Fable finale (30/08/2026) — comparer en BYTES :
    # `compare_digest(str, str)` leve TypeError sur tout caractere non-ASCII
    # (un U+200B colle depuis un email survivait a .strip()) — hier un 400
    # << code incorrect >>, sinon un 500 public. En bytes, tout octet compare.
    if not secrets.compare_digest(str(stored).encode('utf-8'),
                                  otp_code.strip().encode('utf-8')):
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
    jamais d'une marque codée en dur.

    QJR146 (i) — DESTINATAIRE VIDE ⇒ ``False``, SANS APPELER ``send_mail``.
    Un email absent partait jusqu'au backend d'envoi, qui décide seul de lever
    ou non : sur le backend console (développement) et sur certains backends
    tolérants, ``send_mail(..., [''])`` NE lève pas et cette fonction rendait
    ``True`` — l'appelant croyait alors le code envoyé et l'écran l'annonçait
    au client. L'absence de destinataire est un fait connu AVANT l'appel : on
    le dit, une fois, ici.
    """
    if not str(email or '').strip():
        logger.warning('QJ11: email OTP non envoyé (devis %s) — '
                       'aucune adresse destinataire', devis_ref)
        return False
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
                         on_behalf_of='', lignes=None, entreprise=None):
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
            # CIQ319 — identité de l'entreprise signataire (vide hors C&I).
            **_champs_signature_entreprise(entreprise),
        )
        logger.info(
            'QJ10: DevisSignature créée pour devis %s (hash=%s…)',
            devis.reference, content_hash[:16])
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('QJ10: échec DevisSignature pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _champs_signature_entreprise(entreprise):
    """CIQ319 — ``{raison_sociale, signataire_qualite, ice_declare}`` du
    bloc ``entreprise`` (contrat ``acceptation_entreprise.json``), bornés aux
    longueurs du modèle ; ``{}`` sans bloc."""
    if not isinstance(entreprise, dict):
        return {}
    return {
        'raison_sociale': str(entreprise.get('raison_sociale') or '')
        .strip()[:200],
        'signataire_qualite': str(entreprise.get('signataire_qualite') or '')
        .strip()[:150],
        'ice_declare': str(entreprise.get('ice') or '').strip()[:30],
    }


#: CIQ319 — modes dont l'acceptation EN LIGNE exige l'identité d'entreprise.
MODES_ACCEPTATION_ENTREPRISE = ('commercial', 'industriel')
#: Champs du bloc ``entreprise`` (contrat ``acceptation_entreprise.json``) et
#: le message 400 qui NOMME chacun.
CHAMPS_ENTREPRISE = (
    ('raison_sociale',
     "La raison sociale de l'entreprise est requise pour accepter ce devis."),
    ('signataire_qualite',
     'La qualité du signataire est requise pour accepter ce devis.'),
    ('ice', "L'ICE de l'entreprise est requis pour accepter ce devis."),
)


class EntrepriseInvalide(Exception):
    """CIQ319 — bloc ``entreprise`` refusé : ``detail`` + ``champ`` nommé
    (``entreprise.<cle>``), rendus en 400 par les vues."""

    def __init__(self, detail, champ):
        super().__init__(detail)
        self.detail = detail
        self.champ = champ


def exige_identite_entreprise(devis):
    """Vrai pour un devis commercial / industriel (règle sur le MODE)."""
    mode = str(getattr(devis, 'mode_installation', '') or '').strip().lower()
    return mode in MODES_ACCEPTATION_ENTREPRISE


def lire_entreprise_acceptation(devis, brut, *, obligatoire):
    """CIQ319/CIQ323 — le bloc ``entreprise`` d'un corps d'acceptation,
    validé, ou ``None``.

    * hors commercial / industriel : IGNORÉ (``None``, ni erreur ni écriture) ;
    * ``obligatoire`` (lien public, portail) : les trois champs requis ;
    * ICE validé par ``parametres.tax_id_validators.validate_ice_ma`` (la
      règle EXISTANTE, jamais une seconde).

    Lève :class:`EntrepriseInvalide` (détail + champ nommé)."""
    if not exige_identite_entreprise(devis):
        return None
    if brut in (None, ''):
        brut = {}
    if not isinstance(brut, dict):
        raise EntrepriseInvalide(
            'Le bloc entreprise doit être un objet.', 'entreprise')
    valeurs = {}
    for cle, message in CHAMPS_ENTREPRISE:
        valeur = brut.get(cle)
        if valeur is not None and not isinstance(valeur, (str, int)):
            raise EntrepriseInvalide(
                f'entreprise.{cle} : texte attendu.', f'entreprise.{cle}')
        valeur = str(valeur or '').strip()
        if obligatoire and not valeur:
            raise EntrepriseInvalide(message, f'entreprise.{cle}')
        valeurs[cle] = valeur
    if valeurs['ice']:
        from apps.parametres.tax_id_validators import validate_ice_ma
        verdict = validate_ice_ma(valeurs['ice'])
        if not verdict.get('valide'):
            raise EntrepriseInvalide(verdict.get('message') or 'ICE invalide.',
                                     'entreprise.ice')
    if not any(valeurs.values()):
        return None
    return valeurs


def signature_entreprise(devis):
    """CIQ319 — le bloc de RENDU ``signature_entreprise`` (contrat
    ``acceptation_entreprise.json``) : ``{raison_sociale, signataire_nom,
    signataire_qualite, ice, date}`` d'un devis C&I accepté en ligne, sinon
    ``None``. Lecture seule."""
    if not exige_identite_entreprise(devis):
        return None
    try:
        sig = devis.signature
    except Exception:  # noqa: BLE001 — RelatedObjectDoesNotExist
        return None
    if sig is None or not (sig.raison_sociale or sig.signataire_qualite
                           or sig.ice_declare):
        return None
    return {
        'raison_sociale': sig.raison_sociale,
        'signataire_nom': sig.signataire_nom,
        'signataire_qualite': sig.signataire_qualite,
        'ice': sig.ice_declare,
        'date': sig.signed_at.date().isoformat() if sig.signed_at else None,
    }


def divergence_ice(devis, ice_declare):
    """CIQ319 — vrai quand le Client porte DÉJÀ un ICE différent de celui
    déclaré à l'acceptation (jamais écrasé : drapeau pour le vendeur)."""
    client = getattr(devis, 'client', None)
    ice_client = ''.join(str(getattr(client, 'ice', '') or '').split())
    declare = ''.join(str(ice_declare or '').split())
    return bool(ice_client and declare and ice_client != declare)


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


SUFFIXE_EXEMPLAIRE_SIGNE = '__signe'


def _copier_exemplaire_signe(cle_rendu, *, devis):
    """QJR670 suivi — fige l'exemplaire signé sous SA PROPRE clé MinIO.

    ``generate_premium_devis_pdf`` écrit sur une clé déterministe
    (``devis/<co>/<ref>.pdf``) que tout re-rendu interne réécrit : stocker
    cette clé comme ``signed_pdf_key`` laissait le document signé être écrasé
    par le rendu suivant. On copie donc les octets sous ``…__signe.pdf`` —
    suffixe qu'aucune clé de rendu (``builder._pdf_key``) ne produit.
    Échec de copie (stockage indisponible) ⇒ on garde la clé de rendu,
    comportement d'avant ce correctif, plutôt que de ne rien lier.
    """
    if not cle_rendu:
        return cle_rendu
    base = cle_rendu[:-4] if cle_rendu.lower().endswith('.pdf') else cle_rendu
    cle_signee = f'{base}{SUFFIXE_EXEMPLAIRE_SIGNE}.pdf'
    try:
        from apps.ventes.utils.pdf import _upload_pdf, download_pdf
        _upload_pdf(download_pdf(cle_rendu), cle_signee)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'QJR670: copie de l\'exemplaire signé impossible (devis %s) : %s',
            getattr(devis, 'reference', '?'), exc)
        return cle_rendu
    return cle_signee


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
        key = _copier_exemplaire_signe(key, devis=devis)
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
    de la SOCIÉTÉ émettrice (AFAC59 : ``company_identity``) si renseigné.
    Chaîne VIDE quand rien n'est
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
        # AFAC59 (C-AFAC-051) — RIB du profil de la société émettrice.
        rib = ''
        if getattr(devis, 'company', None) is not None:
            from apps.parametres.selectors import company_identity
            rib = (company_identity(devis.company).get('rib') or '').strip()
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
                 idempotent_reaccept=True, rejouer_aval=False,
                 entreprise=None, override_credit=False,
                 override_avertissement=False):
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

        # QJR520 — une version REMPLACÉE (révisée, archivée) ne se signe plus :
        # sans cette garde, signer le lien public de v1 après « Réviser »
        # acceptait v1 ET effondrait v2 (sa « sœur ») en REFUSE — plus aucune
        # version active, aucun BC. Rien n'est écrit (règle #4).
        # ADEV7 — la règle vit dans ``modifiabilite.geste_cycle_permis``
        # (partagée par refuser / envoyer / relancer).
        from apps.ventes.domain.modifiabilite import (
            ACCEPTER, geste_cycle_permis)
        permis, message = geste_cycle_permis(devis, ACCEPTER)
        if not permis:
            raise AcceptError(message, conflict=True)

        # ADEV11 (C-ADEV-004) — la signature PUBLIQUE (``user=None`` : le
        # jeton authentifie, aucun compte) ne peut jamais accepter un
        # BROUILLON, même si une vue l'appelle sans passer par
        # ``_resolve_proposal_link`` : un devis jamais envoyé n'a pas été
        # présenté au client. L'acceptation INTERNE d'un brouillon (``user``
        # posé) reste régie par ERR33 ci-dessous (ADEV12, GATED D-ADEV-2).
        if user is None and devis.statut == Devis.Statut.BROUILLON:
            raise AcceptError(BROUILLON_REFUS, conflict=True, code='brouillon')

        # ADEV52 (C-ADEV-019) — UNE règle d'expiration (``utils/expiry``, fin
        # du dernier jour à l'heure du Maroc) appliquée au CLIENT (lien public
        # et portail) : 409 ``expiree``, rien n'est écrit (règle #4 : aucun
        # statut ne bouge). L'acceptation interne garde son comportement.
        if _acceptation_par_le_client(user):
            from apps.ventes.utils.expiry import is_expired
            if is_expired(devis):
                raise AcceptError(EXPIREE_REFUS, conflict=True, code='expiree')

        # ERR33 — only a live devis (brouillon / envoyé) can be accepted.
        if devis.statut not in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            raise AcceptError(
                'Seul un devis en cours (brouillon ou envoyé) peut être '
                f'accepté ; statut actuel : « {devis.get_statut_display()} ».',
                conflict=True)

        # ADEV13 (C-ADEV-005) — blocage crédit et avertissement de vente
        # bloquant : UNE garde, ici, pour les trois portes (vue interne,
        # signature publique, portail client). Auparavant seule la vue
        # interne la posait — le lien public et le portail acceptaient un
        # client bloqué (chantier créé). Rien n'est écrit sur refus.
        _garde_blocages_acceptation(
            devis, user=user, override_credit=override_credit,
            override_avertissement=override_avertissement)

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
            # QJR421 — POINT DE SAUVEGARDE. Cf. le commentaire du bloc
            # ``_persist_attribution`` plus bas : sans ``atomic()`` imbriqué,
            # une erreur BASE levée ici marquerait la transaction entière comme
            # non validable, et l'``except`` ci-dessous n'absorberait qu'une
            # apparence d'incident. UN savepoint pour tout le bloc (jamais un
            # par ligne de devis).
            with transaction.atomic():
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
        # ADOC131 (D-ADOC-4) — le lien public du devis reste vivant pendant
        # le chantier (jusqu'à la réception + 90 jours) : même transaction.
        from apps.ventes.domain.suivi import ouvrir_suivi
        ouvrir_suivi(devis)

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
            # QJR421 — POINT DE SAUVEGARDE (même raison que ci-dessous).
            with transaction.atomic():
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
            # CIQ319 — raison sociale, qualité et ICE du signataire C&I,
            # enregistrés AVEC la signature (aucun statut nouveau, règle #4).
            entreprise=entreprise,
        )
        # CIQ319 (complément) — l'ICE / la raison sociale déclarés remontent
        # au Client qui n'en a pas (service CRM du contrat CIQ8) ; un ICE
        # différent déjà présent n'est jamais écrasé (``divergence_ice``).
        # Point de sauvegarde : jamais une acceptation cassée pour ça.
        if isinstance(entreprise, dict) and devis.client_id:
            try:
                with transaction.atomic():
                    from apps.crm.services import (
                        completer_client_depuis_acceptation,
                    )
                    completer_client_depuis_acceptation(
                        devis.client_id, devis.company,
                        raison_sociale=entreprise.get('raison_sociale'),
                        ice=entreprise.get('ice'))
            except Exception:  # noqa: BLE001 — best-effort, journalisé
                logger.exception(
                    'CIQ319 : identité entreprise non remontée au client '
                    '(devis %s)', getattr(devis, 'reference', '?'))
        # QJ9 — Attribution first-touch : copie UTM/fbclid du lead vers
        # etude_params du devis pour que l'attribution reste lossless même si
        # le lead est fusionné.
        try:
            # ── QJR421 / QJR4-04 — UN POINT DE SAUVEGARDE PAR ÉCRITURE ──────
            #
            # CE QUI ÉTAIT FAUX. Ce ``try/except`` vivait NU à l'intérieur du
            # ``with transaction.atomic()`` ouvert plus haut. Or en base, une
            # requête en échec marque la transaction ENTIÈRE comme non
            # validable : l'``except`` CROYAIT absorber l'incident, mais tout
            # ce qui suivait — l'effondrement des sœurs, la publication de
            # ``devis_accepted``, et le passage du devis à l'état signé
            # lui-même — échouait au commit. Un « best-effort » qui fait tomber
            # l'essentiel n'est pas du best-effort.
            #
            # LA RÈGLE. Chaque écriture best-effort de cette transaction prend
            # son PROPRE ``atomic()`` imbriqué : la base ouvre un point de
            # sauvegarde, l'échec y revient, et la transaction principale reste
            # validable. La journalisation ne change pas (on n'avale jamais
            # l'incident en silence) et le coût est CONSTANT — un savepoint par
            # bloc best-effort, jamais un par ligne de devis.
            with transaction.atomic():
                _persist_attribution(devis=devis)
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'QJ9: _persist_attribution échoué pour devis %s : %s',
                getattr(devis, 'reference', '?'), exc)

        # QJR560 / D-QJR5-11 — V2 d'un devis signé : BC et factures de la V1
        # passent à la V2, seul l'écart est régularisé. Point de sauvegarde :
        # un incident ici n'annule jamais la signature du client (journalisé).
        try:
            with transaction.atomic():
                rattacher_aval_financier_revision(devis, user=user)
        except Exception:  # noqa: BLE001 — best-effort, journalisé
            logger.exception(
                'QJR560 : aval financier de révision non rattaché (devis %s)',
                getattr(devis, 'reference', '?'))

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


# ── Décision fondateur (Reda, 08/10/2026) — DÉS-ACCEPTATION ─────────────────
#
# Un lead qui SORT de « Signé » par une action utilisateur (changement d'étape
# unitaire ou en masse) dés-accepte son devis : le devis repasse « envoyé »,
# les tampons d'acceptation sont effacés, les variantes sœurs refusées PAR
# cette acceptation reviennent, et ce que l'acceptation a créé
# AUTOMATIQUEMENT (chantier, contrat SAV, commission, parrainage) est défait
# par les abonnés de ``devis_acceptation_annulee``. Si quelque chose de RÉEL
# existe en aval (facture, bon de commande, chantier avancé, contrat SAV
# facturé…), RIEN n'est écrit et la raison est rendue en français.
#
# La preuve de signature (``DevisSignature``, PDF scellé) n'est JAMAIS
# supprimée : une note de chatter dit que l'acceptation a été annulée.

#: Motif posé par l'effondrement des sœurs (``_effondrer_soeurs_et_publier``)
#: — c'est le MARQUEUR qui prouve qu'une sœur a été refusée par l'acceptation
#: (avec ``date_refus`` == date d'acceptation et le même groupe).
MOTIF_VARIANTE_NON_RETENUE = 'variante non retenue'


class AnnulationAcceptationBloquee(Exception):
    """L'acceptation ne peut pas être annulée : quelque chose de réel existe
    en aval. ``message`` nomme exactement ce qui bloque (français)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def raison_blocage_annulation_acceptation(devis):
    """Rend la raison (français) qui EMPÊCHE d'annuler l'acceptation de
    ``devis``, ou ``None`` si l'annulation est permise. Lecture seule.

    Bloquent : une facture non annulée liée au devis (directement, par son bon
    de commande ou par une facture consolidée — brouillon comprise : elle
    n'est jamais créée par l'acceptation), un bon de commande non annulé, un
    dossier 82-21 sorti de « En constitution », puis ce que disent les
    sélecteurs des apps propriétaires (chantier avancé, contrat SAV engagé)."""
    from django.db.models import Q
    from apps.ventes.models import (
        BonCommande, Facture, RegulatoryDossier,
    )

    company_id = devis.company_id
    facture = (Facture.objects
               .filter(company_id=company_id)
               .filter(Q(devis_id=devis.pk)
                       | Q(bon_commande__devis_id=devis.pk)
                       | Q(sources__devis_id=devis.pk))
               .exclude(statut=Facture.Statut.ANNULEE)
               .order_by('pk').distinct().first())
    if facture is not None:
        if facture.statut == Facture.Statut.BROUILLON:
            return (f'la facture {facture.reference} (brouillon) est déjà '
                    "créée. Supprimez-la ou annulez-la d'abord.")
        if facture.statut == Facture.Statut.PAYEE:
            return (f'la facture {facture.reference} est déjà payée. '
                    "Annulez-la d'abord.")
        return (f'la facture {facture.reference} est déjà émise. '
                "Annulez-la d'abord.")
    bc = (BonCommande.objects
          .filter(company_id=company_id, devis_id=devis.pk)
          .exclude(statut=BonCommande.Statut.ANNULE)
          .first())
    if bc is not None:
        return (f'le bon de commande {bc.reference} existe déjà '
                f"(« {bc.get_statut_display()} »). Annulez-le d'abord.")
    dossier = (RegulatoryDossier.objects
               .filter(company_id=company_id, devis_id=devis.pk)
               .exclude(statut=RegulatoryDossier.Statut.EN_CONSTITUTION)
               .first())
    if dossier is not None:
        nom = dossier.reference_dossier or f'n° {dossier.pk}'
        return (f'le dossier 82-21 {nom} est déjà '
                f'« {dossier.get_statut_display()} ».')
    # Apps propriétaires — par leurs sélecteurs, jamais leurs modèles.
    from apps.installations.selectors import (
        blocage_annulation_acceptation as blocage_chantier,
    )
    from apps.sav.selectors import (
        blocage_annulation_acceptation as blocage_sav,
    )
    company = devis.company
    return (blocage_chantier(devis.pk, company)
            or blocage_sav(devis.pk, company))


def annuler_acceptation(*, devis, user, motif=''):
    """Dés-accepte ``devis`` (miroir d'``accept_devis``) — décision fondateur
    du 08/10/2026.

    UNE transaction, sous le verrou du GROUPE DE VARIANTES pris dans l'ordre
    des ``pk`` (le même qu'``accept_devis`` : jamais d'inter-blocage entre une
    acceptation et une annulation concurrentes). Dans l'ordre :

    1. contrôle de blocage (``raison_blocage_annulation_acceptation``) — un
       blocage lève ``AnnulationAcceptationBloquee`` AVANT toute écriture ;
    2. le devis repasse « envoyé », ``date_acceptation`` / ``accepte_par_nom``
       / ``option_acceptee`` sont effacés (une ré-acceptation est une
       acceptation FRAÎCHE : l'événement ``devis_accepted`` repart) ;
    3. les sœurs refusées PAR cette acceptation (motif
       ``MOTIF_VARIANTE_NON_RETENUE``, ``date_refus`` == date d'acceptation,
       même groupe, jamais une version remplacée) redeviennent actives —
       « envoyé » si elles avaient été envoyées, sinon « brouillon » ;
    4. note de chatter (qui, quand, option et date annulées ; preuve de
       signature conservée) ;
    5. ``devis_acceptation_annulee`` est publié DANS la transaction : les
       abonnés défont leurs effets et tombent avec elle en cas d'échec.

    Un devis qui n'est pas « accepté » est rendu tel quel (no-op). La preuve
    e-signature (``DevisSignature``, PDF scellé) n'est jamais touchée.
    """
    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_acceptation_annulee

    with transaction.atomic():
        racine = devis.version_parent_id or devis.pk
        groupe = list(
            Devis.objects
            .select_related('company')
            .select_for_update(of=('self',))
            .filter(Q(pk=racine) | Q(version_parent_id=racine))
            .order_by('pk'))
        courant = next((d for d in groupe if d.pk == devis.pk), None)
        if courant is None or courant.statut != Devis.Statut.ACCEPTE:
            return courant or devis
        devis = courant

        raison = raison_blocage_annulation_acceptation(devis)
        if raison:
            raise AnnulationAcceptationBloquee(raison)

        ancienne_option = devis.option_acceptee or ''
        ancienne_date = devis.date_acceptation
        ancien_nom = devis.accepte_par_nom or ''
        devis.statut = Devis.Statut.ENVOYE
        devis.date_acceptation = None
        devis.accepte_par_nom = ''
        devis.option_acceptee = ''
        devis.save(update_fields=[
            'statut', 'date_acceptation', 'accepte_par_nom',
            'option_acceptee'])

        # Sœurs refusées PAR cette acceptation — et elles seules.
        restaurees = []
        if ancienne_date is not None:
            for soeur in groupe:
                if (soeur.pk == devis.pk
                        or soeur.company_id != devis.company_id
                        or soeur.statut != Devis.Statut.REFUSE
                        or soeur.is_active
                        or soeur.superseded_by_id is not None
                        or soeur.motif_refus != MOTIF_VARIANTE_NON_RETENUE
                        or soeur.date_refus != ancienne_date):
                    continue
                soeur.statut = (Devis.Statut.ENVOYE if soeur.date_envoi
                                else Devis.Statut.BROUILLON)
                soeur.date_refus = None
                soeur.motif_refus = ''
                soeur.is_active = True
                soeur.save(update_fields=[
                    'statut', 'date_refus', 'motif_refus', 'is_active'])
                activity.log_devis_note(
                    soeur, user,
                    f"Variante rétablie : l'acceptation de {devis.reference} "
                    'a été annulée.')
                restaurees.append(soeur.reference)

        qui = getattr(user, 'username', None) or 'le système'
        quand = timezone.localtime().strftime('%d/%m/%Y %H:%M')
        details = []
        if ancienne_option in Devis.OptionAcceptee.values:
            details.append(
                f'option « {Devis.OptionAcceptee(ancienne_option).label} »')
        elif ancienne_option:
            details.append(f'option « {ancienne_option} »')
        if ancienne_date:
            details.append(f'acceptée le {ancienne_date.strftime("%d/%m/%Y")}')
        if ancien_nom:
            details.append(f'par {ancien_nom}')
        corps = (f'Acceptation annulée le {quand} par {qui}'
                 + (f' ({", ".join(details)})' if details else '')
                 + ' — le devis repasse « Envoyé ».')
        if motif:
            corps += f' Motif : {motif}.'
        if restaurees:
            corps += f' Variante(s) rétablie(s) : {", ".join(restaurees)}.'
        corps += ' La preuve de signature du client est conservée.'
        activity.log_devis_note(devis, user, corps)

        devis_acceptation_annulee.send(
            sender=Devis, devis=devis, user=user,
            option_acceptee=ancienne_option,
            date_acceptation=ancienne_date, motif=motif or '')
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


# ── QJR76 : le courriel fournisseur ─────────────────────────────────────────
# `log_supplier_email` est l'autre envoi de document du domaine : il rejoint
# les e-mails d'acceptation et les OTP.
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


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (voir la docstring) : ils s'exécutent après toutes
# les définitions de ce module, donc l'ordre de chargement ne peut jamais faire
# lire un module à moitié construit. Chacun vise le module qui PORTE le corps —
# jamais la façade, dont les ré-exports s'exécutent dans l'ordre des tâches.
# SPL263 — QJR560 : ``accept_devis`` rattache l'aval financier d'une V2 ;
# le corps vit dans ``domain/revision.py`` (qui n'importe jamais ce module).
from apps.ventes.domain.revision import (  # noqa: E402
    rattacher_aval_financier_revision,
)
