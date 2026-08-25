"""T-TRACE — traçage des visiteurs EXTERNES et alertes anti-fraude.

ORDRES FONDATEUR DU 25/08/2026 (verbatim) :
  · « store IP … keep them stored » ;
  · « notify when two clients have any similar data that can show it is a
    competitor » ;
  · « always add the director in the notifications » ;
  · « and this at all the points … clients just visiting the website, client
    asking for a quote, client accessing their quote » ;
  · « the commercial should be notified by his previous visit and when and
    for how much time » ;
  · « if he asked for a NEW quote this should be clearly notified to
    commercial with red and director as well ».

VÉRITÉ TECHNIQUE ACTÉE. L'adresse MAC n'est PAS collectable depuis le web
(elle ne franchit jamais le routeur du visiteur). L'identifiant PRIMAIRE est
donc ``appareil_id`` — un uuid que le SITE pose lui-même dans le localStorage
du navigateur. L'IP est un signal SECONDAIRE : le fondateur l'a explicitement
jugée trompeuse (les IP sont massivement partagées au Maroc), elle ne suffit
donc jamais à AFFIRMER une identité — seulement à étayer un soupçon, et
toujours libellée comme tel dans le texte des alertes.

DEUX PRINCIPES QUI NE SE NÉGOCIENT PAS DANS CE MODULE
-----------------------------------------------------
1. **Le traçage ne casse JAMAIS un point public.** Toute écriture est
   best-effort : un `try/except` journalisé enveloppe chaque service. Un
   client qui ouvre sa proposition ne doit pas voir une erreur parce qu'une
   trace anti-fraude n'a pas pu s'écrire.
2. **Rien n'est inventé.** Une notification enrichie ne parle de l'historique
   d'un appareil QUE si cet historique existe réellement ; sans historique,
   la phrase est simplement absente — jamais « 0 visite », jamais une durée
   estimée, jamais un défaut forfaitaire.

Le service est unique et réexporté par ``apps/crm/services.py`` : aucun autre
module n'écrit ``VisiteExterne`` à la main.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Bornes de nettoyage (alignées sur les colonnes du modèle) ───────────────
MAX_CONTEXTE = 200
MAX_TOKEN_SUFFIXE = 6
MAX_IP = 64
MAX_USER_AGENT = 255
MAX_LANGUE = 10
MAX_APPAREIL = 64

#: Une durée sur page au-delà de 12 h n'est pas une lecture : c'est un onglet
#: oublié ouvert toute la nuit. Bornée pour ne pas polluer les totaux montrés
#: au commercial (« durée totale X min ») avec une valeur qui n'a aucun sens.
MAX_DUREE_S = 12 * 3600

#: Fenêtre de corrélation « concurrent » (ordre fondateur : 30 jours).
FENETRE_CORRELATION_JOURS = 30

#: Points de contact qui portent un DOCUMENT nominatif d'un prospect précis —
#: les seuls qui alimentent la corrélation concurrent. Une simple visite du
#: site (``visite_site``) est anonyme et ne désigne aucun lead : deux
#: visiteurs du même cybercafé ne sont pas un concurrent.
POINTS_DOCUMENT = ('proposition', 'questionnaire', 'booking', 'tunnel_lead')

#: Rôles SYSTÈME qui constituent la DIRECTION d'une société (registre canonique
#: ``apps.roles.models.CANONICAL_SYSTEM_ROLES``). C'est le mécanisme RÉEL déjà
#: utilisé par ``services._company_fallback_managers`` — jamais une seconde
#: notion de « direction » inventée ici.
ROLES_DIRECTION = ('Directeur', 'Administrateur')


# ═══════════════════════════════════════════════════════════════════════════
# Nettoyage des entrées
# ═══════════════════════════════════════════════════════════════════════════

def _texte(valeur, longueur) -> str:
    """Chaîne nettoyée et tronquée — jamais None, jamais une exception."""
    if valeur is None:
        return ''
    try:
        return str(valeur).strip()[:longueur]
    except Exception:  # noqa: BLE001 — défensif : une entrée publique
        return ''


#: Alias PUBLIC du nettoyeur — les vues publiques bornent leurs entrées avec
#: EXACTEMENT le même code que le service (jamais une seconde troncature qui
#: pourrait diverger des colonnes du modèle).
nettoyer_texte = _texte


def _duree(valeur) -> int:
    """Secondes bornées [0, MAX_DUREE_S] — une valeur illisible vaut 0."""
    try:
        return max(0, min(MAX_DUREE_S, int(float(valeur))))
    except (TypeError, ValueError):
        return 0


def suffixe_jeton(token) -> str:
    """6 DERNIERS caractères d'un jeton public — jamais le jeton lui-même.

    Assez pour rapprocher deux traces d'un même lien dans une enquête, jamais
    assez pour rouvrir le lien (les jetons font 43+ caractères)."""
    brut = _texte(token, 200)
    return brut[-MAX_TOKEN_SUFFIXE:] if brut else ''


def ip_de_requete(request) -> str:
    """IP du client, lue CÔTÉ SERVEUR — jamais acceptée d'un corps de requête.

    Même extraction que le webhook lead (``webhooks.website_lead_webhook``) :
    première adresse de ``X-Forwarded-For`` (le proxy/Worker met le client en
    tête), repli ``REMOTE_ADDR``."""
    if request is None:
        return ''
    try:
        transmise = (request.META.get('HTTP_X_FORWARDED_FOR', '') or '')
        premiere = transmise.split(',')[0].strip()
        return _texte(premiere or request.META.get('REMOTE_ADDR'), MAX_IP)
    except Exception:  # noqa: BLE001 — défensif
        return ''


def user_agent_de_requete(request) -> str:
    """Navigateur annoncé, TRONQUÉ — lu côté serveur, jamais du corps."""
    if request is None:
        return ''
    try:
        return _texte(request.META.get('HTTP_USER_AGENT'), MAX_USER_AGENT)
    except Exception:  # noqa: BLE001 — défensif
        return ''


def appareil_de_requete(request) -> str:
    """``appareil_id`` porté par une requête publique (clé ADDITIVE).

    Trois emplacements, dans l'ordre — un POST le met dans son corps, un GET
    de page ne peut pas :
      1. le corps (``request.data``) — beacon, questionnaire, engagement ;
      2. la query string (``?appareil_id=…``) — ouverture d'un document ;
      3. l'en-tête ``X-Appareil-Id`` — quand le site préfère ne rien mettre
         dans l'URL.

    Absent des trois = comportement historique inchangé : ce module ne réclame
    jamais la clé, il l'utilise quand elle est là."""
    if request is None:
        return ''
    try:
        donnees = getattr(request, 'data', None)
        if isinstance(donnees, dict):
            trouve = _texte(donnees.get('appareil_id'), MAX_APPAREIL)
            if trouve:
                return trouve
        params = getattr(request, 'query_params', None)
        if params is None:
            params = getattr(request, 'GET', None)
        if params is not None:
            trouve = _texte(params.get('appareil_id'), MAX_APPAREIL)
            if trouve:
                return trouve
        return _texte(
            request.headers.get('X-Appareil-Id'), MAX_APPAREIL)
    except Exception:  # noqa: BLE001 — défensif
        return ''


# ═══════════════════════════════════════════════════════════════════════════
# Service unique d'écriture
# ═══════════════════════════════════════════════════════════════════════════

def enregistrer_visite_externe(company, *, point, appareil_id='', lead=None,
                               contexte='', token='', ip='', user_agent='',
                               langue='', duree_s=0, fin=False, request=None):
    """Enregistre UN passage d'un visiteur externe. Best-effort, jamais bloquant.

    C'est le SEUL point d'écriture de ``crm.VisiteExterne`` : chaque accroche
    (beacon du site, webhook lead, ouverture de proposition, réponse au
    questionnaire, réservation) passe par ici.

    BATTEMENTS. Le beacon du site bat toutes les ~20 s. Sans garde, une lecture
    de 10 minutes produirait 30 lignes : le MÊME appareil, sur la MÊME page, au
    MÊME point, dans la fenêtre ``VisiteExterne.FENETRE_BATTEMENT_MINUTES``,
    met donc à jour la MÊME ligne. ``duree_s`` est un CUMUL envoyé par le site
    (jamais un delta) : on garde la plus grande valeur vue, de sorte qu'un
    battement arrivé dans le désordre ne fasse jamais RECULER la durée. Un
    battement portant ``fin=True`` clôt la visite — le suivant en ouvre une
    nouvelle.

    ``ip``/``user_agent`` sont lus de ``request`` quand ils ne sont pas fournis
    explicitement : ils ne viennent JAMAIS du corps de la requête.

    Renvoie la ``VisiteExterne`` écrite, ou ``None`` (société inconnue, ou
    échec — journalisé, jamais propagé).
    """
    try:
        if company is None:
            return None
        from .models import VisiteExterne

        appareil_id = _texte(appareil_id, MAX_APPAREIL)
        contexte = _texte(contexte, MAX_CONTEXTE)
        langue = _texte(langue, MAX_LANGUE)
        ip = _texte(ip, MAX_IP) or ip_de_requete(request)
        user_agent = (_texte(user_agent, MAX_USER_AGENT)
                      or user_agent_de_requete(request))
        duree_s = _duree(duree_s)
        fin = bool(fin)

        depuis = timezone.now() - timedelta(
            minutes=VisiteExterne.FENETRE_BATTEMENT_MINUTES)
        en_cours = VisiteExterne.objects.filter(
            company=company, point=point, contexte=contexte,
            terminee=False, created_at__gte=depuis)
        if appareil_id:
            # Cas NORMAL : l'appareil identifie le visiteur.
            en_cours = en_cours.filter(appareil_id=appareil_id)
        elif ip:
            # Repli quand le site n'a pas (encore) posé d'``appareil_id`` —
            # sans lui, CHAQUE battement d'un beacon ouvrirait une ligne, et
            # une proposition lue 10 min en produirait des dizaines. On
            # regroupe alors sur (IP + navigateur), la meilleure approximation
            # disponible du « même visiteur, même page, même demi-heure ». Ce
            # repli sert UNIQUEMENT à ne pas dupliquer des lignes : il n'est
            # jamais utilisé pour AFFIRMER une identité (les corrélations
            # « concurrent » qui s'appuient sur l'IP le disent explicitement).
            en_cours = en_cours.filter(
                appareil_id='', ip=ip, user_agent=user_agent)
        else:
            # Ni appareil ni IP : rien sur quoi regrouper honnêtement.
            en_cours = en_cours.none()
        visite = en_cours.order_by('-created_at').first()

        if visite is not None:
            champs = []
            if duree_s > visite.duree_s:
                visite.duree_s = duree_s
                champs.append('duree_s')
            if fin and not visite.terminee:
                visite.terminee = True
                champs.append('terminee')
            # On COMPLÈTE ce qu'on ne savait pas encore, on n'écrase jamais ce
            # qui est déjà connu (un battement ultérieur peut arriver sans
            # en-tête, ou depuis une page qui ignore la langue).
            if lead is not None and visite.lead_id is None:
                visite.lead = lead
                champs.append('lead')
            for nom, valeur in (('ip', ip), ('user_agent', user_agent),
                                ('langue', langue),
                                ('token_suffixe', suffixe_jeton(token))):
                if valeur and not getattr(visite, nom):
                    setattr(visite, nom, valeur)
                    champs.append(nom)
            if champs:
                visite.save(update_fields=champs + ['updated_at'])
            return visite

        return VisiteExterne.objects.create(
            company=company, lead=lead, point=point, contexte=contexte,
            token_suffixe=suffixe_jeton(token), ip=ip,
            user_agent=user_agent, langue=langue, appareil_id=appareil_id,
            duree_s=duree_s, terminee=fin,
        )
    except Exception as exc:  # noqa: BLE001 — le traçage ne casse JAMAIS un
        # point public : on journalise et on rend la main.
        logger.warning(
            'T-TRACE: enregistrer_visite_externe échoué (point=%s) : %s',
            point, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Lecture — ce que l'on sait d'un appareil
# ═══════════════════════════════════════════════════════════════════════════

def historique_appareil(company, appareil_id):
    """Résumé de TOUT ce que la société sait de CET appareil.

    Renvoie ``None`` quand rien n'est connu — jamais un résumé vide qui
    laisserait croire à une mesure (règle « zéro chiffre inventé »).

    Dict : ``visites`` (nombre), ``duree_totale_s``, ``premiere``, ``derniere``
    (datetimes), ``pages`` (contextes distincts, les plus récents d'abord) et
    ``leads`` (identifiants des leads déjà touchés par cet appareil)."""
    try:
        if company is None:
            return None
        appareil_id = _texte(appareil_id, MAX_APPAREIL)
        if not appareil_id:
            return None
        from django.db.models import Count, Max, Min, Sum

        from .models import VisiteExterne

        qs = VisiteExterne.objects.filter(
            company=company, appareil_id=appareil_id)
        agrege = qs.aggregate(
            visites=Count('id'), duree_totale_s=Sum('duree_s'),
            premiere=Min('created_at'), derniere=Max('created_at'))
        if not agrege.get('visites'):
            return None
        pages = list(
            qs.exclude(contexte='')
            .order_by('-created_at')
            .values_list('contexte', flat=True)[:20])
        vues = []
        for page in pages:
            if page not in vues:
                vues.append(page)
        return {
            'visites': agrege['visites'],
            'duree_totale_s': agrege.get('duree_totale_s') or 0,
            'premiere': agrege.get('premiere'),
            'derniere': agrege.get('derniere'),
            'pages': vues,
            # Dédoublonné en PYTHON, jamais par `.distinct()` : le
            # `Meta.ordering` du modèle se glisse dans le SELECT DISTINCT et
            # ramène alors des doublons (piège Django classique).
            'leads': sorted(set(
                qs.exclude(lead__isnull=True)
                .values_list('lead_id', flat=True))),
        }
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('T-TRACE: historique_appareil échoué : %s', exc)
        return None


def _duree_fr(secondes) -> str:
    """« 45 s » / « 12 min » / « 1 h 05 » — jamais une durée arrondie à faux."""
    secondes = int(secondes or 0)
    if secondes < 60:
        return f'{secondes} s'
    if secondes < 3600:
        return f'{secondes // 60} min'
    return f'{secondes // 3600} h {(secondes % 3600) // 60:02d}'


def _date_fr(moment) -> str:
    """« 24/08/2026 à 18:32 » dans le fuseau du serveur, ou '' si absent."""
    if moment is None:
        return ''
    try:
        return timezone.localtime(moment).strftime('%d/%m/%Y à %H:%M')
    except Exception:  # noqa: BLE001 — défensif
        return ''


def resume_historique_fr(historique, *, avant_demande=False) -> str:
    """Phrase FR de l'historique d'un appareil, pour le corps d'une notification.

    Formulation demandée par le fondateur (« the commercial should be notified
    by his previous visit and when and for how much time ») : « A visité le
    site N fois avant sa demande (durée totale X min ; dernière visite le
    24/08/2026 à 18:32). »

    Renvoie '' quand il n'y a RIEN à dire : une notification ne porte jamais
    « 0 visite » ni une durée estimée — elle porte simplement une phrase de
    moins. Chaque parenthèse n'apparaît que si sa donnée existe vraiment.
    """
    if not historique or not historique.get('visites'):
        return ''
    visites = int(historique['visites'])
    # « fois » est invariable en français : jamais de pluriel à accorder ici.
    quand = ' avant sa demande' if avant_demande else ''
    phrase = f'A visité le site {visites} fois{quand}'
    details = []
    duree = historique.get('duree_totale_s') or 0
    if duree:
        details.append(f'durée totale {_duree_fr(duree)}')
    derniere = _date_fr(historique.get('derniere'))
    if derniere:
        details.append(f'dernière visite le {derniere}')
    pages = historique.get('pages') or []
    if pages:
        details.append(f'dernière page {pages[0]}')
    if details:
        phrase += f' ({" ; ".join(details)})'
    return f'{phrase}.'


# ═══════════════════════════════════════════════════════════════════════════
# Destinataires — la direction est TOUJOURS ajoutée
# ═══════════════════════════════════════════════════════════════════════════

def utilisateurs_direction(company):
    """Utilisateurs ACTIFS de DIRECTION de la société (``ROLES_DIRECTION``).

    Mécanisme RÉEL du dépôt : le rôle est une FK ``CustomUser.role`` vers
    ``roles.Role`` dont le ``nom`` appartient au registre canonique
    ``CANONICAL_SYSTEM_ROLES`` — exactement la requête que fait déjà
    ``services._company_fallback_managers``. Liste éventuellement VIDE (une
    société sans compte Directeur/Administrateur n'en a pas) : on ne fabrique
    jamais un destinataire pour tenir la promesse."""
    if company is None:
        return []
    try:
        from django.contrib.auth import get_user_model
        return list(get_user_model().objects.filter(
            company=company, is_active=True,
            role__nom__in=ROLES_DIRECTION,
        ).order_by('id'))
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('T-TRACE: utilisateurs_direction échoué : %s', exc)
        return []


def avec_direction(destinataires, company):
    """« always add the director in the notifications » (fondateur).

    Renvoie ``destinataires`` + la direction de la société, DÉDUPLIQUÉ et dans
    l'ordre (le commercial concerné reste en tête — c'est lui qui agit)."""
    combines = list(destinataires or []) + utilisateurs_direction(company)
    vus, sortie = set(), []
    for utilisateur in combines:
        pk = getattr(utilisateur, 'pk', None)
        if pk is not None and pk not in vus:
            vus.add(pk)
            sortie.append(utilisateur)
    return sortie


# ═══════════════════════════════════════════════════════════════════════════
# Alertes ROUGES anti-fraude
# ═══════════════════════════════════════════════════════════════════════════

def _une_seule_fois(company, cle) -> bool:
    """Garde d'idempotence permanente (``core.idempotency.dedupe_event``).

    Une alerte anti-fraude doit arriver UNE fois, pas à chaque battement du
    beacon. Réutilise le registre d'idempotence de fondation déjà employé par
    le webhook du site — jamais un second mécanisme. Un échec du registre vaut
    « laisse passer » : mieux vaut une alerte en double qu'une alerte perdue."""
    try:
        from core.idempotency import dedupe_event
        empreinte = hashlib.sha256(cle.encode('utf-8')).hexdigest()
        return dedupe_event(
            company=company, source='crm.visite_alerte', event_id=empreinte)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('T-TRACE: garde d’idempotence indisponible : %s', exc)
        return True


def alerter_appareil_partage(lead) -> None:
    """ALERTE ROUGE (a) — une NOUVELLE demande de devis arrive depuis un
    appareil DÉJÀ rattaché à un AUTRE lead de la même société.

    « if he asked for a NEW quote this should be clearly notified to commercial
    with red and director as well » (fondateur). Le « rouge » est la sévérité
    CRITIQUE de l'événement ``visiteur_appareil_partage``
    (``notifications/severity.py``) — le titre porte en plus le point rouge
    pour qu'il soit lisible dans un e-mail ou un push, hors de la cloche.

    Ne conclut RIEN : l'alerte nomme les DEUX fiches et laisse l'arbitrage au
    commercial (même client qui recommande ? concurrent en reconnaissance ?).
    Best-effort — jamais d'exception propagée, jamais bloquante pour la
    capture du lead.
    """
    try:
        appareil_id = _texte(getattr(lead, 'appareil_id', ''), MAX_APPAREIL)
        company = getattr(lead, 'company', None)
        if not appareil_id or company is None or lead.pk is None:
            return
        from .models import Lead

        autres = list(
            Lead.objects.filter(company=company, appareil_id=appareil_id)
            .exclude(pk=lead.pk)
            .order_by('-date_creation')
            .values_list('pk', 'nom')[:5])
        if not autres:
            return
        if not _une_seule_fois(company, f'appareil_partage:{lead.pk}'):
            return

        from apps.notifications.services import notify_many

        from .services import lead_notification_recipients
        destinataires = avec_direction(
            lead_notification_recipients(lead), company)
        if not destinataires:
            return

        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        fiches = ', '.join(
            f'#{pk} {(autre_nom or "").strip() or "sans nom"}'
            for pk, autre_nom in autres)
        corps = [
            f'La demande de {nom} (fiche #{lead.pk}) arrive depuis un appareil '
            f'déjà utilisé pour {len(autres)} autre(s) fiche(s) : {fiches}.',
            'Possible doublon (le même client redemande) ou reconnaissance '
            'concurrente : à arbitrer avant de chiffrer.',
        ]
        historique = resume_historique_fr(
            historique_appareil(company, appareil_id))
        if historique:
            corps.append(historique)
        notify_many(
            destinataires, 'visiteur_appareil_partage',
            f'🔴 Nouvelle demande depuis un appareil déjà connu — {nom}',
            body='\n'.join(corps),
            link=f'/crm/leads?lead={lead.pk}',
            company=company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'T-TRACE: alerter_appareil_partage échoué (lead #%s) : %s',
            getattr(lead, 'pk', '?'), exc)


def detecter_concurrent(company, *, appareil_id='', ip='') -> None:
    """ALERTE ROUGE (b) — un MÊME visiteur consulte les documents de PLUSIEURS
    prospects différents sous 30 jours.

    « notify when two clients have any similar data that can show it is a
    competitor » (fondateur). Deux signaux, de force très différente :

      · ``appareil_id`` — signal FORT : le même navigateur a ouvert les
        propositions/questionnaires de ≥ 2 leads distincts ;
      · ``ip`` — signal FAIBLE, examiné SEULEMENT si l'appareil ne dit rien.
        Les IP sont massivement partagées au Maroc (4G, cybercafés, une
        entreprise entière derrière une seule sortie) : l'alerte le DIT dans
        son texte plutôt que de laisser croire à une preuve.

    Seuls les points qui désignent un prospect NOMMÉ comptent
    (``POINTS_DOCUMENT``) : deux visiteurs anonymes du site ne sont pas un
    concurrent. Best-effort — jamais d'exception propagée.
    """
    try:
        if company is None:
            return
        appareil_id = _texte(appareil_id, MAX_APPAREIL)
        ip = _texte(ip, MAX_IP)
        depuis = timezone.now() - timedelta(days=FENETRE_CORRELATION_JOURS)
        from .models import VisiteExterne

        base = VisiteExterne.objects.filter(
            company=company, point__in=POINTS_DOCUMENT,
            created_at__gte=depuis).exclude(lead__isnull=True)

        signal, cle, leads = '', '', []
        if appareil_id:
            leads = sorted(set(
                base.filter(appareil_id=appareil_id)
                .values_list('lead_id', flat=True)))
            if len(leads) >= 2:
                signal, cle = 'appareil', f'appareil:{appareil_id}'
        if not signal and ip:
            leads = sorted(set(
                base.filter(ip=ip).values_list('lead_id', flat=True)))
            if len(leads) >= 2:
                signal, cle = 'ip', f'ip:{ip}'
        if not signal:
            return

        empreinte = ','.join(str(pk) for pk in leads)
        if not _une_seule_fois(company, f'concurrent:{cle}:{empreinte}'):
            return

        from .models import Lead
        noms = list(
            Lead.objects.filter(company=company, pk__in=leads)
            .order_by('pk').values_list('pk', 'nom')[:10])
        fiches = ', '.join(
            f'#{pk} {(nom or "").strip() or "sans nom"}' for pk, nom in noms)

        if signal == 'appareil':
            titre = '🔴 Un même appareil consulte plusieurs prospects'
            constat = (
                f'Le même appareil a ouvert les documents de {len(leads)} '
                f'prospects différents en {FENETRE_CORRELATION_JOURS} jours : '
                f'{fiches}.')
            nuance = ('Signal FORT (identifiant d’appareil). Un concurrent en '
                      'reconnaissance se comporte exactement ainsi — à '
                      'vérifier avant d’envoyer un nouveau chiffrage.')
        else:
            titre = '🔴 Une même adresse IP consulte plusieurs prospects'
            constat = (
                f'La même adresse IP a servi à ouvrir les documents de '
                f'{len(leads)} prospects différents en '
                f'{FENETRE_CORRELATION_JOURS} jours : {fiches}.')
            nuance = ('Signal FAIBLE : au Maroc une IP est très souvent '
                      'partagée (4G, cybercafé, une entreprise entière). '
                      'À traiter comme une piste à vérifier, jamais comme '
                      'une preuve.')

        destinataires = _destinataires_des_leads(company, leads)
        if not destinataires:
            return
        from apps.notifications.services import notify_many
        notify_many(
            destinataires, 'visiteur_concurrent_suspecte', titre,
            body='\n'.join([constat, nuance]),
            link=f'/crm/leads?lead={leads[0]}',
            company=company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('T-TRACE: detecter_concurrent échoué : %s', exc)


def _destinataires_des_leads(company, lead_ids):
    """Les commerciaux des leads concernés + la direction, dédupliqués.

    Une corrélation concerne PLUSIEURS fiches, donc potentiellement plusieurs
    commerciaux : ils sont tous prévenus (chacun ignore ce que l'autre voit),
    et la direction l'est TOUJOURS."""
    from .models import Lead
    from .services import lead_notification_recipients

    destinataires = []
    for lead in Lead.objects.filter(company=company, pk__in=lead_ids):
        destinataires.extend(lead_notification_recipients(lead))
    return avec_direction(destinataires, company)


def rattacher_visites_au_lead(lead) -> int:
    """Rattache RÉTROACTIVEMENT les visites ANONYMES d'un appareil à SON lead.

    Le visiteur passe d'abord anonymement (``lead`` NULL) puis demande un
    devis : à cet instant seulement on sait à QUI appartenaient ces passages.
    Ne touche QUE les lignes encore sans lead de la MÊME société et du MÊME
    appareil — jamais une trace déjà attribuée à un autre lead (ce serait
    justement effacer la preuve qu'un appareil sert deux dossiers).

    Renvoie le nombre de lignes rattachées (0 = rien à faire). Best-effort."""
    try:
        appareil_id = _texte(getattr(lead, 'appareil_id', ''), MAX_APPAREIL)
        company = getattr(lead, 'company', None)
        if not appareil_id or company is None or lead.pk is None:
            return 0
        from .models import VisiteExterne

        return VisiteExterne.objects.filter(
            company=company, appareil_id=appareil_id, lead__isnull=True,
        ).update(lead=lead)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'T-TRACE: rattacher_visites_au_lead échoué (lead #%s) : %s',
            getattr(lead, 'pk', '?'), exc)
        return 0


def tracer_et_correler(company, *, point, appareil_id='', lead=None,
                       contexte='', token='', langue='', duree_s=0,
                       fin=False, request=None, ip='', user_agent=''):
    """Enregistre la visite PUIS lance la détection de corrélation concurrent.

    Le raccourci que TOUTES les accroches appellent : une trace qui ne
    déclencherait aucune analyse ne servirait à rien, et une analyse sans
    trace n'aurait rien à lire. Best-effort de bout en bout."""
    visite = enregistrer_visite_externe(
        company, point=point, appareil_id=appareil_id, lead=lead,
        contexte=contexte, token=token, langue=langue, duree_s=duree_s,
        fin=fin, request=request, ip=ip, user_agent=user_agent)
    if visite is not None and point in POINTS_DOCUMENT:
        detecter_concurrent(
            company, appareil_id=visite.appareil_id, ip=visite.ip)
    return visite
