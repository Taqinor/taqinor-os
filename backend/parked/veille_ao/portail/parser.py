"""VAO17 — le parseur d'une ligne de résultat. PUR : du texte entre, des faits sortent.

Aucune E/S ici : ni réseau, ni disque, ni base, ni Django (garde
``tests/test_purete_portail.py``). C'est ce qui rend tout le collecteur
testable en millisecondes sur les fixtures committées, hors du gate des
migrations qui est le poste de coût dominant de la CI.

Ce qu'une ligne de résultat porte, et où
-----------------------------------------
=========================== ==================================================
``reference_avis``          ``<span class="ref">`` — la référence AFFICHÉE par
                            l'acheteur (« 12/2026/K1Z »)
``ref_consultation`` +      lus dans l'URL de détail
``org_acronyme``            (``…&refConsultation=<n>&orgAcronyme=<code>``) —
                            c'est l'identité PROPRE du portail, celle qui sert
                            au dédoublonnage de niveau 1 (VAO11). Elle n'est
                            PAS la référence affichée : les confondre ferait
                            entrer deux avis pour la même consultation.
``objet``                   après ``<strong> Objet : </strong>``
``acheteur``                après ``Acheteur public :``
``lieu``/``procedure``/     après leurs libellés respectifs
``categorie``
``date_publication``        le ``<div> jj/mm/aaaa </div>`` de la PREMIÈRE
                            cellule (en-tête « Publié le »)
``date_limite_remise``      le ``jj/mm/aaaa hh:mm`` de la ligne, rendu AWARE
                            en Africa/Casablanca
``url_detail``              l'URL de détail, absolue si une base est fournie
=========================== ==================================================

Les clés rendues sont celles de ``services.CHAMPS_RECTIFIABLES`` : le
dictionnaire se donne tel quel à ``enregistrer_avis`` (VAO11). Une clé qu'on
ne sait pas remplir est ABSENTE plutôt que vide — une ré-collecte ne doit
jamais EFFACER une valeur qu'un humain ou la page de détail a renseignée.

Une ligne malformée n'emporte JAMAIS la collecte
-------------------------------------------------
Elle est ignorée, avec son motif, et rendue dans ``Extraction.ignorees`` : le
journal d'exécution peut alors dire « 34 lignes, 2 illisibles » au lieu de
faire disparaître deux avis en silence. C'est la même règle que VAO20 : ce
qu'on n'a pas su lire se DIT.

La sélection est volontairement tolérante à la mise en forme (on cherche des
LIBELLÉS et des ancres, pas des chemins de balises profonds) : le portail est
un logiciel tiers qui peut être restylé sans prévenir. Ce qui n'est PAS
tolérant, c'est la disparition des ancres elles-mêmes — et c'est VAO20 qui la
transforme en erreur nommée.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

#: Le portail publie en heure marocaine. Une date limite naïve, comparée à
#: ``timezone.now()``, décale le « expiré » d'une heure selon la saison — sur
#: une remise de plis à 10 h, c'est exactement le genre d'erreur qui fait
#: rater un dépôt.
CASABLANCA = ZoneInfo('Africa/Casablanca')

#: L'analyseur HTML : ``html.parser`` est celui de la bibliothèque standard,
#: donc aucune dépendance binaire (ni ``lxml``, ni ``html5lib``) à installer
#: en production.
ANALYSEUR = 'html.parser'

_LIEN_DETAIL_RE = re.compile(r'EntrepriseDetailConsultation', re.IGNORECASE)
_TABLE_RE = re.compile(r'tableauResultat', re.IGNORECASE)
_DATE_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
_DATE_HEURE_RE = re.compile(
    r'(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:à\s*)?(\d{1,2})\s*[:hH]\s*(\d{2})')
_ESPACES_RE = re.compile(r'\s+')


class LigneIllisible(ValueError):
    """Une ligne qu'on ne sait pas lire — ignorée, jamais fatale.

    Volontairement une ``ValueError`` et non une ``ErreurPortail`` : ce n'est
    pas un échec de collecte, c'est un enregistrement écarté. Confondre les
    deux ferait tomber 33 avis bons pour un avis bancal.
    """


@dataclass
class Extraction:
    """Le résultat d'un parsing de page : ce qu'on a lu, ET ce qu'on a écarté."""

    lignes: list = field(default_factory=list)
    ignorees: list = field(default_factory=list)

    @property
    def total_lu(self):
        return len(self.lignes)

    @property
    def total_vu(self):
        """Lignes rencontrées, illisibles comprises — la base du contrôle croisé."""
        return len(self.lignes) + len(self.ignorees)


# ─────────────────────────────────────────────────────────────────────────
# Normalisation — de petites fonctions pures, testables une par une
# ─────────────────────────────────────────────────────────────────────────


def decoder_utf8(contenu):
    """Le portail sert de l'UTF-8 ; on le décode en UTF-8, sans deviner.

    Un décodage approximatif ne casse rien de visible : il rend juste
    « bÃ¢timent » au lieu de « bâtiment », et cette bouillie part ensuite dans
    un devis. Le repli ``latin-1`` n'est là que pour ne pas perdre une page
    entière sur un octet fautif ; il est journalisé.
    """
    if isinstance(contenu, str):
        return contenu
    try:
        return contenu.decode('utf-8')
    except UnicodeDecodeError:
        logger.warning(
            'veille_ao.portail : page non décodable en UTF-8, repli latin-1 '
            '(les accents peuvent être abîmés).')
        return contenu.decode('latin-1', errors='replace')


def normaliser(texte):
    """Espaces insécables, retours à la ligne et doublons d'espaces écrasés."""
    if not texte:
        return ''
    texte = texte.replace('\xa0', ' ').replace(' ', ' ')
    return _ESPACES_RE.sub(' ', texte).strip(' \t\n\r:•-')


def sans_accents(texte):
    """Pour COMPARER un libellé, jamais pour stocker une valeur."""
    decompose = unicodedata.normalize('NFKD', texte or '')
    return ''.join(c for c in decompose if not unicodedata.combining(c)).lower()


def lire_date(texte):
    """Une date ``jj/mm/aaaa`` → ``date``, ou ``None`` si illisible."""
    trouve = _DATE_RE.search(texte or '')
    if not trouve:
        return None
    jour, mois, annee = (int(x) for x in trouve.groups())
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def lire_date_heure(texte):
    """Un ``jj/mm/aaaa hh:mm`` → ``datetime`` AWARE (Africa/Casablanca)."""
    trouve = _DATE_HEURE_RE.search(texte or '')
    if not trouve:
        return None
    jour, mois, annee, heure, minute = (int(x) for x in trouve.groups())
    try:
        return datetime(annee, mois, jour, heure, minute, tzinfo=CASABLANCA)
    except ValueError:
        return None


def lire_identifiants(href):
    """``(ref_consultation, org_acronyme)`` lus dans une URL de détail.

    Ce couple est l'identité du portail (VAO11 niveau 1). Il est pris dans
    l'URL, jamais dans le texte affiché : l'URL est ce que le portail utilise
    lui-même pour retrouver la consultation.
    """
    parametres = parse_qs(urlparse(href or '').query)
    ref = (parametres.get('refConsultation') or [''])[0].strip()
    org = (parametres.get('orgAcronyme') or [''])[0].strip()
    return ref, org


# ─────────────────────────────────────────────────────────────────────────
# Extraction d'une ligne
# ─────────────────────────────────────────────────────────────────────────


def _valeur_apres_libelle(noeud, libelle):
    """Le texte qui suit un ``<strong>Libellé :</strong>``, jusqu'au retour.

    On s'arrête au premier ``<br>`` ou ``<strong>`` : c'est ce qui sépare les
    champs dans une cellule du portail. Comparaison SANS accents, pour que
    « Procédure » reste trouvable si le portail écrit « Procedure ».
    """
    cible = sans_accents(libelle)
    for fort in noeud.find_all(['strong', 'b', 'label']):
        if not sans_accents(fort.get_text()).strip().startswith(cible):
            continue
        morceaux = []
        for suivant in fort.next_siblings:
            nom = getattr(suivant, 'name', None)
            if nom in ('br', 'strong', 'b', 'label'):
                break
            morceaux.append(
                suivant.get_text(' ') if nom else str(suivant))
        valeur = normaliser(' '.join(morceaux))
        if valeur:
            return valeur
    return ''


def _liste(valeur):
    """Un attribut HTML, toujours rendu en liste de mots.

    Selon l'analyseur, BeautifulSoup rend ``headers``/``class`` tantôt en
    liste, tantôt en chaîne. Joindre une chaîne caractère par caractère
    (« p u b l i e ») ferait rater la cellule en silence — le genre de bug qui
    ne casse rien et perd juste la date de publication de tous les avis.
    """
    if valeur is None:
        return []
    if isinstance(valeur, str):
        return valeur.split()
    return list(valeur)


def _cellule_marquee(cellules, *marqueurs):
    """La cellule dont l'en-tête ou la classe porte l'un des marqueurs."""
    for cellule in cellules:
        mots = sans_accents(' '.join(
            _liste(cellule.get('headers')) + _liste(cellule.get('class'))))
        if any(marqueur in mots for marqueur in marqueurs):
            return cellule
    return None


def _cellule_de_publication(cellules):
    """La cellule « Publié le » : par son en-tête, sinon la première."""
    cellule = _cellule_marquee(cellules, 'publie')
    if cellule is not None:
        return cellule
    return cellules[0] if cellules else None


def analyser_ligne(ligne, url_base=''):
    """Un ``<tr>`` de résultat → un dictionnaire d'avis BRUT.

    Lève ``LigneIllisible`` (avec le motif) si la ligne n'a pas le minimum
    vital : une identité de portail et un objet. Rendre un avis sans objet
    remplirait l'écran de lignes vides que personne ne peut trier.
    """
    cellules = ligne.find_all('td')
    if not cellules:
        raise LigneIllisible('ligne sans cellule')

    lien = ligne.find('a', href=_LIEN_DETAIL_RE)
    if lien is None or not lien.get('href'):
        raise LigneIllisible("aucun lien de détail (refConsultation) sur la ligne")

    href = lien['href']
    ref_consultation, org_acronyme = lire_identifiants(href)
    if not ref_consultation:
        raise LigneIllisible(
            f'refConsultation absent de l\'URL de détail « {href[:120]} »')

    objet = _valeur_apres_libelle(ligne, 'objet')
    if not objet:
        raise LigneIllisible(
            f'objet illisible pour la consultation {ref_consultation}')

    donnees = {
        'ref_consultation': ref_consultation,
        'org_acronyme': org_acronyme,
        'objet': objet,
        'url_detail': urljoin(url_base, href) if url_base else href,
    }

    reference = ligne.find('span', class_='ref')
    if reference is not None:
        valeur = normaliser(reference.get_text(' '))
        if valeur:
            donnees['reference_avis'] = valeur

    for cle, libelle in (('acheteur', 'acheteur'), ('lieu', 'lieu'),
                         ('procedure', 'procedure'), ('categorie', 'categorie')):
        valeur = _valeur_apres_libelle(ligne, libelle)
        if valeur:
            donnees[cle] = valeur

    cellule = _cellule_de_publication(cellules)
    publication = lire_date(cellule.get_text(' ') if cellule else '')
    if publication:
        donnees['date_publication'] = publication

    # La date limite est cherchée D'ABORD dans sa cellule (en-tête
    # « dateLimite »), et seulement à défaut dans toute la ligne : balayer la
    # ligne entière ferait prendre la première date-heure venue si le portail
    # en ajoutait une (date d'ouverture, mise en ligne…).
    cellule_limite = _cellule_marquee(cellules, 'limite', 'remise')
    limite = lire_date_heure(
        cellule_limite.get_text(' ') if cellule_limite is not None else '')
    if limite is None:
        limite = lire_date_heure(ligne.get_text(' '))
    if limite:
        donnees['date_limite_remise'] = limite

    return donnees


def _lignes_de_resultat(soup):
    """Les ``<tr>`` de résultat, table trouvée ou non.

    Deux niveaux de repli : la table par son identifiant PRADO, puis la table
    qui contient un lien de détail, puis les ``<tr>`` porteurs d'un tel lien.
    Un restylage du portail ne doit pas rendre 0 avis là où il y en a 34.
    """
    table = soup.find('table', id=_TABLE_RE)
    if table is None:
        for candidate in soup.find_all('table'):
            if candidate.find('a', href=_LIEN_DETAIL_RE):
                table = candidate
                break
    if table is not None:
        return [tr for tr in table.find_all('tr') if tr.find('td')]
    return [tr for tr in soup.find_all('tr')
            if tr.find('a', href=_LIEN_DETAIL_RE)]


def analyser_page(html, url_base=''):
    """Toutes les lignes d'une page de résultats → une ``Extraction``.

    Ne lève JAMAIS sur une ligne fautive : elle part dans ``ignorees`` avec son
    motif. Le verdict (« réussi », « structure inattendue », « échec ») est le
    travail de ``resultats.py`` (VAO20), pas le sien.
    """
    soup = BeautifulSoup(decoder_utf8(html), ANALYSEUR)
    extraction = Extraction()
    for indice, ligne in enumerate(_lignes_de_resultat(soup), start=1):
        try:
            extraction.lignes.append(analyser_ligne(ligne, url_base=url_base))
        except LigneIllisible as motif:
            extraction.ignorees.append((indice, str(motif)))
            logger.warning(
                'veille_ao.portail : ligne %s ignorée — %s', indice, motif)
        except Exception as erreur:  # noqa: BLE001 — une ligne ne tue pas la page
            extraction.ignorees.append((indice, f'erreur inattendue : {erreur}'))
            logger.exception(
                'veille_ao.portail : ligne %s illisible', indice)
    return extraction


__all__ = [
    'ANALYSEUR', 'CASABLANCA', 'Extraction', 'LigneIllisible', 'analyser_ligne',
    'analyser_page', 'decoder_utf8', 'lire_date', 'lire_date_heure',
    'lire_identifiants', 'normaliser', 'sans_accents',
]
