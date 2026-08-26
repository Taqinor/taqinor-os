"""VAO18 — l'enrichissement du détail, À LA DEMANDE et JAMAIS EN MASSE.

La page de détail d'un avis porte ce que la ligne de résultat ne dit pas :
l'estimation (MAD TTC), la caution provisoire, les lots, le marqueur PME et le
lien du DCE avec sa taille.

**Pourquoi « à la demande » est ici une contrainte technique, pas une
préférence.** Ce point de terminaison **se bloque par intermittence** : deux
délais de **110 secondes** ont été observés le 2026-08-01. L'appeler pour 34
avis d'affilée, c'est une collecte qui dure une heure et finit en échec — et
un pare-feu qui nous voit marteler. Il n'est donc appelé que **sur clic
utilisateur**, un avis à la fois, avec délai d'attente, 2-3 tentatives à repli
exponentiel, et un échec PROPRE.

**Échec propre = l'avis reste intact.** Un détail indisponible ne doit jamais
effacer ce que la collecte a déjà su lire, ni ce qu'un humain a saisi : en cas
d'échec, ``Detail.donnees`` est VIDE (aucune clé) et le message
« Détail indisponible, réessayer » remonte à l'écran. Un dictionnaire de clés
vides, lui, écraserait l'avis — c'est exactement le bug que cette règle évite.

**Le téléchargement du DCE n'est PAS dans le périmètre.** Le flux ATEXO est
multi-étapes et comporte probablement une étape d'identification (non
vérifié) ; le fichier de risque promet d'ailleurs « aucun téléchargement de
DCE en masse ». On AFFICHE le lien et sa taille, et c'est l'humain qui clique.

Ce module est la seconde et dernière frontière réseau du paquet.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from . import ErreurPortail
from .client import (
    CHEMIN, ClientRefuse, GardeNeutre, PortailIndisponible, ReponseInattendue,
    _executer, exiger_source_collectable, user_agent,
)
from .parser import ANALYSEUR, lire_date_heure, normaliser, sans_accents

logger = logging.getLogger(__name__)

#: La page de détail, en MINUSCULES comme la page de recherche (mesuré : une
#: majuscule sur ``entreprise.`` rend un 404).
PAGE_DETAIL = 'entreprise.EntrepriseDetailConsultation'

#: 45 s : dans la fourchette 30-60 s demandée. Les deux blocages mesurés
#: duraient 110 s — couper à 45 s, c'est refuser d'attendre deux minutes pour
#: rien devant un utilisateur qui vient de cliquer.
DELAI_DETAIL = 45.0
DELAI_CONNEXION = 10.0

#: 3 tentatives, repli exponentiel 2 s puis 4 s. Au-delà, c'est du martèlement.
TENTATIVES = 3
REPLI_INITIAL = 2.0

#: Le message montré à l'utilisateur. Il dit quoi faire (réessayer), il ne
#: laisse pas croire que l'avis n'a pas de détail.
MESSAGE_INDISPONIBLE = 'Détail indisponible, réessayer.'

_MONTANT_RE = re.compile(r'(\d[\d\s .]*(?:,\d{1,2})?)')
_TAILLE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(K|M|G)?o', re.IGNORECASE)
_LIEN_DCE_RE = re.compile(r'TelechargementDce|telechargerDce|dce',
                          re.IGNORECASE)


@dataclass
class Lot:
    """Un lot de la consultation. ``numero`` est une CHAÎNE : le portail
    écrit « 1 », « 2 » mais aussi « 1A » ou « Lot unique »."""

    numero: str = ''
    intitule: str = ''
    estimation: Decimal | None = None
    caution: Decimal | None = None


@dataclass
class Detail:
    """Le résultat d'un enrichissement — succès ou échec, toujours explicite.

    ``donnees`` ne contient QUE des clés effectivement lues (sous-ensemble de
    ``services.CHAMPS_RECTIFIABLES``) : sur échec elle est vide, donc rien
    n'est écrasé côté avis.
    """

    disponible: bool = False
    message: str = ''
    donnees: dict = field(default_factory=dict)
    lots: list = field(default_factory=list)
    reserve_pme: bool | None = None
    lien_dce: str = ''
    taille_dce: str = ''
    tentatives: int = 0
    cause: str = ''


# ─────────────────────────────────────────────────────────────────────────
# Lecture de la page (fonctions pures — testables sans réseau)
# ─────────────────────────────────────────────────────────────────────────


def lire_montant(texte):
    """« 2 450 000,00 MAD TTC » → ``Decimal('2450000.00')``, sinon ``None``.

    Format marocain : espaces (ou points) pour les milliers, virgule pour les
    décimales. Rendre un ``float`` ici ferait entrer des arrondis binaires
    dans un montant public — on reste en ``Decimal``, comme les colonnes.
    """
    trouve = _MONTANT_RE.search((texte or '').replace('\xa0', ' '))
    if not trouve:
        return None
    brut = (trouve.group(1).replace(' ', '').replace('.', '').replace(',', '.'))
    try:
        return Decimal(brut)
    except (InvalidOperation, ValueError):
        return None


def _valeur_du_libelle(soup, *libelles):
    """La cellule qui suit un libellé de la table de détail.

    Le portail présente le détail en paires ``<td>libellé</td><td>valeur</td>``.
    On compare sans accents et sur un PRÉFIXE : « Estimation », « Estimation
    du marché » et « Estimation (MAD) » doivent tous répondre.
    """
    cibles = [sans_accents(libelle) for libelle in libelles]
    for cellule in soup.find_all(['td', 'th', 'dt']):
        texte = sans_accents(normaliser(cellule.get_text(' ')))
        if not any(texte.startswith(cible) for cible in cibles):
            continue
        voisine = cellule.find_next_sibling(['td', 'dd'])
        if voisine is not None:
            valeur = normaliser(voisine.get_text(' '))
            if valeur:
                return valeur
    return ''


def _lire_lots(soup):
    lots = []
    for ligne in soup.find_all('tr'):
        numero = ligne.find(class_='lot-numero')
        if numero is None:
            continue
        intitule = ligne.find(class_='lot-intitule')
        estimation = ligne.find(class_='lot-estimation')
        caution = ligne.find(class_='lot-caution')
        lots.append(Lot(
            numero=normaliser(numero.get_text(' ')),
            intitule=normaliser(intitule.get_text(' ')) if intitule else '',
            estimation=(lire_montant(estimation.get_text(' '))
                        if estimation else None),
            caution=lire_montant(caution.get_text(' ')) if caution else None,
        ))
    return lots


def _lire_pme(soup):
    """``True``/``False``/``None`` — ``None`` = la page ne le dit pas.

    Le troisième état compte : « on ne sait pas » n'est pas « non réservé ».
    Afficher « non réservé aux PME » sur une page muette serait une invention.
    """
    marqueur = soup.find(class_='marqueur-pme')
    texte = normaliser(marqueur.get_text(' ')) if marqueur is not None else ''
    if not texte:
        texte = _valeur_du_libelle(soup, 'reserve aux pme', 'reserve pme')
    if not texte:
        return None
    reponse = sans_accents(texte)
    if reponse.startswith('oui'):
        return True
    if reponse.startswith('non'):
        return False
    return None


def _lire_dce(soup):
    lien = soup.find('a', href=_LIEN_DCE_RE)
    if lien is None:
        return '', ''
    taille = soup.find(class_='taille-dce')
    if taille is None:
        voisin = lien.find_next(string=_TAILLE_RE)
        texte_taille = normaliser(str(voisin)) if voisin else ''
    else:
        texte_taille = normaliser(taille.get_text(' '))
    return lien.get('href', ''), texte_taille.strip('()')


def analyser_detail(html):
    """La page de détail → un ``Detail`` renseigné (aucune E/S).

    Lève ``ReponseInattendue`` si la page n'a aucune des ancres attendues :
    une page de détail muette est une DÉRIVE, pas un avis sans montant.
    """
    soup = BeautifulSoup(html or '', ANALYSEUR)
    detail = Detail(disponible=True)

    estimation = lire_montant(
        _valeur_du_libelle(soup, 'estimation', 'montant estime'))
    if estimation is not None:
        detail.donnees['montant_estime'] = estimation

    caution = lire_montant(_valeur_du_libelle(soup, 'caution'))
    if caution is not None:
        detail.donnees['caution_provisoire'] = caution

    ouverture = lire_date_heure(
        _valeur_du_libelle(soup, "date d'ouverture", 'ouverture des plis'))
    if ouverture is not None:
        detail.donnees['date_ouverture'] = ouverture

    limite = lire_date_heure(
        _valeur_du_libelle(soup, 'date limite', 'remise des plis'))
    if limite is not None:
        detail.donnees['date_limite_remise'] = limite

    detail.lots = _lire_lots(soup)
    if len(detail.lots) == 1:
        detail.donnees['lot'] = (detail.lots[0].numero or '')[:160]

    detail.reserve_pme = _lire_pme(soup)
    detail.lien_dce, detail.taille_dce = _lire_dce(soup)

    if not (detail.donnees or detail.lots or detail.lien_dce):
        raise ReponseInattendue(
            "La page de détail n'a aucune des ancres attendues (estimation, "
            'caution, lots, DCE) : le portail a probablement changé de forme. '
            "C'est une DÉRIVE à signaler, pas un avis sans détail.")
    return detail


# ─────────────────────────────────────────────────────────────────────────
# La récupération — sur CLIC, une seule consultation à la fois
# ─────────────────────────────────────────────────────────────────────────


def url_de_detail(url_base, ref_consultation, org_acronyme):
    """L'URL de la page de détail, construite depuis la source."""
    racine = (url_base or '').rstrip('/')
    return (f'{racine}/{CHEMIN}?page={PAGE_DETAIL}'
            f'&refConsultation={ref_consultation}'
            f'&orgAcronyme={org_acronyme}')


def enrichir(source, ref_consultation, org_acronyme, *, garde=None,
             transport=None, dormir=time.sleep, tentatives=TENTATIVES):
    """Va chercher le détail d'UN avis. Ne lève JAMAIS sur une panne réseau.

    Rend toujours un ``Detail`` : ``disponible=False`` + message français
    quand ça n'a pas marché, ``donnees`` restant VIDE pour que l'avis existant
    ne soit jamais dégradé par un échec.

    Un refus du portail (403) N'EST PAS réessayé : la règle d'arrêt définitif
    de VAO16 vaut ici aussi.

    ``dormir`` est injectable pour que les tests ne dorment pas réellement.
    """
    garde = garde or GardeNeutre()
    try:
        url_base = exiger_source_collectable(source)
    except ErreurPortail as erreur:
        return Detail(disponible=False, message=str(erreur),
                      cause=type(erreur).__name__)

    url = url_de_detail(url_base, ref_consultation, org_acronyme)
    entetes = {'User-Agent': user_agent(), 'Accept': 'text/html',
               'Accept-Language': 'fr'}
    delai = httpx.Timeout(DELAI_DETAIL, connect=DELAI_CONNEXION)
    attente = REPLI_INITIAL
    derniere = None

    with httpx.Client(headers=entetes, timeout=delai, follow_redirects=True,
                      transport=transport) as client:
        for numero in range(1, max(1, tentatives) + 1):
            try:
                reponse = _executer(lambda: client.get(url), url, garde,
                                    f'détail {ref_consultation}')
                detail = analyser_detail(reponse.text)
                detail.tentatives = numero
                return detail
            except ClientRefuse as erreur:
                # Refus = arrêt définitif. Réessayer serait du martèlement, et
                # changer d'identité serait du maquillage : ni l'un ni l'autre.
                logger.warning('veille_ao.portail : détail refusé — %s', erreur)
                return Detail(disponible=False, message=MESSAGE_INDISPONIBLE,
                              tentatives=numero, cause=type(erreur).__name__)
            except (PortailIndisponible, ReponseInattendue) as erreur:
                derniere = erreur
                logger.warning(
                    'veille_ao.portail : détail %s indisponible (tentative '
                    '%s/%s) — %s', ref_consultation, numero, tentatives, erreur)
                if numero < tentatives:
                    dormir(attente)
                    attente *= 2

    return Detail(disponible=False, message=MESSAGE_INDISPONIBLE,
                  tentatives=max(1, tentatives),
                  cause=type(derniere).__name__ if derniere else '')


__all__ = [
    'DELAI_DETAIL', 'Detail', 'Lot',
    'MESSAGE_INDISPONIBLE', 'PAGE_DETAIL', 'REPLI_INITIAL', 'TENTATIVES',
    'analyser_detail', 'enrichir', 'lire_montant', 'url_de_detail',
]
