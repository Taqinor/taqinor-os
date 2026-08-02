"""AOF147 — détecteur de littéraux orphelins, en AVERTISSEMENT par défaut.

Le seul contrôle qui attrape les quatre défauts d'un coup
=========================================================
Les quatre défauts réels de la session du 27/07 sont tous des littéraux
survivants : 5 143 680 tapé pour 5 413 680 ; « batteries 2 800 » contre un
bordereau à 2 600 ; un bordereau frère périmé à 5 219 280 ; un LISEZ-MOI figé.
Le contrôleur STRUCTUREL (AOF146) en voit trois — pas le quatrième, parce
qu'il vit dans une parenthèse de texte libre qu'aucune structure ne relie à un
montant.

La règle est simple : **tout nombre de 4 chiffres et plus, et toute référence
produit, présents dans un texte rendu doivent correspondre à une valeur du
contexte de dossier.** Sinon c'est un vestige.

Pourquoi il démarre en AVERTISSEMENT (garde-fou obligatoire)
------------------------------------------------------------
Un détecteur bruyant est désactivé en trois dossiers, et la fatigue d'alerte
tue tout le dispositif — y compris les contrôles qui, eux, ne se trompent
jamais. Le passage en mode BLOQUANT n'est donc pas un réglage par défaut mais
un **acte de configuration explicite et tracé** : il exige un taux de faux
positifs MESURÉ sur un dossier réel, un motif, un auteur et une date
(``ConfigurationLiteraux.bloquante``). Sans mesure, la configuration bloquante
est refusée.

Module PUR : chaînes, dicts, aucun ORM, aucune I/O.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

__all__ = [
    'MODE_AVERTISSEMENT',
    'MODE_BLOQUANT',
    'SEUIL_FAUX_POSITIFS',
    'ConfigurationLiteraux',
    'LiteralOrphelin',
    'valeurs_du_contexte',
    'detecter',
    'controler',
    'mesurer_faux_positifs',
]

MODE_AVERTISSEMENT = 'avertissement'
MODE_BLOQUANT = 'bloquant'

#: Au-delà de ce taux de faux positifs mesuré, le mode bloquant est refusé :
#: un contrôle qui se trompe plus d'une fois sur vingt sera contourné.
SEUIL_FAUX_POSITIFS = Decimal('0.05')

#: Séparateurs de milliers français, en ÉCHAPPEMENTS (une espace
#: fine invisible dans le source est indébogable).
ESPACES = '\u202f\u00a0\u2009 '

_MOTIF_NOMBRE = re.compile(
    r'\d{1,3}(?:[' + ESPACES + r'.]\d{3})+(?:,\d+)?'
    r'|\d+(?:,\d+)?'
)

#: Un jeton « référence produit » : au moins une lettre ET un chiffre, quatre
#: caractères minimum. « A3 » ou « 05H » sont trop courts pour être des
#: références et produiraient un bruit constant.
_MOTIF_REFERENCE = re.compile(
    r'\b(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)'
    r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b'
)

#: Second motif : les codes tout en CAPITALES avec tiret, qui ne portent aucun
#: chiffre — « BOS-G » est exactement de cette forme, et c'est la référence
#: que la bascule réelle a laissée traîner. Exiger des segments capitalisés
#: écarte « Sous-total » ou « Rez-de-chaussée », qui produiraient un bruit
#: permanent en tête de paragraphe.
#: Le ``(?<![-\w])`` n'est pas cosmétique : sans lui, « décret n° 2-12-349 »
#: fait naître un faux « 12-349 » au MILIEU d'un numéro réglementaire — mesuré
#: sur le corpus, c'était l'unique faux positif du détecteur.
_MOTIF_CODE = re.compile(r'(?<![-\w])[A-Z0-9]{2,}(?:-[A-Z0-9]+)+\b')

#: Contextes qui DISCULPENT un nombre : ce sont des identifiants réglementaires
#: ou des coordonnées, pas des grandeurs du dossier.
_MOTIFS_DISCULPANTS = (
    r'(?:d[ée]cret|arr[êe]t[ée]|dahir|loi|article|art\.)\s*(?:n\s*°|no)?\s*$',
    r'(?:norme|nf|en|iec|cei|iso)\s*(?:en\s*)?$',
    r'(?:code\s+postal|cp)\s*:?\s*$',
    r'(?:t[ée]l|t[ée]l[ée]phone|fax|gsm)\s*:?\s*$',
    r'(?:ice|if|rc|cnss|patente|rib|iban)\s*:?\s*$',
    r'(?:page|pages|p\.)\s*$',
)

ANNEE_MIN = 1900
ANNEE_MAX = 2100


class LiteralOrphelin(Exception):
    """Levée en mode BLOQUANT quand un littéral ne vient d'aucune valeur."""

    def __init__(self, orphelins):
        self.orphelins = list(orphelins)
        super().__init__(
            "Littéraux orphelins (aucune valeur du contexte ne les explique) : "
            + ' ; '.join(
                "{} → « {} » dans « {} »".format(
                    o['emplacement'], o['valeur'], o['extrait'])
                for o in self.orphelins))


class ConfigurationLiteraux:
    """Mode du détecteur. Bloquant = décision explicite, mesurée et tracée."""

    def __init__(self, mode=MODE_AVERTISSEMENT, *, taux_faux_positifs=None,
                 motif='', auteur='', date=''):
        if mode not in (MODE_AVERTISSEMENT, MODE_BLOQUANT):
            raise ValueError("Mode inconnu : {!r}".format(mode))
        self.mode = mode
        self.taux_faux_positifs = taux_faux_positifs
        self.motif = motif
        self.auteur = auteur
        self.date = date

    @property
    def bloque(self):
        return self.mode == MODE_BLOQUANT

    @classmethod
    def bloquante(cls, *, taux_faux_positifs, motif, auteur, date,
                  seuil=SEUIL_FAUX_POSITIFS):
        """Construit la configuration BLOQUANTE — refusée sans mesure.

        Trois refus délibérés : sans taux mesuré, au-dessus du seuil, ou sans
        motif/auteur/date. Le troisième n'est pas de la bureaucratie : sans
        trace, personne ne saura, dans six mois, sur quoi la mesure portait.
        """
        if taux_faux_positifs is None:
            raise ValueError(
                "Passage en mode bloquant refusé : le taux de faux positifs "
                "doit être MESURÉ sur un dossier réel avant activation.")
        taux = Decimal(str(taux_faux_positifs))
        if taux > Decimal(str(seuil)):
            raise ValueError(
                "Passage en mode bloquant refusé : taux de faux positifs "
                "mesuré {} > seuil {}. Un détecteur bruyant est désactivé en "
                "trois dossiers.".format(taux, seuil))
        if not (motif and auteur and date):
            raise ValueError(
                "Passage en mode bloquant refusé : motif, auteur et date sont "
                "obligatoires — c'est un changement de configuration tracé.")
        return cls(MODE_BLOQUANT, taux_faux_positifs=taux, motif=motif,
                   auteur=auteur, date=date)


def _normaliser(texte):
    sans_accent = unicodedata.normalize('NFKD', str(texte or ''))
    sans_accent = ''.join(c for c in sans_accent
                          if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', sans_accent.lower()).strip()


def _decimal(brut):
    nettoye = brut
    for espace in ESPACES:
        nettoye = nettoye.replace(espace, '')
    nettoye = nettoye.replace('.', '').replace(',', '.')
    try:
        return Decimal(nettoye)
    except (InvalidOperation, ValueError):
        return None


def valeurs_du_contexte(contexte):
    """Aplatit le contexte en ``(nombres, références normalisées)``.

    Tout nombre du contexte compte, à n'importe quelle profondeur : c'est la
    seule façon d'éviter qu'une grandeur légitime soit signalée parce qu'elle
    était rangée une clé plus bas que prévu.
    """
    nombres = set()
    references = set()

    def _descendre(noeud):
        if isinstance(noeud, dict):
            for valeur in noeud.values():
                _descendre(valeur)
        elif isinstance(noeud, (list, tuple, set)):
            for valeur in noeud:
                _descendre(valeur)
        elif isinstance(noeud, bool):
            return
        elif isinstance(noeud, (int, float, Decimal)):
            nombres.add(Decimal(str(noeud)))
        elif isinstance(noeud, str):
            for occurrence in _MOTIF_NOMBRE.finditer(noeud):
                valeur = _decimal(occurrence.group(0))
                if valeur is not None:
                    nombres.add(valeur)
            normalise = _normaliser(noeud)
            if normalise:
                references.add(normalise)

    _descendre(contexte)
    return nombres, references


def _disculpe(texte, position):
    amont = texte[max(0, position - 40):position].lower()
    return any(re.search(motif, amont) for motif in _MOTIFS_DISCULPANTS)


def _extrait(texte, position, largeur=70):
    debut = max(0, position - largeur // 2)
    return texte[debut:debut + largeur].replace('\n', ' ').strip()


def detecter(textes, contexte, *, references_supplementaires=()):
    """Littéraux d'un ensemble de textes qu'aucune valeur du contexte n'explique.

    ``textes`` : ``[{'emplacement': 'memoire §4.2', 'texte': '…'}]``.
    Renvoie ``[{'emplacement', 'nature', 'valeur', 'extrait', 'position'}]``.
    """
    nombres, references = valeurs_du_contexte(contexte)
    for supplement in references_supplementaires or ():
        normalise = _normaliser(supplement)
        if normalise:
            references.add(normalise)

    orphelins = []
    for entree in textes or ():
        texte = str(entree.get('texte') or '')
        emplacement = entree.get('emplacement') or ''

        for occurrence in _MOTIF_NOMBRE.finditer(texte):
            brut = occurrence.group(0)
            chiffres = re.sub(r'\D', '', brut)
            if len(chiffres) < 4:
                continue
            valeur = _decimal(brut)
            if valeur is None or valeur in nombres:
                continue
            if (valeur == valeur.to_integral_value()
                    and ANNEE_MIN <= int(valeur) <= ANNEE_MAX):
                continue  # millésime : ni un montant ni une quantité
            if _disculpe(texte, occurrence.start()):
                continue
            orphelins.append({
                'emplacement': emplacement,
                'nature': 'nombre',
                'valeur': brut,
                'position': occurrence.start(),
                'extrait': _extrait(texte, occurrence.start()),
            })

        vus = set()
        for motif in (_MOTIF_REFERENCE, _MOTIF_CODE):
            for occurrence in motif.finditer(texte):
                jeton = occurrence.group(0)
                if len(jeton.replace('-', '')) < 4:
                    continue
                if occurrence.start() in vus:
                    continue
                normalise = _normaliser(jeton)
                if not normalise:
                    continue
                if any(normalise in reference for reference in references):
                    continue
                if _disculpe(texte, occurrence.start()):
                    continue
                vus.add(occurrence.start())
                orphelins.append({
                    'emplacement': emplacement,
                    'nature': 'reference',
                    'valeur': jeton,
                    'position': occurrence.start(),
                    'extrait': _extrait(texte, occurrence.start()),
                })
    return orphelins


def controler(textes, contexte, *, configuration=None, **options):
    """Applique le détecteur selon la configuration : avertit ou bloque.

    Renvoie la liste des orphelins en mode avertissement ; lève
    ``LiteralOrphelin`` en mode bloquant.
    """
    configuration = configuration or ConfigurationLiteraux()
    orphelins = detecter(textes, contexte, **options)
    if orphelins and configuration.bloque:
        raise LiteralOrphelin(orphelins)
    return orphelins


def mesurer_faux_positifs(cas, contexte, **options):
    """Mesure le taux de faux positifs sur un corpus ANNOTÉ.

    ``cas`` : ``[{'emplacement', 'texte', 'attendu': bool}]`` où ``attendu``
    dit si le passage contient RÉELLEMENT un vestige. Renvoie
    ``{'total', 'signales', 'faux_positifs', 'faux_negatifs', 'taux'}``.

    Publier cette mesure est la condition d'activation du mode bloquant : un
    taux non mesuré n'est pas un taux faible, c'est un taux inconnu.
    """
    faux_positifs = 0
    faux_negatifs = 0
    signales = 0
    for cas_unique in cas or ():
        entree = [{'emplacement': cas_unique.get('emplacement') or '',
                   'texte': cas_unique.get('texte') or ''}]
        trouve = bool(detecter(entree, contexte, **options))
        if trouve:
            signales += 1
        if trouve and not cas_unique.get('attendu'):
            faux_positifs += 1
        if not trouve and cas_unique.get('attendu'):
            faux_negatifs += 1
    total = len(list(cas or ()))
    taux = (Decimal(faux_positifs) / Decimal(total)) if total else Decimal('0')
    return {
        'total': total,
        'signales': signales,
        'faux_positifs': faux_positifs,
        'faux_negatifs': faux_negatifs,
        'taux': taux,
    }
