"""VAO20 — échouer FORT, jamais « 0 résultat » en silence.

Le constat qui commande tout ce module : la pagination du portail dépend d'un
champ d'état interne PRADO de 87 Ko, et le portail est un logiciel tiers
(Atexo) qui peut changer du jour au lendemain. **Un collecteur qui casse sans
le dire est pire que pas de collecteur** — c'est ainsi qu'on rate un appel
d'offres en se croyant couvert.

Trois cas, qui ne doivent JAMAIS être confondus
------------------------------------------------
======================== =================================== ================
Cas                      Ce que c'est                        Ce qu'on fait
======================== =================================== ================
``SUCCES``               collecte réussie, 0 nouveauté        rien à signaler
                         possible — c'est NORMAL
``ANOMALIE``             collecte réussie, mais la structure  on remonte
                         a bougé : lignes illisibles, ou le   l'anomalie AVEC
                         compte ne tombe pas juste            les données
``ECHEC``                compteur introuvable, aucune ligne   on LÈVE une
                         là où le portail en annonce, page    erreur nommée
                         de refus                             (jamais [])
======================== =================================== ================

Le contrôle croisé
------------------
``span#…_nombreElement`` dit combien de consultations le portail a trouvées.
Si le nombre de lignes lues en diffère, **ce n'est pas un résultat, c'est une
anomalie** : soit le parseur a raté des lignes, soit la page a changé. Sans ce
contrôle, une dérive du HTML se lit exactement comme « il n'y avait rien
aujourd'hui », et personne ne s'en aperçoit avant d'avoir raté un marché.

Ce module est PUR : il reçoit du texte, il rend un verdict. Il détient aussi
les deux lecteurs du protocole PRADO (le compteur et le pagestate), pour que
le client comme le verdict s'appuient sur la MÊME lecture — deux lectures
divergentes du même compteur seraient un bug impossible à voir.
"""
from __future__ import annotations

import html as html_stdlib
import logging
import re
from dataclasses import dataclass, field

from . import ErreurPortail
from .parser import analyser_page

logger = logging.getLogger(__name__)

#: Les trois verdicts. Des chaînes simples (pas un ``TextChoices`` Django) :
#: ce module doit rester importable sans Django.
SUCCES = 'succes'
ANOMALIE = 'anomalie'
ECHEC = 'echec'

_TOTAL_RE = re.compile(
    r'id="ctl0_CONTENU_PAGE_resultSearch_nombreElement"[^>]*>\s*'
    r'([\d\s .,]+?)\s*<', re.IGNORECASE)
_INPUT_PAGESTATE_RE = re.compile(
    r'<input[^>]*name="PRADO_PAGESTATE"[^>]*>', re.IGNORECASE)
_VALUE_RE = re.compile(r'value="([^"]*)"', re.IGNORECASE)

#: Les marques d'une page de refus. Servent UNIQUEMENT à rendre le message
#: d'échec précis (« refus » plutôt que « page inattendue ») : la décision
#: d'arrêt, elle, se prend sur le code HTTP dans ``client.py``.
_MARQUES_DE_REFUS = ('403', 'interdit', 'forbidden', 'access denied',
                     "n'êtes pas autorisé", 'support-id')


class ReponseInattendue(ErreurPortail):
    """200 OK, mais la page n'a pas la forme attendue.

    C'est une ERREUR, pas un résultat vide. Elle porte toujours un message
    français qui dit CE QUI manque — « la page a changé » sans plus n'aide
    personne à réparer.
    """


@dataclass
class Resultat:
    """Le verdict d'une page de résultats, avec de quoi le justifier."""

    verdict: str = SUCCES
    total_annonce: int | None = None
    lignes: list = field(default_factory=list)
    ignorees: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    message: str = ''

    @property
    def est_succes(self):
        return self.verdict == SUCCES

    @property
    def est_anomalie(self):
        return self.verdict == ANOMALIE

    @property
    def total_lu(self):
        return len(self.lignes)

    def resume(self):
        """Une phrase française pour le journal d'exécution (VAO24)."""
        if self.est_succes and not self.lignes:
            return ('Collecte réussie : aucune consultation ne correspond '
                    '(0 résultat annoncé par le portail).')
        if self.est_succes:
            return f'Collecte réussie : {self.total_lu} consultation(s) lue(s).'
        return (f'Collecte réussie avec anomalie : {self.total_lu} ligne(s) '
                f'lue(s) — {" ; ".join(self.anomalies)}')


# ─────────────────────────────────────────────────────────────────────────
# Les deux lecteurs du protocole PRADO (purs)
# ─────────────────────────────────────────────────────────────────────────


def lire_total(html):
    """Le nombre de consultations ANNONCÉ par le portail, ou ``None``.

    ``None`` n'est pas 0 : c'est « le compteur est introuvable », donc une
    page qui n'a plus la forme attendue. Confondre les deux est exactement
    l'erreur que ce module existe pour empêcher.
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


def ressemble_a_un_refus(html):
    """La page a-t-elle l'allure d'un refus du pare-feu ?

    Sert à NOMMER l'échec, pas à le décider : le code HTTP reste l'autorité
    (``client._erreur_de_statut``). Un portail qui rend un 200 portant une
    page « Interdit » existe, et l'appeler « structure inattendue » enverrait
    chercher un bug de parseur là où il y a un refus.
    """
    minuscule = (html or '').lower()
    return any(marque in minuscule for marque in _MARQUES_DE_REFUS)


# ─────────────────────────────────────────────────────────────────────────
# Le verdict
# ─────────────────────────────────────────────────────────────────────────


#: Sentinelle : « ne fais pas le contrôle croisé sur ce lot ». Un seul cas
#: l'utilise — une collecte TRONQUÉE au plafond de pages, où l'écart entre le
#: lu et l'annoncé est ATTENDU et déjà signalé comme anomalie. Crier deux fois
#: la même chose noierait le message utile.
SANS_CONTROLE_CROISE = 'sans-controle-croise'


def analyser_resultats(html, url_base='', total_annonce=None,
                       lignes_attendues=None):
    """Une page (ou une liste de pages) → un ``Resultat``, ou une erreur NOMMÉE.

    ``total_annonce`` permet de passer le compteur lu sur la PREMIÈRE page
    d'une séquence paginée (les pages suivantes le réaffichent, mais c'est
    celui de l'étape 1 qui fait foi) ; à défaut, il est lu sur la page.
    ``lignes_attendues`` dit combien de lignes CE lot devrait porter (une page
    GET est plafonnée à 10, un postback à 500) ; ``SANS_CONTROLE_CROISE``
    désactive la comparaison.
    """
    pages = [html] if isinstance(html, str) else [p for p in html]
    premiere = pages[0] if pages else ''
    if total_annonce is None:
        total_annonce = lire_total(premiere)
    html = premiere

    if total_annonce is None:
        if ressemble_a_un_refus(html):
            raise ReponseInattendue(
                'Le portail a répondu par une page de REFUS au lieu des '
                'résultats. La collecte est en ÉCHEC — surtout pas « 0 '
                'résultat » : le repli est le canal officiel (VAO44), jamais '
                'une nouvelle tentative déguisée.')
        raise ReponseInattendue(
            'Compteur de résultats introuvable : la page de résultats n\'a '
            'plus la forme attendue (le portail est un logiciel tiers qui peut '
            'changer du jour au lendemain). C\'est un ÉCHEC de collecte, pas '
            'un résultat vide — un collecteur qui casse sans le dire fait '
            'rater un appel d\'offres en se croyant couvert.')

    lignes = []
    ignorees = []
    for page in pages:
        extraction = analyser_page(page, url_base=url_base)
        lignes.extend(extraction.lignes)
        ignorees.extend(extraction.ignorees)

    resultat = Resultat(
        total_annonce=total_annonce, lignes=lignes, ignorees=ignorees)

    attendu = total_annonce if lignes_attendues is None else lignes_attendues
    controle = attendu is not SANS_CONTROLE_CROISE

    # ── ÉCHEC : le portail annonce des consultations, on n'en lit AUCUNE.
    if total_annonce > 0 and not lignes and not ignorees:
        raise ReponseInattendue(
            f'Le portail annonce {total_annonce} consultation(s) et le '
            "parseur n'en lit AUCUNE : la structure du tableau de résultats a "
            'changé. Rendre un tableau vide ici ferait croire à une veille à '
            'jour alors qu\'elle est aveugle.')

    # ── ANOMALIE : on a des données, mais le compte ne tombe pas juste.
    if ignorees:
        resultat.anomalies.append(
            f'{len(ignorees)} ligne(s) illisible(s) : '
            + ' ; '.join(f'ligne {indice} — {motif}'
                         for indice, motif in ignorees[:3]))

    if controle and len(lignes) != attendu:
        resultat.anomalies.append(
            f'contrôle croisé : {len(lignes)} ligne(s) lue(s) pour '
            f'{attendu} attendue(s) ({total_annonce} annoncée(s) par le '
            'portail)')

    if resultat.anomalies:
        resultat.verdict = ANOMALIE
        logger.warning('veille_ao.portail : collecte ANORMALE — %s',
                       ' ; '.join(resultat.anomalies))
    resultat.message = resultat.resume()
    return resultat


def analyser_recherche(recherche, url_base=''):
    """Le verdict d'une ``Recherche`` rendue par le client (VAO16).

    Les pages RETENUES sont celles du postback : la réponse GET de l'étape 1
    ne montre que les 10 premières lignes, qui sont RÉPÉTÉES dans le postback
    à 500. Les compter deux fois ferait un doublon systématique de 10 avis.

    Une recherche TRONQUÉE au plafond de pages est une anomalie déclarée,
    jamais un succès muet.
    """
    pages = list(getattr(recherche, 'pages', None) or [])
    total = getattr(recherche, 'total_annonce', None)
    tronquee = bool(getattr(recherche, 'tronquee', False))
    if not pages:
        raise ReponseInattendue(
            "Aucune page reçue du portail : la collecte n'a pas eu lieu. "
            "Ce n'est pas « 0 résultat ».")

    utiles = pages[1:] if len(pages) > 1 else pages[:1]
    resultat = analyser_resultats(
        utiles, url_base=url_base, total_annonce=total,
        lignes_attendues=_lignes_attendues(total, len(pages), tronquee))

    if tronquee:
        resultat.verdict = ANOMALIE
        resultat.anomalies.append(
            'collecte TRONQUÉE au plafond de pages : le mot-clé ramène plus '
            'que ce que le fichier de risque autorise à parcourir. Restreindre '
            'le mot-clé plutôt que lever le plafond.')
        resultat.message = resultat.resume()
    return resultat


def _lignes_attendues(total, nombre_de_pages, tronquee):
    """Combien de lignes le lot retenu devrait porter.

    * une seule page = la réponse GET, **plafonnée à 10 lignes** par le
      portail : comparer 10 lignes lues à 34 annoncées ferait crier à
      l'anomalie sur une collecte parfaitement normale ;
    * plusieurs pages = tout le résultat, donc le total annoncé ;
    * collecte tronquée = pas de contrôle croisé (l'écart est attendu, et il
      est DÉJÀ signalé comme anomalie).
    """
    if total is None:
        return None
    if tronquee:
        return SANS_CONTROLE_CROISE
    if nombre_de_pages <= 1:
        return min(total, 10)
    return total


__all__ = [
    'ANOMALIE', 'ECHEC', 'ReponseInattendue', 'Resultat',
    'SANS_CONTROLE_CROISE', 'SUCCES', 'analyser_recherche',
    'analyser_resultats', 'lire_pagestate', 'lire_total',
    'ressemble_a_un_refus',
]
