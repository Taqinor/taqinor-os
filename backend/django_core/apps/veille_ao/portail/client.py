"""VAO16 — le client HTTP du portail : la recette VÉRIFIÉE EN MAIN, rien d'autre.

Ce module est **l'une des deux seules frontières réseau** du paquet (l'autre
est ``detail.py``). Tout ce qu'il fait a été mesuré le 2026-08-01 ; rien n'y
est ajouté « au cas où ».

La séquence, en trois étapes
----------------------------
1. ``GET index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours``
   ``&searchAnnCons&keyWord=<mot-clé>`` — la réponse porte le total dans
   ``span#ctl0_CONTENU_PAGE_resultSearch_nombreElement`` et les **10 premières
   lignes seulement** (plafond d'affichage du portail).
2. Si le total dépasse 10 : **POST sur la MÊME URL et la MÊME jarre de
   cookies**, rejouant le postback PRADO (``PRADO_PAGESTATE`` déséchappé,
   ``PRADO_POSTBACK_TARGET=ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop``,
   ``PRADO_POSTBACK_PARAMETER`` vide, ``…$listePageSizeTop=500``) → toutes les
   lignes en une seule réponse (vérifié : les 34 résultats de « solaire »).
3. Si le total dépasse 500 : re-POST avec le **NOUVEAU** pagestate de la
   réponse précédente et ``…$numPageTop=N``.

Deux contraintes techniques mesurées, faciles à casser sans le savoir :
``page=entreprise.`` est en **minuscules** (une majuscule rend un 404), et la
paire GET→POST doit partager **une seule jarre de cookies** (PHPSESSID +
SERVERID collant) — d'où le ``httpx.Client`` unique qui traverse les 3 étapes.
Les paramètres de date en GET sont ignorés par le portail et le filtrage de
dates par formulaire s'est révélé peu fiable : on ne les utilise pas, la date
de publication est lue sur la ligne.

LA RÈGLE DE CONDUITE QUI PRIME SUR TOUT LE RESTE
------------------------------------------------
Le client envoie un **User-Agent HONNÊTE** déclarant Taqinor et un contact.
**S'il est refusé (403), il S'ARRÊTE définitivement et remonte l'échec.** Il
ne réessaie JAMAIS avec un User-Agent de navigateur.

Ce n'est pas une préférence de style. Le pare-feu du portail refuse déjà les
clients scriptés (``curl`` et ``python-requests`` reçoivent un 403) et, **en
l'absence de conditions d'utilisation traitant de l'accès automatisé, cette
règle de refus est l'expression la plus probante de la volonté de
l'exploitant**. Maquiller l'identité du client pour contourner un contrôle qui
nous a explicitement refusés est hors périmètre : le repli d'un 403 est le
canal officiel (alertes du portail, VAO44) et la saisie manuelle — jamais le
déguisement. Voir ``tos_risk/marchespublics_gov_ma.md``.

Deuxième règle, de PROPORTION : **la requête est toujours restreinte par
mots-clés** (1 à 3 pages, moins de 10 requêtes par jour). Un balayage des
~3 380 avis ouverts (~338 POST/jour) est interdit et doit être **impossible
par construction** — une recherche sans mot-clé restrictif est refusée ici,
pas seulement déconseillée.

Enfin : **aucune URL de portail en dur**. L'adresse vient de
``SourceVeille.url_base`` (VAO7) ; ce module ne connaît que le CHEMIN PRADO,
qui est le protocole, pas la cible.
"""
from __future__ import annotations

import html as html_stdlib
import logging
import os
import re
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from . import ErreurPortail
# Les gardes vivent dans ``garde_fous`` (VAO19) et sont RÉ-EXPORTÉES ici :
# le client reste le point d'entrée lisible du paquet, sans détenir deux fois
# la même règle.
from .garde_fous import (
    GardeFous, MaquillageRefuse, RechercheNonRestreinte, cle_de_societe,
    exiger_mot_cle_restrictif, verifier_identite_honnete,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Les échecs, NOMMÉS. Un collecteur qui rend « 0 résultat » sur une panne est
# pire que pas de collecteur (VAO20) : chaque cause a donc son type.
# ─────────────────────────────────────────────────────────────────────────


class ClientRefuse(ErreurPortail):
    """L'exploitant nous refuse (403/401/406/429) — ARRÊT DÉFINITIF.

    Aucune nouvelle tentative, sous aucun déguisement. Cette exception est le
    signal d'arrêt du dispositif, pas une erreur transitoire à réessayer.
    """


class PortailIndisponible(ErreurPortail):
    """Panne technique (5xx, délai dépassé, connexion impossible).

    Distincte de ``ClientRefuse`` : ce n'est pas un refus, c'est une
    indisponibilité. Elle se journalise en échec et se rejoue le lendemain —
    jamais dans la foulée (la cadence prime).
    """


class ReponseInattendue(ErreurPortail):
    """200 OK, mais la page n'a pas la forme attendue.

    Pagestate absent, compteur introuvable : le portail est un logiciel tiers
    (Atexo) qui peut changer du jour au lendemain. On le DIT, on ne rend pas
    un tableau vide.
    """


class SourceNonCollectable(ErreurPortail):
    """La source est inactive, sans URL, ou n'est pas une porte automatique."""


# ─────────────────────────────────────────────────────────────────────────
# L'identité déclarée
# ─────────────────────────────────────────────────────────────────────────

#: Le contact par défaut est l'adresse PUBLIQUE de l'entreprise — un fait
#: vérifiable, pas une boîte inventée pour l'occasion. Le fondateur peut
#: poser une adresse dédiée dans ``VEILLE_AO_CONTACT`` (ex. une adresse de
#: courriel) : elle est alors reprise telle quelle dans le User-Agent.
CONTACT_DEFAUT = 'https://taqinor.ma'


def user_agent():
    """Le User-Agent HONNÊTE — la seule identité possible du client.

    Volontairement NON surchargeable : seul le *contact* se configure. Laisser
    l'environnement réécrire tout le User-Agent rouvrirait par la fenêtre la
    porte que la règle ferme (« il suffit de poser un UA de navigateur dans
    le ``.env`` et ça passe »).
    """
    contact = (os.environ.get('VEILLE_AO_CONTACT') or CONTACT_DEFAUT).strip()
    ua = f"TaqinorBot/1.0 (veille appels d'offres publics ; +{contact})"
    verifier_identite_honnete(ua)
    return ua


# ─────────────────────────────────────────────────────────────────────────
# Le protocole PRADO — des constantes, pas une URL
# ─────────────────────────────────────────────────────────────────────────

#: ``entreprise.`` est en MINUSCULES : une majuscule rend un 404 (mesuré).
CHEMIN = 'index.php'
PAGE_RECHERCHE = 'entreprise.EntrepriseAdvancedSearch'
CIBLE_TAILLE_PAGE = 'ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop'
CIBLE_NUMERO_PAGE = 'ctl0$CONTENU_PAGE$resultSearch$numPageTop'

#: Le portail n'affiche que 10 lignes par défaut, et accepte 500 par postback.
TAILLE_PAGE_PAR_DEFAUT = 10
TAILLE_PAGE_MAX = 500

#: Plafond de pages par mot-clé. Le fichier de risque promet « 1 à 3 pages » :
#: au-delà, on ne pagine pas en silence, on remonte l'anomalie.
PAGES_MAX = 3

DELAI_CONNEXION = 10.0
DELAI_LECTURE = 60.0

_TOTAL_RE = re.compile(
    r'id="ctl0_CONTENU_PAGE_resultSearch_nombreElement"[^>]*>\s*'
    r'([\d\s .,]+?)\s*<', re.IGNORECASE)
_INPUT_PAGESTATE_RE = re.compile(
    r'<input[^>]*name="PRADO_PAGESTATE"[^>]*>', re.IGNORECASE)
_VALUE_RE = re.compile(r'value="([^"]*)"', re.IGNORECASE)


def lire_total(html):
    """Le nombre de consultations ANNONCÉ par le portail, ou ``None``.

    ``None`` n'est pas 0 : c'est « le compteur est introuvable », donc une
    page qui n'a plus la forme attendue. Les deux ne doivent jamais être
    confondus — c'est tout le propos de VAO20.
    """
    trouve = _TOTAL_RE.search(html or '')
    if not trouve:
        return None
    chiffres = re.sub(r'[^\d]', '', trouve.group(1))
    return int(chiffres) if chiffres else None


def lire_pagestate(html):
    """Le champ caché ``PRADO_PAGESTATE``, DÉSÉCHAPPÉ, ou ``None``.

    Le déséchappement n'est pas cosmétique : le pagestate est du base64 qui
    contient des « + » servis en ``&#43;``. Le renvoyer échappé fait rendre au
    portail une page 1 muette au lieu de la page demandée — un bug qui se lit
    « 0 résultat » et non « erreur ».
    """
    balise = _INPUT_PAGESTATE_RE.search(html or '')
    if not balise:
        return None
    valeur = _VALUE_RE.search(balise.group(0))
    if not valeur:
        return None
    return html_stdlib.unescape(valeur.group(1))


# ─────────────────────────────────────────────────────────────────────────
# Les gardes d'entrée
# ─────────────────────────────────────────────────────────────────────────


def exiger_source_collectable(source):
    """Refuse de partir si la source ne doit pas être interrogée.

    ``SourceVeille.actif`` est un interrupteur d'arrêt réel (VAO7) : une
    source désactivée n'est JAMAIS interrogée. La source est reçue en canard
    (``url_base``/``actif``) et non importée : le client reste sans Django.
    """
    if not getattr(source, 'actif', False):
        raise SourceNonCollectable(
            f'Source « {getattr(source, "libelle", "?")} » inactive : '
            "l'interrupteur d'arrêt est fermé, aucune requête n'est envoyée.")
    url_base = (getattr(source, 'url_base', '') or '').strip()
    if not url_base:
        raise SourceNonCollectable(
            f'Source « {getattr(source, "libelle", "?")} » sans URL de base : '
            "l'adresse du portail vit en base (SourceVeille), jamais dans le "
            'code du collecteur.')
    return url_base


def url_de_recherche(url_base, mot_cle):
    """L'URL exacte de l'étape 1 — construite, jamais écrite en dur.

    Les trois drapeaux ``AllCons``/``EnCours``/``searchAnnCons`` sont des
    paramètres SANS valeur : les passer par un dictionnaire httpx les
    transformerait en ``AllCons=``, que le portail ignore. D'où la
    construction à la main de la chaîne de requête.
    """
    racine = url_base.rstrip('/')
    return (f'{racine}/{CHEMIN}?page={PAGE_RECHERCHE}'
            f'&AllCons&EnCours&searchAnnCons&keyWord={quote(mot_cle)}')


# ─────────────────────────────────────────────────────────────────────────
# Le résultat rendu à l'orchestration
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class Recherche:
    """Ce que le client rapporte : des PAGES, pas des avis.

    Le découpage en lignes est le travail du parseur (VAO17) et le verdict
    celui de ``resultats.py`` (VAO20). Le client, lui, ne fait que la
    conversation réseau — c'est ce qui garde les trois testables séparément.
    """

    mot_cle: str
    total_annonce: int | None = None
    pages: list = field(default_factory=list)
    requetes: int = 0
    tronquee: bool = False

    @property
    def html(self):
        """La DERNIÈRE page reçue — celle qui porte le plus de lignes."""
        return self.pages[-1] if self.pages else ''


class GardeNeutre:
    """Garde INERTE : ne freine rien, ne compte rien, ne verrouille rien.

    Elle n'est JAMAIS le défaut (VAO19 a fait des ``GardeFous`` réels le
    défaut de ``rechercher``) : elle sert aux tests qui vérifient le
    PROTOCOLE PRADO et n'ont rien à dire sur la cadence ou le quota. La
    fournir est un geste explicite, visible en revue.
    """

    def avant_requete(self, description=''):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _erreur_de_statut(reponse, url):
    code = reponse.status_code
    if code in (401, 403, 406, 429):
        return ClientRefuse(
            f'Le portail refuse le collecteur (HTTP {code}) sur {url}. '
            "ARRÊT DÉFINITIF : aucune nouvelle tentative, et surtout aucune "
            "sous une identité de navigateur. Le repli est le canal officiel "
            '(alertes du portail, VAO44) et la saisie manuelle.')
    if code >= 500:
        return PortailIndisponible(
            f'Portail indisponible (HTTP {code}) sur {url}. La collecte est '
            'en ÉCHEC — ce n\'est pas « 0 résultat ».')
    if code >= 400:
        return ReponseInattendue(
            f'Réponse inattendue (HTTP {code}) sur {url}.')
    return None


def _executer(appel, url, garde, description):
    """Un aller-retour réseau, gardé et traduit en erreurs NOMMÉES."""
    garde.avant_requete(description)
    try:
        reponse = appel()
    except httpx.TimeoutException as erreur:
        raise PortailIndisponible(
            f'Délai dépassé sur {url} ({description}) : {erreur}') from erreur
    except httpx.HTTPError as erreur:
        raise PortailIndisponible(
            f'Échec réseau sur {url} ({description}) : {erreur}') from erreur
    faute = _erreur_de_statut(reponse, url)
    if faute is not None:
        raise faute
    return reponse


def rechercher(source, mot_cle, *, garde=None, transport=None, client=None):
    """La séquence complète pour UN mot-clé. Rend une ``Recherche``.

    **Par défaut, la garde est RÉELLE** (``GardeFous`` de VAO19) : interrupteur
    d'arrêt, quota quotidien dur, cadence, verrou de société. Un appel sans
    ``garde`` sur un dispositif désarmé lève donc ``CollecteDesarmee`` avant
    la moindre connexion — y compris sur déclenchement manuel.

    ``transport``/``client`` n'existent que pour les tests : ils permettent de
    rejouer la séquence contre les fixtures committées, sans réseau.
    """
    garde = garde or GardeFous(cle=cle_de_societe(source))
    mot_cle = exiger_mot_cle_restrictif(mot_cle)
    url_base = exiger_source_collectable(source)
    url = url_de_recherche(url_base, mot_cle)

    # Le verrou tient TOUTE la séquence : deux collectes simultanées pour la
    # même société, c'est le double du volume promis au fichier de risque.
    with garde:
        if client is not None:
            return _sequence(client, url, mot_cle, garde)

        entetes = {
            'User-Agent': user_agent(),
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr',
        }
        delai = httpx.Timeout(DELAI_LECTURE, connect=DELAI_CONNEXION)
        # UNE seule jarre de cookies pour toute la séquence : le POST n'est
        # servi que si PHPSESSID et SERVERID du GET l'accompagnent (mesuré).
        with httpx.Client(headers=entetes, timeout=delai,
                          follow_redirects=True, transport=transport) as ouvert:
            return _sequence(ouvert, url, mot_cle, garde)


def _sequence(client, url, mot_cle, garde):
    recherche = Recherche(mot_cle=mot_cle)

    # ── Étape 1 : le GET. 10 lignes, le total, et le pagestate.
    reponse = _executer(lambda: client.get(url), url, garde,
                        f'recherche « {mot_cle} »')
    recherche.requetes += 1
    recherche.pages.append(reponse.text)
    recherche.total_annonce = lire_total(reponse.text)

    if recherche.total_annonce is None:
        raise ReponseInattendue(
            f'Compteur de résultats introuvable sur {url} : la page n\'a plus '
            'la forme attendue (le portail est un logiciel tiers qui peut '
            'changer). C\'est une ERREUR, pas « 0 résultat ».')
    if recherche.total_annonce <= TAILLE_PAGE_PAR_DEFAUT:
        return recherche

    # ── Étape 2 : le postback qui passe l'affichage à 500 lignes.
    pagestate = lire_pagestate(reponse.text)
    if not pagestate:
        raise ReponseInattendue(
            f'Champ PRADO_PAGESTATE absent de {url} : la pagination du portail '
            'en dépend entièrement, la collecte ne peut pas être complète.')

    reponse = _postback(client, url, pagestate, garde, mot_cle, numero_page=None)
    recherche.requetes += 1
    recherche.pages.append(reponse.text)

    if recherche.total_annonce <= TAILLE_PAGE_MAX:
        return recherche

    # ── Étape 3 : les pages suivantes, chacune avec le NOUVEAU pagestate.
    pages_attendues = -(-recherche.total_annonce // TAILLE_PAGE_MAX)  # arrondi haut
    for numero in range(2, min(pages_attendues, PAGES_MAX) + 1):
        pagestate = lire_pagestate(reponse.text)
        if not pagestate:
            raise ReponseInattendue(
                f'Pagestate absent de la page {numero - 1} : impossible de '
                'demander la page suivante sans lui.')
        reponse = _postback(client, url, pagestate, garde, mot_cle,
                            numero_page=numero)
        recherche.requetes += 1
        recherche.pages.append(reponse.text)

    if pages_attendues > PAGES_MAX:
        # On NE pagine pas en silence au-delà du plafond promis au fichier de
        # risque : on le dit, et l'orchestration le journalise en anomalie.
        recherche.tronquee = True
        logger.warning(
            'veille_ao.portail : « %s » annonce %s résultats (%s pages) — '
            'plafond de %s pages atteint, collecte TRONQUÉE. Restreindre le '
            'mot-clé plutôt que lever le plafond.',
            mot_cle, recherche.total_annonce, pages_attendues, PAGES_MAX)
    return recherche


def _postback(client, url, pagestate, garde, mot_cle, numero_page=None):
    """Le POST PRADO — même URL, même jarre de cookies, pagestate déséchappé."""
    donnees = {
        'PRADO_PAGESTATE': pagestate,
        'PRADO_POSTBACK_TARGET': CIBLE_TAILLE_PAGE,
        'PRADO_POSTBACK_PARAMETER': '',
        CIBLE_TAILLE_PAGE: str(TAILLE_PAGE_MAX),
    }
    description = f'postback « {mot_cle} » (500 lignes)'
    if numero_page is not None:
        donnees[CIBLE_NUMERO_PAGE] = str(numero_page)
        donnees['PRADO_POSTBACK_TARGET'] = CIBLE_NUMERO_PAGE
        description = f'postback « {mot_cle} » page {numero_page}'
    return _executer(lambda: client.post(url, data=donnees), url, garde,
                     description)


__all__ = [
    'CIBLE_NUMERO_PAGE', 'CIBLE_TAILLE_PAGE', 'ClientRefuse', 'GardeNeutre',
    'MaquillageRefuse', 'PAGES_MAX', 'PortailIndisponible', 'Recherche',
    'RechercheNonRestreinte', 'ReponseInattendue', 'SourceNonCollectable',
    'TAILLE_PAGE_MAX', 'exiger_mot_cle_restrictif', 'exiger_source_collectable',
    'lire_pagestate', 'lire_total', 'rechercher', 'url_de_recherche',
    'user_agent', 'verifier_identite_honnete',
]
