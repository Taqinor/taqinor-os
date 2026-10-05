"""VEIL20 — Règles gratuites (zéro jeton, zéro réseau) : classes, doublons,
indices dropshipper.

Champs utilisables : SEULEMENT ceux d'``ads_archive`` stockés par la découverte
(texte, titres, légende/domaine, nom de Page, dates, payeur UE) — ni catégorie,
ni abonnés, ni âge de Page. Lexiques versionnés
``data/veille_lexiques/{fr,en,de,es,it,nl}.json`` (vêtements + chaussures +
sacs = D-VEIL-3) et liste MODIFIABLE des places de marché / géants
``data/veille_lexiques/places_de_marche.json`` (D-VEIL-1).

Règles (déterministes : même entrée → même sortie) :

1. Page ou domaine de la liste → ``place_de_marche`` (sans IA).
2. Aucun vocabulaire produit + vocabulaire éditorial/appli/service →
   ``pas_vendeur`` ; produit hors périmètre seul → ``hors_sujet``. Une règle de
   mot-clé SEULE n'exclut jamais : il faut au moins deux termes distincts ou
   deux pubs distinctes, sinon ``incertain``.
3. Vocabulaire produit + signal de vente + domaine propre → ``vendeur``.
4. Doublons : même domaine propre, même payeur UE, ou même texte normalisé sur
   au moins deux ``page_id`` → ``doublon`` (de la première Page vue).
5. Indices dropshipper (un SCORE, jamais un verdict seul) : remise ≥ 50 %,
   urgence contredite par la durée de diffusion, nom de Page générique,
   extension ``.shop``/``.store``, texte identique sur plusieurs Pages.
   Deux indices ou plus → ``oui`` ; sinon ``incertain``.
6. Tout le reste → ``incertain`` (pour l'IA).

Chaque verdict porte un motif FR et des preuves ``{champ, valeur,
ad_archive_id}``. Une décision humaine (ou IA) n'est JAMAIS écrasée par une
règle.
"""
from __future__ import annotations

import datetime
import functools
import json
import re
import unicodedata
from pathlib import Path

VERSION_REGLES = 'regles-v1'
DOSSIER_LEXIQUES = Path(__file__).resolve().parent / 'data' / 'veille_lexiques'
LANGUES = ('fr', 'en', 'de', 'es', 'it', 'nl')
CATEGORIES = ('produit', 'hors_sujet', 'editorial', 'commerce', 'urgence',
              'nom_generique')
SEUIL_REMISE_PCT = 50
DUREE_URGENCE_CONTREDITE = datetime.timedelta(days=14)
LONGUEUR_MIN_TEXTE_DOUBLON = 20
LONGUEUR_PREUVE = 160


def normaliser(texte):
    """Minuscules, sans accents, apostrophes droites, espaces réduits."""
    texte = str(texte or '').replace('’', "'").replace('‘', "'")
    decompose = unicodedata.normalize('NFKD', texte)
    sans_accents = ''.join(c for c in decompose
                           if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sans_accents.lower()).strip()


@functools.lru_cache(maxsize=1)
def lexiques():
    """Union des lexiques des six langues, par catégorie (normalisée)."""
    union = {cat: set() for cat in CATEGORIES}
    versions = {}
    for langue in LANGUES:
        donnees = json.loads((DOSSIER_LEXIQUES / f'{langue}.json').read_text(
            encoding='utf-8'))
        versions[langue] = donnees.get('version')
        for cat in CATEGORIES:
            union[cat].update(normaliser(t) for t in donnees.get(cat, []))
    return {cat: tuple(sorted(termes)) for cat, termes in union.items()}


@functools.lru_cache(maxsize=1)
def liste_places_de_marche():
    donnees = json.loads((DOSSIER_LEXIQUES / 'places_de_marche.json')
                         .read_text(encoding='utf-8'))
    return {
        'page_ids': frozenset(str(p) for p in donnees.get('page_ids', [])),
        'domaines': frozenset(d.lower() for d in donnees.get('domaines', [])),
        'racines': frozenset(r.lower() for r in donnees.get('racines', [])),
        'sociaux': frozenset(d.lower() for d in
                             donnees.get('domaines_sociaux', [])),
    }


@functools.lru_cache(maxsize=4096)
def _motif_terme(terme):
    if re.fullmatch(r"[\w' -]+", terme):
        return re.compile(r'(?<!\w)' + re.escape(terme) + r'(?!\w)')
    return re.compile(re.escape(terme))


def _trouver(categorie, texte):
    """Termes de ``categorie`` présents dans ``texte`` (normalisé)."""
    return [t for t in lexiques()[categorie]
            if t and _motif_terme(t).search(texte)]


def est_place_de_marche_domaine(domaine):
    if not domaine:
        return False
    liste = liste_places_de_marche()
    domaine = domaine.lower()
    return (domaine in liste['domaines']
            or domaine.split('.')[0] in liste['racines'])


def est_domaine_social(domaine):
    return bool(domaine) and domaine.lower() in liste_places_de_marche()[
        'sociaux']


def _extrait(valeur):
    return str(valeur or '')[:LONGUEUR_PREUVE]


def _preuve(champ, valeur, ad_archive_id):
    return {'champ': champ, 'valeur': _extrait(valeur),
            'ad_archive_id': str(ad_archive_id or '')}


def _pubs_triees(fiche):
    return sorted(fiche.get('pubs') or [],
                  key=lambda p: str(p.get('ad_archive_id') or ''))


def _sources(fiche):
    """(champ, texte brut, ad_archive_id) pour chaque texte lisible."""
    sources = []
    for pub in _pubs_triees(fiche):
        ad_id = pub.get('ad_archive_id')
        if pub.get('texte'):
            sources.append(('ad_creative_bodies', pub['texte'], ad_id))
        for titre in pub.get('titres') or []:
            sources.append(('ad_creative_link_titles', titre, ad_id))
    return sources


def _occurrences(categorie, sources):
    occ = []
    for champ, brut, ad_id in sources:
        for terme in _trouver(categorie, normaliser(brut)):
            occ.append((terme, champ, brut, ad_id))
    return occ


def _fort(occ):
    """Une règle de mot-clé SEULE n'exclut jamais : ≥ 2 termes distincts ou
    ≥ 2 pubs distinctes."""
    return (len({o[0] for o in occ}) >= 2
            or len({o[3] for o in occ}) >= 2)


def _remises(texte):
    return [int(v) for v in re.findall(r'(\d{2,3})\s?%', texte or '')
            if SEUIL_REMISE_PCT <= int(v) < 100]


def indices_dropshipper(fiche, *, textes_multi_pages=frozenset(),
                        maintenant=None):
    """Liste triée d'indices ``{champ, valeur}`` (jamais un verdict seul)."""
    indices = []
    pubs = _pubs_triees(fiche)
    for pub in pubs:
        remises = _remises(pub.get('texte'))
        if remises:
            indices.append({'champ': 'ad_creative_bodies',
                            'valeur': f'remise de {max(remises)} %'})
            break
    for pub in pubs:
        urgences = _trouver('urgence', normaliser(pub.get('texte')))
        debut = pub.get('debut')
        if urgences and debut is not None:
            fin = pub.get('fin') or maintenant
            if fin is not None and fin - debut >= DUREE_URGENCE_CONTREDITE:
                indices.append({
                    'champ': 'ad_delivery_start_time',
                    'valeur': f'« {urgences[0]} » diffusé depuis le '
                              f'{debut.date().isoformat()}'})
                break
    jetons = [j for j in re.split(r'[^a-z0-9]+',
                                  normaliser(fiche.get('page_name'))) if j]
    if jetons and all(j in lexiques()['nom_generique'] for j in jetons):
        indices.append({'champ': 'page_name',
                        'valeur': _extrait(fiche.get('page_name'))})
    for pub in pubs:
        domaine = (pub.get('domaine') or '').lower()
        if domaine.endswith('.shop') or domaine.endswith('.store'):
            indices.append({'champ': 'ad_creative_link_captions',
                            'valeur': domaine})
            break
    for pub in pubs:
        if normaliser(pub.get('texte')) in textes_multi_pages:
            indices.append({'champ': 'ad_creative_bodies',
                            'valeur': 'texte identique sur plusieurs Pages'})
            break
    return indices


def classer(fiche, *, textes_multi_pages=frozenset(), maintenant=None):
    """Verdict de règle pour UNE fiche : ``{classe, motif_fr, preuves,
    dropshipper: {probable, indices}}``. Pur, déterministe, sans réseau."""
    pubs = _pubs_triees(fiche)
    premier = pubs[0].get('ad_archive_id') if pubs else ''
    indices = indices_dropshipper(fiche, textes_multi_pages=textes_multi_pages,
                                  maintenant=maintenant)
    dropshipper = {'probable': 'oui' if len(indices) >= 2 else 'incertain',
                   'indices': indices}

    def resultat(classe, motif, preuves):
        return {'classe': classe, 'motif_fr': motif, 'preuves': preuves,
                'dropshipper': dropshipper}

    liste = liste_places_de_marche()
    if str(fiche.get('page_id') or '') in liste['page_ids']:
        return resultat('place_de_marche',
                        'Page de la liste des places de marché et géants.',
                        [_preuve('page_id', fiche.get('page_id'), premier)])
    for pub in pubs:
        if est_place_de_marche_domaine(pub.get('domaine')):
            return resultat(
                'place_de_marche',
                'Domaine de la liste des places de marché et géants.',
                [_preuve('ad_creative_link_captions',
                         pub.get('legende') or pub.get('domaine'),
                         pub.get('ad_archive_id'))])

    sources = _sources(fiche)
    if fiche.get('page_name'):
        sources.append(('page_name', fiche['page_name'], premier))
    produit = _occurrences('produit', sources)
    hors = _occurrences('hors_sujet', sources)
    editorial = _occurrences('editorial', sources)
    commerce = _occurrences('commerce', sources)
    domaine_propre = next(
        (p for p in pubs if p.get('domaine')
         and not est_domaine_social(p.get('domaine'))), None)

    def preuves_de(occ, n=2):
        vues, sortie = set(), []
        for terme, champ, brut, ad_id in occ:
            if terme in vues:
                continue
            vues.add(terme)
            sortie.append(_preuve(champ, brut, ad_id))
            if len(sortie) >= n:
                break
        return sortie

    if produit:
        if commerce and domaine_propre is not None:
            return resultat(
                'vendeur',
                'Pubs de vêtements, chaussures ou sacs avec un signal de '
                'vente et un domaine propre.',
                preuves_de(produit, 1) + preuves_de(commerce, 1) + [
                    _preuve('ad_creative_link_captions',
                            domaine_propre.get('domaine'),
                            domaine_propre.get('ad_archive_id'))])
        return resultat(
            'incertain',
            'Vocabulaire produit sans signal de vente ou sans domaine '
            'propre : à trier par l\'IA.', preuves_de(produit, 2))
    if editorial and _fort(editorial) and not (hors and commerce):
        return resultat(
            'pas_vendeur',
            'Aucun vêtement, chaussure ni sac ; vocabulaire éditorial, '
            'd\'application ou de service.', preuves_de(editorial))
    if hors and _fort(hors):
        return resultat(
            'hors_sujet',
            'Produits hors périmètre (ni vêtements, ni chaussures, ni sacs).',
            preuves_de(hors))
    preuves = preuves_de(editorial + hors, 2)
    return resultat('incertain',
                    'Indices insuffisants pour une règle : à trier par '
                    'l\'IA.', preuves)


def detecter_doublons(fiches):
    """``(doublons, textes_multi_pages)`` : ``doublons[page_id] = (page_id
    d'origine, preuve)`` — l'origine est la PREMIÈRE fiche de la liste qui
    partage le domaine propre, le payeur UE ou le texte normalisé."""
    premier_par_cle = {}
    pages_par_texte = {}
    doublons = {}
    for fiche in fiches:
        page_id = str(fiche.get('page_id'))
        for pub in _pubs_triees(fiche):
            texte = normaliser(pub.get('texte'))
            if len(texte) >= LONGUEUR_MIN_TEXTE_DOUBLON:
                pages_par_texte.setdefault(texte, set()).add(page_id)
    textes_multi = frozenset(t for t, pages in pages_par_texte.items()
                             if len(pages) >= 2)
    for fiche in fiches:
        page_id = str(fiche.get('page_id'))
        cles = []
        for pub in _pubs_triees(fiche):
            ad_id = pub.get('ad_archive_id')
            domaine = (pub.get('domaine') or '').lower()
            if domaine and not est_domaine_social(domaine) \
                    and not est_place_de_marche_domaine(domaine):
                cles.append((('domaine', domaine),
                             _preuve('ad_creative_link_captions',
                                     pub.get('legende') or domaine, ad_id)))
            for payeur in pub.get('payeurs') or []:
                cles.append((('payeur', normaliser(payeur)),
                             _preuve('beneficiary_payers', payeur, ad_id)))
            texte = normaliser(pub.get('texte'))
            if texte in textes_multi:
                cles.append((('texte', texte),
                             _preuve('ad_creative_bodies', pub.get('texte'),
                                     ad_id)))
        for cle, preuve in cles:
            origine = premier_par_cle.setdefault(cle, page_id)
            if origine != page_id and page_id not in doublons:
                doublons[page_id] = (origine, preuve)
    return doublons, textes_multi


def classer_tout(fiches, *, maintenant=None):
    """Verdicts de règle pour une liste ordonnée de fiches :
    ``{page_id: resultat}`` (``resultat['doublon_de']`` = page_id ou None)."""
    doublons, textes_multi = detecter_doublons(fiches)
    resultats = {}
    for fiche in fiches:
        page_id = str(fiche.get('page_id'))
        res = classer(fiche, textes_multi_pages=textes_multi,
                      maintenant=maintenant)
        res['doublon_de'] = None
        if page_id in doublons and res['classe'] != 'place_de_marche':
            origine, preuve = doublons[page_id]
            res['classe'] = 'doublon'
            res['motif_fr'] = ('Même domaine, même payeur ou même texte '
                               'qu\'une autre Page déjà vue.')
            res['preuves'] = [preuve]
            res['doublon_de'] = origine
        resultats[page_id] = res
    return resultats


# ── Application en base (aucun appel réseau) ────────────────────────────────
def fiche_annonceur(annonceur):
    """Fiche de règles d'un annonceur, depuis ses pubs vues stockées."""
    from .models import VeillePubVue

    pubs = VeillePubVue.objects.filter(
        company_id=annonceur.company_id, annonceur=annonceur).order_by('id')
    vues, sortie = set(), []
    for pv in pubs:
        if pv.ad_archive_id in vues:
            continue
        vues.add(pv.ad_archive_id)
        sortie.append({
            'ad_archive_id': pv.ad_archive_id, 'texte': pv.extrait,
            'titres': list(pv.titres or []), 'legende': pv.legende,
            'domaine': pv.domaine, 'payeurs': list(pv.payeurs or []),
            'debut': pv.debut_diffusion, 'fin': pv.fin_diffusion,
        })
    return {'page_id': annonceur.page_id, 'page_name': annonceur.page_name,
            'pubs': sortie}


def appliquer_regles(decouverte, *, maintenant=None):
    """Applique les règles aux annonceurs d'une découverte. Un verdict
    courant HUMAIN ou IA n'est jamais écrasé ; un verdict de règle identique
    n'est pas redoublé (idempotent). Renvoie ``{classe: nombre}``."""
    from django.db import transaction
    from django.utils import timezone

    from .models import VeilleAnnonceur, VeilleVerdict
    from .veille_decouverte import annonceurs_de

    maintenant = maintenant or timezone.now()
    annonceurs = list(annonceurs_de(decouverte).select_related(
        'verdict_courant').order_by('id'))
    par_page = {a.page_id: a for a in annonceurs}
    resultats = classer_tout([fiche_annonceur(a) for a in annonceurs],
                             maintenant=maintenant)
    compte = {}
    with transaction.atomic():
        for page_id, res in resultats.items():
            ann = par_page[page_id]
            courant = ann.verdict_courant
            if courant is not None and courant.decide_par in ('humain', 'ia'):
                continue
            doublon = par_page.get(res['doublon_de']) if res['doublon_de'] \
                else None
            if (courant is not None and courant.classe == res['classe']
                    and courant.motif_fr == res['motif_fr']
                    and list(courant.preuves or []) == res['preuves']
                    and courant.doublon_de_id == getattr(doublon, 'pk', None)):
                compte[res['classe']] = compte.get(res['classe'], 0) + 1
                continue
            verdict = VeilleVerdict.objects.create(
                company_id=ann.company_id, annonceur=ann,
                classe=res['classe'], motif_fr=res['motif_fr'],
                preuves=res['preuves'], decide_par='regle',
                version_consigne=VERSION_REGLES,
                dropshipper=res['dropshipper']['probable'],
                dropshipper_indices=res['dropshipper']['indices'],
                doublon_de=doublon)
            champs = {'classe': res['classe'], 'verdict_courant': verdict,
                      'doublon_de': doublon}
            if ann.dropshipper_decide_par not in ('humain', 'ia'):
                champs.update(
                    dropshipper_probable=res['dropshipper']['probable'],
                    dropshipper_indices=res['dropshipper']['indices'],
                    dropshipper_decide_par='regle')
            VeilleAnnonceur.objects.filter(pk=ann.pk).update(**champs)
            compte[res['classe']] = compte.get(res['classe'], 0) + 1
    return compte
