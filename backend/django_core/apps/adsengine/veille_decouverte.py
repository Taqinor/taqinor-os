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
import logging
import re
from collections import Counter

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
}
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
        nb = 3 if '.'.join(labels[-2:]) in SUFFIXES_DOUBLES else 2
        if len(labels) < nb:
            continue
        return '.'.join(labels[-nb:])
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
        dt = datetime.datetime(jour.year, jour.month, jour.day)
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
