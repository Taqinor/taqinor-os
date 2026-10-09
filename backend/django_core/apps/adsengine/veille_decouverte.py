"""VEIL15/VEIL16 — Découverte de vendeurs : ingestion idempotente d'une page de
résultats ``ads_archive`` et orchestration à la demande (une étape = un appel).

Ingestion (VEIL15) : ``ingerer_page(requete, reponse, numero_page)`` — dans UNE
transaction, verrou ``select_for_update`` sur la requête : upsert des pubs vues,
des agrégats annonceur (pubs DISTINCTES par ``ad_archive_id``, pays vus,
mots-clés, ≤ 5 extraits, domaines comptés), du curseur et des compteurs.
Rejouer la même page ne change rien ; une erreur au milieu d'une page ne laisse
ni curseur avancé ni pubs partielles.

``legende_vers_domaine(texte)`` extrait le domaine AFFICHÉ d'une légende
d'appel à l'action (texte libre, PAS une URL garantie) sans nouvelle
dépendance : nom d'hôte en minuscules, sans ``www.``, réduit au domaine
enregistrable (suffixes ``co.uk``/``com.fr``… reconnus). Une légende sans
domaine → ``''`` (jamais un faux domaine).
"""
from __future__ import annotations

import datetime
import functools
import json
import logging
import re
from collections import Counter
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

LONGUEUR_EXTRAIT_PUB = 500
LONGUEUR_EXTRAIT_ANNONCEUR = 200
MAX_EXTRAITS_ANNONCEUR = 5

# ── legende_vers_domaine ────────────────────────────────────────────────────
# TLD reconnus (liste fermée : un mot suivi d'un point n'est PAS un domaine).
_TLD_GENERIQUES = {
    'com', 'net', 'org', 'info', 'biz', 'shop', 'store', 'online', 'site',
    'boutique', 'fashion', 'clothing', 'shoes', 'bags', 'style', 'co', 'io',
    'app', 'me', 'eu', 'store', 'top', 'xyz', 'club', 'world', 'website',
    'tech', 'design', 'live', 'life', 'moda', 'paris', 'london', 'berlin',
    'tienda', 'uk', 'ma', 'us', 'ch', 'no', 'is', 'tr', 'cn', 'au', 'ca',
    'br',  # AACQ38 — com.br
}
_TLD_PAYS_UE = {
    'at', 'be', 'bg', 'hr', 'cy', 'cz', 'dk', 'ee', 'fi', 'fr', 'de', 'gr',
    'hu', 'ie', 'it', 'lv', 'lt', 'lu', 'mt', 'nl', 'pl', 'pt', 'ro', 'sk',
    'si', 'es', 'se',
}
TLD_CONNUS = _TLD_GENERIQUES | _TLD_PAYS_UE
# Suffixes publics à deux niveaux (le domaine enregistrable en a trois).
SUFFIXES_DOUBLES = {
    'co.uk', 'org.uk', 'me.uk', 'ltd.uk', 'plc.uk', 'net.uk', 'ac.uk',
    'com.fr', 'asso.fr', 'com.es', 'org.es', 'com.pl', 'com.pt', 'com.gr',
    'com.cy', 'com.mt', 'co.at', 'or.at', 'com.ro', 'co.hu', 'com.hr',
    'com.de', 'co.it', 'com.au', 'co.ma',
    # AACQ38 — suffixes à deux niveaux manquants (jamais rendus seuls).
    'com.tr', 'org.tr', 'net.tr', 'com.cn', 'net.cn', 'org.cn', 'com.br',
    'net.br', 'org.br', 'com.ma', 'net.ma', 'org.ma', 'net.au', 'org.au',
}


@functools.lru_cache(maxsize=1)
def _hebergeurs_boutiques():
    """AACQ38 — hébergeurs de boutiques (myshopify.com, wixsite.com…), lus
    dans le lexique ``places_de_marche.json`` (une seule source)."""
    chemin = (Path(__file__).resolve().parent / 'data' / 'veille_lexiques'
              / 'places_de_marche.json')
    donnees = json.loads(chemin.read_text(encoding='utf-8'))
    return frozenset(
        str(d).lower() for d in donnees.get('hebergeurs_boutiques', []))


_RE_HOTE = re.compile(
    r'(?<![\w.@/-])(?:https?://)?(?:[\w.+-]+@)?'
    r'((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})'
    r'(?=$|[/\s:?#),;!"\'»]|\.(?:\s|$))',
    re.IGNORECASE)


def legende_vers_domaine(texte):
    """Domaine affiché d'une légende, ou ``''`` si aucun domaine certain."""
    if not texte:
        return ''
    for trouve in _RE_HOTE.finditer(str(texte).strip()):
        hote = trouve.group(1).lower().strip('.')
        labels = hote.split('.')
        if len(labels) < 2 or labels[-1] not in TLD_CONNUS:
            continue
        if labels[0] == 'www':
            labels = labels[1:]
        if len(labels) < 2:
            continue
        racine = '.'.join(labels[-2:])
        if racine in _hebergeurs_boutiques():
            # AACQ38 — boutique hébergée : le sous-domaine EST le vendeur ;
            # l'hébergeur nu n'est jamais un domaine de vendeur.
            if len(labels) < 3:
                continue
            return '.'.join(labels[-3:])
        nb = 3 if racine in SUFFIXES_DOUBLES else 2
        if len(labels) < nb:
            continue
        domaine = '.'.join(labels[-nb:])
        if domaine in SUFFIXES_DOUBLES:  # AACQ38 — jamais un suffixe public
            continue
        return domaine
    return ''


# ── Extraction d'une pub reçue (champs ads_archive autorisés SEULEMENT) ─────
def _premier(liste):
    for valeur in liste or []:
        if valeur:
            return str(valeur)
    return ''


def _date(valeur):
    if not valeur:
        return None
    dt = parse_datetime(str(valeur))
    if dt is None:
        try:
            jour = datetime.date.fromisoformat(str(valeur)[:10])
        except ValueError:
            return None
        dt = datetime.datetime(jour.year, jour.month, jour.day,
                               tzinfo=datetime.timezone.utc)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, datetime.timezone.utc)
    return dt


def _payeurs(pub):
    noms = []
    for entree in pub.get('beneficiary_payers') or []:
        if isinstance(entree, dict):
            nom = entree.get('payer') or entree.get('beneficiary')
        else:
            nom = entree
        if nom and str(nom) not in noms:
            noms.append(str(nom)[:200])
    return noms


def extraire_pub(pub, pays):
    """Champs stockés d'une pub ``ads_archive`` (aucune URL de snapshot)."""
    legendes = [str(c) for c in (pub.get('ad_creative_link_captions') or [])
                if c]
    domaine = ''
    for legende in legendes:
        domaine = legende_vers_domaine(legende)
        if domaine:
            break
    return {
        'extrait': _premier(pub.get('ad_creative_bodies'))[
            :LONGUEUR_EXTRAIT_PUB],
        'legende': (legendes[0] if legendes else '')[:500],
        'domaine': domaine,
        'titres': [str(t)[:200] for t in
                   (pub.get('ad_creative_link_titles') or []) if t][:5],
        'langues': [str(x) for x in (pub.get('languages') or [])][:10],
        'plateformes': [str(x) for x in
                        (pub.get('publisher_platforms') or [])][:10],
        'payeurs': _payeurs(pub),
        'debut_diffusion': _date(pub.get('ad_delivery_start_time')),
        'fin_diffusion': _date(pub.get('ad_delivery_stop_time')),
        'pays_portee': [pays],
    }


def recalculer_agregats(annonceur):
    """Recalcule les agrégats d'un annonceur DEPUIS ses pubs vues (idempotent :
    deux pubs de même ``ad_archive_id`` vues par deux requêtes comptent une
    fois)."""
    from .models import VeillePubVue

    pubs = list(VeillePubVue.objects.filter(
        company_id=annonceur.company_id, annonceur=annonceur)
        .select_related('requete').order_by('id'))
    par_ad = {}
    for pv in pubs:
        par_ad.setdefault(pv.ad_archive_id, pv)
    annonceur.nb_pubs_vues = len(par_ad)
    annonceur.pays_vus = sorted({pv.requete.pays for pv in pubs})
    annonceur.mots_cles = sorted({pv.requete.mot_cle for pv in pubs})
    extraits, textes = [], set()
    for ad_id, pv in par_ad.items():
        texte = (pv.extrait or '').strip()[:LONGUEUR_EXTRAIT_ANNONCEUR]
        if texte and texte not in textes:
            textes.add(texte)
            extraits.append({'texte': texte, 'ad_archive_id': ad_id})
        if len(extraits) >= MAX_EXTRAITS_ANNONCEUR:
            break
    annonceur.extraits = extraits
    compte = Counter(pv.domaine for pv in par_ad.values() if pv.domaine)
    annonceur.domaines = [{'domaine': d, 'nb': n}
                          for d, n in sorted(compte.items(),
                                             key=lambda x: (-x[1], x[0]))]
    payeurs = []
    for pv in par_ad.values():
        for nom in pv.payeurs or []:
            if nom not in payeurs:
                payeurs.append(nom)
    annonceur.payeurs = payeurs
    if par_ad and not annonceur.ad_archive_id_exemple:
        annonceur.ad_archive_id_exemple = next(iter(par_ad))
    annonceur.save(update_fields=[
        'nb_pubs_vues', 'pays_vus', 'mots_cles', 'extraits', 'domaines',
        'payeurs', 'ad_archive_id_exemple', 'page_name', 'updated_at'])


def ingerer_page(requete, reponse, numero_page):
    """Ingère UNE page de résultats pour ``requete`` (idempotent).

    ``reponse`` = la sortie de ``AdLibraryClient.chercher``. Renvoie
    ``{deja_ingeree, pubs, nouveaux_annonceurs, a_suivant}``. Tout se fait
    dans UNE transaction : en cas d'erreur, rien n'est écrit."""
    from .models import (VeilleAnnonceur, VeilleDecouverte, VeillePubVue,
                         VeilleRequete)

    numero_page = int(numero_page)
    with transaction.atomic():
        req = (VeilleRequete.objects.select_for_update()
               .get(pk=requete.pk))
        if any(int(e.get('page', 0)) == numero_page
               for e in (req.journal_pages or [])):
            return {'deja_ingeree': True, 'pubs': 0,
                    'nouveaux_annonceurs': 0,
                    'a_suivant': bool(req.curseur_after)}
        dec = VeilleDecouverte.objects.select_for_update().get(
            pk=req.decouverte_id)
        deja_vus = set(VeillePubVue.objects.filter(
            company_id=req.company_id, requete__decouverte_id=dec.pk)
            .values_list('annonceur__page_id', flat=True))
        touches = {}
        page_ids = set()
        pubs = list(reponse.get('pubs') or [])
        for pub in pubs:
            ad_id = str(pub.get('id') or '').strip()
            page_id = str(pub.get('page_id') or '').strip()
            if not ad_id or not page_id:
                continue
            page_ids.add(page_id)
            nom = str(pub.get('page_name') or '')[:255]
            annonceur, _cree = VeilleAnnonceur.objects.get_or_create(
                company_id=req.company_id, page_id=page_id,
                defaults={'page_name': nom})
            if nom and annonceur.page_name != nom:
                annonceur.page_name = nom
            VeillePubVue.objects.get_or_create(
                company_id=req.company_id, requete=req, ad_archive_id=ad_id,
                defaults=dict(annonceur=annonceur, numero_page=numero_page,
                              **extraire_pub(pub, req.pays)))
            touches[annonceur.pk] = annonceur
        for annonceur in touches.values():
            recalculer_agregats(annonceur)

        nouveaux = len(page_ids - deja_vus)
        a_suivant = bool(reponse.get('a_suivant'))
        req.journal_pages = list(req.journal_pages or []) + [
            {'page': numero_page, 'pubs': len(pubs), 'nouveaux': nouveaux}]
        req.pages_lues += 1
        req.appels += 1
        req.pubs += len(pubs)
        req.nouveaux_annonceurs += nouveaux
        # Curseur : en mémoire de la requête le temps du lancement SEULEMENT.
        req.curseur_after = (reponse.get('after_suivant') or '') \
            if a_suivant else ''
        req.save(update_fields=[
            'journal_pages', 'pages_lues', 'appels', 'pubs',
            'nouveaux_annonceurs', 'curseur_after', 'updated_at'])

        dec.pages_lues += 1
        dec.appels_consommes += 1
        dec.pubs_recues += len(pubs)
        if reponse.get('usage'):
            dec.dernier_usage_app = dict(reponse['usage'])
        dec.save(update_fields=['pages_lues', 'appels_consommes',
                                'pubs_recues', 'dernier_usage_app',
                                'updated_at'])
    return {'deja_ingeree': False, 'pubs': len(pubs),
            'nouveaux_annonceurs': nouveaux, 'a_suivant': a_suivant}


# ═════════════════════════════════════════════════════════════════════════════
# VEIL16 — Lancement à la demande : une tâche Celery = UN appel, garde de
# quota, reprise. Aucune tâche planifiée (beat) : seule l'action d'un humain
# lance une découverte.
# ═════════════════════════════════════════════════════════════════════════════
# Reprise progressive après un quota : toujours < 3 600 s (visibilité Redis).
PALIERS_PAUSE_S = (300, 600, 1200, 1800)
# Délai court entre deux étapes (une étape = une page d'une requête).
COUNTDOWN_ETAPE_S = 2
JOB_KIND = 'veille_decouverte'
NOM_TACHE = 'adsengine.veille_etape'

STATUTS_FINAUX = ('termine', 'echec', 'annule')
STATUTS_REQUETE_OUVERTS = ('a_faire', 'en_cours')


class LancementRefuse(Exception):
    """Refus de création/lancement (message FR + statut HTTP)."""

    def __init__(self, message_fr, statut_http=400):
        self.message_fr = message_fr
        self.statut_http = statut_http
        super().__init__(message_fr)


def _entier_positif(valeur, nom):
    if valeur in (None, ''):
        raise LancementRefuse(
            f'« {nom} » est obligatoire : aucun plafond n\'est inventé.')
    try:
        entier = int(valeur)
    except (TypeError, ValueError):
        raise LancementRefuse(f'« {nom} » doit être un entier.')
    if entier <= 0:
        raise LancementRefuse(f'« {nom} » doit être strictement positif.')
    return entier


def _seuil_pause_usage():
    from django.conf import settings
    try:
        return int(getattr(settings, 'VEILLE_PAUSE_USAGE_PCT', 75))
    except (TypeError, ValueError):
        return 75


def creer_decouverte(company, user, donnees):
    """Valide et crée une découverte + ses requêtes (mot-clé × pays).

    Refus 403 FR si la société n'est pas dans ``VEILLE_SOCIETES_AUTORISEES`` ;
    400 FR si un plafond manque (aucun défaut inventé), si un mot-clé dépasse
    100 caractères ou si un pays n'est pas couvert. Aucun appel réseau."""
    from . import ad_library_client as alc
    from . import veille_acces
    from .models import VeilleDecouverte, VeilleRequete

    if not veille_acces.societe_autorisee(company):
        raise LancementRefuse(
            veille_acces.MESSAGES_FR[veille_acces.NON_AUTORISE], 403)
    donnees = donnees or {}
    plafond_appels = _entier_positif(donnees.get('plafond_appels'),
                                     'plafond_appels')
    plafond_pages = _entier_positif(donnees.get('plafond_pages_par_requete'),
                                    'plafond_pages_par_requete')
    search_type = donnees.get('search_type') or 'KEYWORD_UNORDERED'
    if search_type not in alc.SEARCH_TYPES:
        raise LancementRefuse(f'Mode de recherche inconnu : {search_type}.')
    ad_active_status = donnees.get('ad_active_status') or 'ACTIVE'
    if ad_active_status not in alc.AD_ACTIVE_STATUS:
        raise LancementRefuse(
            f'Statut de diffusion inconnu : {ad_active_status}.')
    mots_cles = donnees.get('mots_cles')
    if not isinstance(mots_cles, list) or not mots_cles:
        raise LancementRefuse('Au moins un mot-clé avec ses pays est requis.')
    propres, couples = [], []
    for entree in mots_cles:
        if not isinstance(entree, dict):
            raise LancementRefuse('Mot-clé illisible.')
        try:
            texte = alc.valider_mot_cle(entree.get('texte'))
            pays = entree.get('pays') or []
            if not isinstance(pays, list) or not pays:
                raise alc.ParametreInvalide(
                    f'Aucun pays choisi pour « {texte} ».')
            codes = []
            for code in pays:
                code = alc.valider_pays(code)
                if code not in codes:
                    codes.append(code)
        except alc.ParametreInvalide as exc:
            raise LancementRefuse(exc.message_fr)
        propres.append({'texte': texte, 'pays': codes})
        for code in codes:
            if (texte, code) not in couples:
                couples.append((texte, code))

    cle = str(donnees.get('cle_idempotence') or '')[:64]
    with transaction.atomic():
        if cle:
            existante = VeilleDecouverte.objects.filter(
                company=company, cle_idempotence=cle).first()
            if existante is not None:
                return existante
        dec = VeilleDecouverte.objects.create(
            company=company, cree_par=user if getattr(user, 'pk', None)
            else None,
            mots_cles=propres, search_type=search_type,
            ad_active_status=ad_active_status,
            plafond_appels=plafond_appels,
            plafond_pages_par_requete=plafond_pages, cle_idempotence=cle)
        for ordre, (texte, code) in enumerate(couples):
            VeilleRequete.objects.create(
                company=company, decouverte=dec, ordre=ordre, mot_cle=texte,
                pays=code, search_type=search_type)
    return dec


def _envoyer_etape(dec, countdown=0):
    """Envoie l'étape ``dec.numero_etape`` (hors transaction de l'appelant)."""
    from .tasks import veille_etape
    veille_etape.apply_async(
        kwargs={'decouverte_id': dec.pk, 'company_id': dec.company_id,
                'job_id': dec.background_job_id, 'etape': dec.numero_etape},
        countdown=max(0, int(countdown)))


def lancer(dec, user):
    """Soumet la découverte comme job de fond (``core.jobs.submit`` : suivi de
    progression). La première étape porte ``etape=0``."""
    from core import jobs

    job = jobs.submit(JOB_KIND, NOM_TACHE, company=dec.company, user=user,
                      decouverte_id=dec.pk, etape=dec.numero_etape)
    dec.background_job = job
    dec.save(update_fields=['background_job', 'updated_at'])
    return job


def reprendre(dec):
    """Relance une découverte en pause/échec réseau : nouvelle chaîne d'étapes
    (le numéro d'étape avance, toute ancienne chaîne devient inerte). Ne
    contourne JAMAIS une pause de quota : l'étape attendra ``reprise_a``."""
    from .models import VeilleDecouverte

    with transaction.atomic():
        dec = VeilleDecouverte.objects.select_for_update().get(pk=dec.pk)
        if dec.statut in ('termine', 'annule'):
            raise LancementRefuse(
                'Cette découverte est close : elle ne peut pas reprendre.')
        dec.numero_etape += 1
        if dec.statut == 'echec':
            dec.statut = 'en_file'
        dec.save(update_fields=['numero_etape', 'statut', 'updated_at'])
    _envoyer_etape(dec)
    return dec


def annuler(dec):
    from .models import VeilleDecouverte

    with transaction.atomic():
        dec = VeilleDecouverte.objects.select_for_update().get(pk=dec.pk)
        if dec.statut not in STATUTS_FINAUX:
            dec.statut = 'annule'
            dec.termine_le = timezone.now()
            dec.save(update_fields=['statut', 'termine_le', 'updated_at'])
            dec.requetes.filter(statut__in=STATUTS_REQUETE_OUVERTS).update(
                curseur_after='')
    return dec


def _erreur(dec, code, message_fr, now):
    dec.erreurs = list(dec.erreurs or []) + [
        {'code': code, 'message_fr': message_fr, 'a': now.isoformat()}]


def _clore(dec, statut, now):
    dec.statut = statut
    dec.termine_le = now
    dec.requetes.filter(statut__in=STATUTS_REQUETE_OUVERTS).update(
        curseur_after='')
    dec.requetes.exclude(curseur_after='').update(curseur_after='')
    job = dec.background_job
    if job is not None:
        if statut == 'echec':
            job.marquer_echec((dec.erreurs or [{}])[-1].get('message_fr', ''))
        else:
            job.marquer_termine()


def _progression(dec):
    total = dec.requetes.count()
    if not total or dec.background_job is None:
        return
    faites = dec.requetes.exclude(statut__in=STATUTS_REQUETE_OUVERTS).count()
    dec.background_job.marquer_progression(int(100 * faites / total))


def executer_etape(decouverte_id, etape=None, *, http_client=None, now=None):
    """UNE étape : au plus UN appel HTTP. Renvoie ``{action, countdown,
    etape}`` où ``action`` ∈ ``continuer`` | ``attendre`` | ``fin`` |
    ``ignore`` ; l'appelant (la tâche) se relance si ``continuer``/``attendre``
    avec le numéro ``etape`` renvoyé."""
    from . import ad_library_client as alc
    from . import veille_acces
    from .models import VeilleDecouverte

    now = now or timezone.now()
    with transaction.atomic():
        dec = (VeilleDecouverte.objects.select_for_update(skip_locked=True)
               .filter(pk=decouverte_id).first())
        if dec is None:  # verrou tenu par une autre étape, ou disparue
            return {'action': 'ignore', 'countdown': 0, 'etape': etape}
        if etape is not None and int(etape) != dec.numero_etape:
            return {'action': 'ignore', 'countdown': 0, 'etape': etape}
        if dec.statut in STATUTS_FINAUX:
            return {'action': 'fin', 'countdown': 0, 'etape': etape}

        dec.numero_etape += 1
        champs = ['numero_etape', 'statut', 'reprise_a', 'erreurs',
                  'pauses_consecutives', 'dernier_usage_app', 'termine_le',
                  'appels_consommes', 'updated_at']

        # Pause de quota en cours : aucun appel avant ``reprise_a``.
        if dec.statut == 'en_pause_quota' and dec.reprise_a \
                and dec.reprise_a > now:
            reste = int((dec.reprise_a - now).total_seconds()) + 1
            dec.save(update_fields=champs)
            return {'action': 'attendre', 'countdown': reste,
                    'etape': dec.numero_etape}

        try:
            # AACQ36 — le mode rejeu (fixtures, réseau coupé) n'exige que la
            # société autorisée ; sinon l'accès d'aujourd'hui, inchangé.
            config = veille_acces.exiger_utilisable_ou_rejeu(dec.company)
        except veille_acces.AccesRefuse as exc:
            _erreur(dec, None, exc.message_fr, now)
            _clore(dec, 'echec', now)
            dec.save(update_fields=champs)
            return {'action': 'fin', 'countdown': 0, 'etape': dec.numero_etape}

        # Choix de la requête : la première ouverte, plafonds respectés.
        requete = None
        for candidate in dec.requetes.filter(
                statut__in=STATUTS_REQUETE_OUVERTS).order_by('ordre', 'id'):
            if candidate.pages_lues >= dec.plafond_pages_par_requete:
                candidate.statut = 'plafond'
                candidate.curseur_after = ''
                candidate.save(update_fields=['statut', 'curseur_after',
                                              'updated_at'])
                continue
            requete = candidate
            break
        if requete is None:
            _clore(dec, 'termine', now)
            dec.save(update_fields=champs)
            return {'action': 'fin', 'countdown': 0, 'etape': dec.numero_etape}
        if dec.appels_consommes >= dec.plafond_appels:
            dec.requetes.filter(statut__in=STATUTS_REQUETE_OUVERTS).update(
                statut='plafond', curseur_after='')
            _clore(dec, 'termine', now)
            dec.save(update_fields=champs)
            return {'action': 'fin', 'countdown': 0, 'etape': dec.numero_etape}

        dec.statut = 'en_cours'
        dec.reprise_a = None
        client = alc.AdLibraryClient(
            config.jeton, app_id=config.app_id, app_secret=config.app_secret,
            http_client=http_client)
        try:
            reponse = client.chercher(
                requete.mot_cle, requete.pays,
                search_type=requete.search_type,
                ad_active_status=dec.ad_active_status,
                after=requete.curseur_after or None)
        except alc.QuotaAtteint as exc:
            palier = PALIERS_PAUSE_S[min(dec.pauses_consecutives,
                                         len(PALIERS_PAUSE_S) - 1)]
            dec.pauses_consecutives += 1
            dec.appels_consommes += 1
            requete.appels += 1
            requete.statut = 'en_cours'
            requete.save(update_fields=['appels', 'statut', 'updated_at'])
            dec.statut = 'en_pause_quota'
            dec.reprise_a = now + datetime.timedelta(seconds=palier)
            if exc.usage:
                dec.dernier_usage_app = dict(exc.usage)
            _erreur(dec, exc.code, exc.message_fr, now)
            dec.save(update_fields=champs)
            return {'action': 'attendre', 'countdown': palier,
                    'etape': dec.numero_etape}
        except alc.AccesInvalide as exc:
            dec.appels_consommes += 1
            requete.appels += 1
            requete.save(update_fields=['appels', 'updated_at'])
            _erreur(dec, exc.code, exc.message_fr, now)
            _clore(dec, 'echec', now)
            dec.save(update_fields=champs)
            return {'action': 'fin', 'countdown': 0, 'etape': dec.numero_etape}
        except alc.AdLibraryErreur as exc:
            # Autre 4xx / paramètre / réseau : la requête est en erreur, le
            # lancement continue avec la suivante.
            dec.appels_consommes += 1
            requete.appels += 1
            requete.statut = 'erreur'
            requete.curseur_after = ''
            requete.message_erreur = veille_acces.masquer_secrets(
                exc.message_fr, config)[:255]
            requete.save(update_fields=['appels', 'statut', 'curseur_after',
                                        'message_erreur', 'updated_at'])
            _erreur(dec, exc.code, requete.message_erreur, now)
            dec.save(update_fields=champs)
            return {'action': 'continuer', 'countdown': COUNTDOWN_ETAPE_S,
                    'etape': dec.numero_etape}

        # Succès : ingestion (même transaction) puis statut de la requête.
        dec.save(update_fields=champs)
        numero_page = requete.pages_lues + 1
        ingerer_page(requete, reponse, numero_page)
        requete.refresh_from_db()
        dec.refresh_from_db()
        if not reponse.get('a_suivant'):
            requete.statut = ('vide' if numero_page == 1
                              and not reponse.get('pubs') else 'terminee')
            requete.curseur_after = ''
        elif requete.pages_lues >= dec.plafond_pages_par_requete:
            requete.statut = 'plafond'
            requete.curseur_after = ''
        else:
            requete.statut = 'en_cours'
        requete.save(update_fields=['statut', 'curseur_after', 'updated_at'])

        dec.pauses_consecutives = 0
        action, countdown = 'continuer', COUNTDOWN_ETAPE_S
        usage_pct = alc.pourcentage_usage(reponse.get('usage'))
        if usage_pct >= _seuil_pause_usage():
            palier = PALIERS_PAUSE_S[0]
            dec.statut = 'en_pause_quota'
            dec.reprise_a = now + datetime.timedelta(seconds=palier)
            dec.pauses_consecutives = 1
            _erreur(dec, None,
                    f'Usage de l\'application à {usage_pct} % : pause '
                    'préventive avant de reprendre.', now)
            action, countdown = 'attendre', palier
        elif not dec.requetes.filter(
                statut__in=STATUTS_REQUETE_OUVERTS).exists():
            _clore(dec, 'termine', now)
            action, countdown = 'fin', 0
        dec.save(update_fields=champs)
        _progression(dec)
        return {'action': action, 'countdown': countdown,
                'etape': dec.numero_etape}


# ═════════════════════════════════════════════════════════════════════════════
# VEIL17 — Verdict humain, étiquette de mesure, tirage de l'échantillon
# ═════════════════════════════════════════════════════════════════════════════
def _classes():
    from .models import VEILLE_CLASSES
    return {cle: libelle for cle, libelle, _b in VEILLE_CLASSES}


def _valider_classe(classe):
    classes = _classes()
    if not classe:
        raise LancementRefuse(
            'Choisir une classe : aucune classe n\'est posée par défaut.')
    if classe not in classes:
        raise LancementRefuse(f'Classe inconnue : {classe}.')
    return classe


def _valider_tri(valeur, *, obligatoire=False):
    if valeur in (None, ''):
        if obligatoire:
            raise LancementRefuse('Dropshipper : choisir oui, non ou '
                                  'incertain.')
        return None
    if valeur not in ('oui', 'non', 'incertain'):
        raise LancementRefuse('Dropshipper : oui, non ou incertain.')
    return valeur


def annonceurs_de(dec):
    """Annonceurs vus par une découverte (même société)."""
    from .models import VeilleAnnonceur
    return (VeilleAnnonceur.objects
            .filter(company_id=dec.company_id,
                    pubs_vues__requete__decouverte_id=dec.pk).distinct())


def poser_verdict_humain(annonceur, user, classe, dropshipper=None,
                         doublon_de=None):
    """Verdict HUMAIN : nouvelle ligne d'historique, devient le verdict
    courant ; prime sur règle et IA (qui ne l'écrasent jamais)."""
    from .models import VeilleAnnonceur, VeilleVerdict

    classe = _valider_classe(classe)
    dropshipper = _valider_tri(dropshipper)
    cible = None
    if classe == 'doublon' and doublon_de not in (None, ''):
        cible = VeilleAnnonceur.objects.filter(
            company_id=annonceur.company_id, pk=doublon_de).first()
        if cible is None or cible.pk == annonceur.pk:
            raise LancementRefuse('« Doublon de » : annonceur introuvable.')
    with transaction.atomic():
        ann = VeilleAnnonceur.objects.select_for_update().get(pk=annonceur.pk)
        verdict = VeilleVerdict.objects.create(
            company_id=ann.company_id, annonceur=ann, classe=classe,
            motif_fr=f'Décision humaine : {_classes()[classe].lower()}.',
            preuves=[], decide_par='humain', auteur=user,
            dropshipper=dropshipper or ann.dropshipper_probable,
            doublon_de=cible)
        ann.classe = classe
        ann.verdict_courant = verdict
        ann.doublon_de = cible if classe == 'doublon' else None
        champs = ['classe', 'verdict_courant', 'doublon_de', 'updated_at']
        if dropshipper:
            ann.dropshipper_probable = dropshipper
            ann.dropshipper_indices = []
            ann.dropshipper_decide_par = 'humain'
            champs += ['dropshipper_probable', 'dropshipper_indices',
                       'dropshipper_decide_par']
        ann.save(update_fields=champs)
    return ann


def poser_etiquette(annonceur, user, classe, dropshipper):
    """Étiquette de MESURE (mode aveugle) : ne touche PAS le verdict courant."""
    from .models import VeilleVerdict

    classe = _valider_classe(classe)
    dropshipper = _valider_tri(dropshipper, obligatoire=True)
    if not annonceur.jeu:
        raise LancementRefuse(
            "Cet annonceur n'appartient à aucun échantillon de mesure tiré.")
    return VeilleVerdict.objects.create(
        company_id=annonceur.company_id, annonceur=annonceur, classe=classe,
        motif_fr='Étiquette de mesure (humain, à l\'aveugle).', preuves=[],
        decide_par='humain', auteur=user, dropshipper=dropshipper,
        est_etiquette_mesure=True, jeu=annonceur.jeu)


def tirer_echantillon(dec, taille_etalonnage, taille_test, rng=None):
    """Tirage aléatoire GELÉ de deux jeux disjoints (étalonnage, test) parmi
    les annonceurs de la découverte. Idempotent : un second appel renvoie le
    tirage existant (``deja_tire``) sans jamais retirer."""
    import random

    from .models import VeilleAnnonceur, VeilleDecouverte

    taille_e = _entier_positif(taille_etalonnage, 'taille_etalonnage')
    taille_t = _entier_positif(taille_test, 'taille_test')
    with transaction.atomic():
        VeilleDecouverte.objects.select_for_update().get(pk=dec.pk)
        existant = VeilleAnnonceur.objects.filter(
            company_id=dec.company_id, jeu_decouverte_id=dec.pk)
        if existant.exists():
            return {
                'etalonnage': sorted(existant.filter(jeu='etalonnage')
                                     .values_list('id', flat=True)),
                'test': sorted(existant.filter(jeu='test')
                               .values_list('id', flat=True)),
                'deja_tire': True,
            }
        candidats = sorted(annonceurs_de(dec).filter(jeu__isnull=True)
                           .values_list('id', flat=True))
        if taille_e + taille_t > len(candidats):
            raise LancementRefuse(
                f'Échantillon impossible : {taille_e + taille_t} annonceurs '
                f'demandés, {len(candidats)} disponibles.')
        tirage = (rng or random.SystemRandom()).sample(
            candidats, taille_e + taille_t)
        etalonnage, test = sorted(tirage[:taille_e]), sorted(tirage[taille_e:])
        VeilleAnnonceur.objects.filter(pk__in=etalonnage).update(
            jeu='etalonnage', jeu_decouverte=dec)
        VeilleAnnonceur.objects.filter(pk__in=test).update(
            jeu='test', jeu_decouverte=dec)
    return {'etalonnage': etalonnage, 'test': test, 'deja_tire': False}


# ═════════════════════════════════════════════════════════════════════════════
# VEIL21/VEIL22 — Fiche de tri IA (liste blanche) et import d'un verdict IA
# ═════════════════════════════════════════════════════════════════════════════
VERSION_CONSIGNE = 'consigne-v1'
CHAMPS_FICHE = ('page_id', 'page_name', 'textes', 'titres', 'legendes',
                'domaines', 'debut_min', 'fin_max', 'payeurs')
MAX_TEXTES_FICHE = 10
CHAMPS_VERDICT_IA = ('page_id', 'classe', 'confiance', 'dropshipper',
                     'indices', 'modele', 'jetons_entree', 'jetons_sortie')


def lire_consigne():
    """La consigne versionnée UNIQUE (VEIL21 hors ligne et VEIL22 dans
    l'ERP)."""
    from pathlib import Path
    chemin = (Path(__file__).resolve().parent / 'data' / 'veille_consigne'
              / 'v1.md')
    return chemin.read_text(encoding='utf-8')


def fiche_tri(annonceur):
    """Fiche envoyée au tri IA : champs de la LISTE BLANCHE seulement (aucun
    jeton, aucune URL de snapshot, aucun identifiant interne)."""
    from .models import VeillePubVue

    pubs = list(VeillePubVue.objects.filter(
        company_id=annonceur.company_id, annonceur=annonceur).order_by('id'))

    def uniques(valeurs, limite=None):
        sortie = []
        for valeur in valeurs:
            valeur = str(valeur or '').strip()
            if valeur and valeur not in sortie:
                sortie.append(valeur)
            if limite and len(sortie) >= limite:
                break
        return sortie

    debuts = [pv.debut_diffusion for pv in pubs if pv.debut_diffusion]
    fins = [pv.fin_diffusion for pv in pubs if pv.fin_diffusion]
    fiche = {
        'page_id': annonceur.page_id,
        'page_name': annonceur.page_name,
        'textes': uniques((pv.extrait for pv in pubs), MAX_TEXTES_FICHE),
        'titres': uniques((t for pv in pubs for t in (pv.titres or [])),
                          MAX_TEXTES_FICHE),
        'legendes': uniques((pv.legende for pv in pubs), MAX_TEXTES_FICHE),
        'domaines': uniques(pv.domaine for pv in pubs),
        'debut_min': min(debuts).date().isoformat() if debuts else None,
        'fin_max': max(fins).date().isoformat() if fins else None,
        'payeurs': uniques(p for pv in pubs for p in (pv.payeurs or [])),
    }
    return {cle: fiche[cle] for cle in CHAMPS_FICHE}


def _entier_ou_none(valeur):
    if valeur in (None, ''):
        return None
    entier = int(valeur)
    if entier < 0:
        raise ValueError
    return entier


def importer_verdict_ia(company, ligne, *, version_consigne=VERSION_CONSIGNE):
    """Enregistre UN verdict IA ``{page_id, classe, confiance, dropshipper,
    indices, modele, jetons_entree, jetons_sortie}``. Renvoie ``(statut,
    message_fr)`` avec ``statut`` ∈ ``importe`` | ``ignore`` | ``erreur``.
    Une décision humaine n'est JAMAIS écrasée."""
    from .models import VeilleAnnonceur, VeilleVerdict

    if not isinstance(ligne, dict):
        return 'erreur', 'ligne illisible (objet JSON attendu)'
    modele = str(ligne.get('modele') or '').strip()
    if not modele:
        return 'erreur', '« modele » manquant'
    classe = ligne.get('classe')
    if classe not in _classes():
        return 'erreur', f'classe hors contrat : {classe!r}'
    dropshipper = ligne.get('dropshipper') or 'incertain'
    if dropshipper not in ('oui', 'non', 'incertain'):
        return 'erreur', f'dropshipper invalide : {dropshipper!r}'
    try:
        confiance = (None if ligne.get('confiance') in (None, '')
                     else float(ligne['confiance']))
        jetons_entree = _entier_ou_none(ligne.get('jetons_entree'))
        jetons_sortie = _entier_ou_none(ligne.get('jetons_sortie'))
    except (TypeError, ValueError):
        return 'erreur', 'confiance ou jetons illisibles'
    if confiance is not None and not 0 <= confiance <= 1:
        return 'erreur', 'confiance hors de 0..1'
    indices = [
        {'champ': str(i.get('champ', ''))[:80],
         'valeur': str(i.get('valeur', ''))[:200]}
        for i in (ligne.get('indices') or []) if isinstance(i, dict)]
    page_id = str(ligne.get('page_id') or '').strip()
    with transaction.atomic():
        ann = (VeilleAnnonceur.objects.select_for_update(of=('self',))
               .select_related('verdict_courant')
               .filter(company=company, page_id=page_id).first())
        if ann is None:
            return 'erreur', f'page_id inconnu : {page_id!r}'
        if ann.verdict_courant and ann.verdict_courant.decide_par == 'humain':
            return 'ignore', 'décision humaine conservée'
        motif = str(ligne.get('motif_fr') or '').strip()[:500] or (
            f'Tri IA ({modele}) : {_classes()[classe].lower()}.')
        verdict = VeilleVerdict.objects.create(
            company=company, annonceur=ann, classe=classe, motif_fr=motif,
            preuves=[], decide_par='ia', modele=modele[:80],
            version_consigne=version_consigne, jetons_entree=jetons_entree,
            jetons_sortie=jetons_sortie, confiance=confiance,
            dropshipper=dropshipper, dropshipper_indices=indices)
        ann.classe = classe
        ann.verdict_courant = verdict
        champs = ['classe', 'verdict_courant', 'updated_at']
        if ann.dropshipper_decide_par != 'humain':
            ann.dropshipper_probable = dropshipper
            ann.dropshipper_indices = indices
            ann.dropshipper_decide_par = 'ia'
            champs += ['dropshipper_probable', 'dropshipper_indices',
                       'dropshipper_decide_par']
        ann.save(update_fields=champs)
    return 'importe', ''
