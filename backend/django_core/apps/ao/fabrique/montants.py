"""AOF125 — montants en lettres par LIGNE et arrêté, toujours RECALCULÉS.

**Le formalisme.** Les CPS marocains exigent les montants en chiffres ET en
lettres, non seulement au total mais LIGNE À LIGNE du bordereau. Aucun outil
solaire international ne traite ce point : c'est un différenciateur, et il
coûte deux lignes de code une fois `core.nombre_lettres` en place (AOF109).

**La règle qui compte.** Le montant en lettres n'est JAMAIS stocké puis comparé
à une chaîne. Stocker les lettres créerait une seconde source de vérité — donc
une seconde occasion de mentir, exactement comme le bordereau frère resté à
5 219 280 pendant que le principal disait 5 413 680. Ici :

* les lettres sont RÉGÉNÉRÉES depuis le nombre à chaque rendu ;
* le contrôle de concordance régénère lui aussi, puis cherche le résultat dans
  le texte RENDU — il compare donc le document au chiffre, jamais une chaîne à
  une autre chaîne toutes deux stockées ;
* les lettres ne sont gelées QUE dans la version de document PUBLIÉE
  (`geler_pour_publication`), c'est-à-dire au moment où le PDF devient une
  pièce déposée et cesse d'être une vue.

Le module ne fait aucune arithmétique de montant : il met en mots ce que
`ordonnancement.py` a calculé.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Tuple

from core.formats_fr import formater_montant
from core.nombre_lettres import montant_en_lettres

MODE_ADMINISTRATIF = 'administratif'
DEVISE_DEFAUT = 'dirhams'

#: Noms de champs qu'AUCUN modèle ne doit porter : les lettres ne se stockent
#: pas. Le garde est exposé ici pour que la couche Django puisse l'appliquer.
CHAMPS_INTERDITS_EN_BASE = (
    'prix_unitaire_lettres', 'montant_lettres', 'arrete_lettres',
    'total_lettres', 'somme_en_lettres')


class LettresStockees(AssertionError):
    """Un modèle prétend stocker un montant en lettres — refusé."""


class ConcordanceRompue(AssertionError):
    """Le texte rendu ne dit pas, en lettres, ce que disent les chiffres."""


def verifier_absence_de_stockage(champs):
    """Refuse tout champ de base de données portant un montant en lettres."""
    fautifs = sorted(set(CHAMPS_INTERDITS_EN_BASE) & set(champs or ()))
    if fautifs:
        raise LettresStockees(
            'les montants en lettres sont RECALCULÉS, jamais stockés ; '
            'champs refusés : %s' % ', '.join(fautifs))
    return True


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def en_lettres(montant, *, devise=DEVISE_DEFAUT):
    """Montant → arrêté administratif en lettres (AOF109). Jamais mémorisé."""
    valeur = _d(montant)
    if valeur is None:
        return ''
    return montant_en_lettres(valeur, devise=devise, mode=MODE_ADMINISTRATIF)


def en_chiffres(montant, *, devise='DH', espace=None):
    """Montant → chaîne française (« 4 999 920,00 DH »)."""
    valeur = _d(montant)
    if valeur is None:
        return ''
    return formater_montant(valeur, devise=devise, espace=espace)


@dataclass(frozen=True)
class LigneEnLettres:
    """Une ligne du bordereau, prête à imprimer — VUE, jamais entité."""

    cle: str
    numero: str
    designation: str
    unite: str
    quantite: Optional[Decimal]
    prix_unitaire: Optional[Decimal]
    prix_unitaire_chiffres: str
    prix_unitaire_lettres: str
    total: Optional[Decimal]
    total_chiffres: str

    def vers_dict(self):
        return {'cle': self.cle, 'numero': self.numero,
                'designation': self.designation, 'unite': self.unite,
                'quantite': self.quantite, 'prix_unitaire': self.prix_unitaire,
                'prix_unitaire_chiffres': self.prix_unitaire_chiffres,
                'prix_unitaire_lettres': self.prix_unitaire_lettres,
                'total': self.total, 'total_chiffres': self.total_chiffres}


def lignes_en_lettres(lignes, *, devise=DEVISE_DEFAUT, devise_courte='DH',
                      espace=None):
    """Vue d'impression du bordereau : chaque PU en chiffres ET en lettres.

    La fonction ne modifie rien : elle retourne une VUE. Les lettres n'existent
    donc que le temps du rendu.
    """
    from .ordonnancement import montant_ligne

    vues = []
    for ligne in lignes or ():
        prix = _d(ligne.get('prix_unitaire'))
        total = montant_ligne(ligne)
        vues.append(LigneEnLettres(
            cle=str(ligne.get('cle') or ligne.get('numero') or ''),
            numero=str(ligne.get('numero') or ''),
            designation=str(ligne.get('designation') or ''),
            unite=str(ligne.get('unite') or ''),
            quantite=_d(ligne.get('quantite')),
            prix_unitaire=prix,
            prix_unitaire_chiffres=en_chiffres(prix, devise=devise_courte,
                                               espace=espace),
            prix_unitaire_lettres=en_lettres(prix, devise=devise),
            total=total,
            total_chiffres=en_chiffres(total, devise=devise_courte,
                                       espace=espace)))
    return tuple(vues)


def arrete(total_ttc, *, devise=DEVISE_DEFAUT, prefixe=None):
    """L'arrêté du bordereau — phrase GÉNÉRÉE, jamais rédigée.

    « Arrêté le présent bordereau des prix à la somme de : QUATRE MILLIONS
    NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE NEUF CENT VINGT DIRHAMS (TTC). »
    """
    lettres = en_lettres(total_ttc, devise=devise)
    if not lettres:
        return ''
    debut = prefixe or 'Arrêté le présent bordereau des prix à la somme de'
    return '%s : %s (toutes taxes comprises).' % (debut, lettres)


# ---------------------------------------------------------------- contrôle
def _normaliser(texte):
    """Espaces insécables/fines unifiées, casse ignorée, blancs compactés."""
    texte = unicodedata.normalize('NFC', str(texte or ''))
    texte = texte.replace(' ', ' ').replace(' ', ' ')
    texte = re.sub(r'\s+', ' ', texte)
    return texte.upper().strip()


@dataclass(frozen=True)
class Divergence:
    """Un montant dont les lettres et les chiffres ne disent pas la même chose."""

    repere: str
    montant: Decimal
    lettres_attendues: str
    chiffres_attendus: str
    lettres_presentes: bool
    chiffres_presents: bool

    @property
    def motif(self):
        if not self.lettres_presentes and not self.chiffres_presents:
            return ('%s : ni les chiffres ni les lettres du montant %s ne '
                    'figurent dans la pièce' % (self.repere, self.montant))
        if not self.lettres_presentes:
            return ('%s : la pièce porte les chiffres mais PAS les lettres '
                    'attendues (« %s »)' % (self.repere,
                                            self.lettres_attendues))
        return ('%s : la pièce porte les lettres mais PAS les chiffres '
                'attendus (« %s »)' % (self.repere, self.chiffres_attendus))

    def vers_dict(self):
        return {'repere': self.repere, 'montant': str(self.montant),
                'lettres_attendues': self.lettres_attendues,
                'chiffres_attendus': self.chiffres_attendus,
                'lettres_presentes': self.lettres_presentes,
                'chiffres_presents': self.chiffres_presents,
                'motif': self.motif}


def controler_concordance(texte_rendu, montants, *, devise=DEVISE_DEFAUT,
                          devise_courte='DH', exiger_chiffres=True):
    """« Lettres == chiffres » — en REGÉNÉRANT, jamais en comparant du stocké.

    :param texte_rendu: le texte de la pièce telle qu'elle sera lue.
    :param montants: mapping `repère → montant` (repère = « total TTC »,
        « ligne 12 »… ; il sert au message, pas au calcul).
    :returns: tuple de `Divergence`, vide quand la pièce est concordante.
    """
    normalise = _normaliser(texte_rendu)
    divergences = []
    for repere, montant in (montants.items() if hasattr(montants, 'items')
                            else montants):
        valeur = _d(montant)
        if valeur is None:
            continue
        lettres = en_lettres(valeur, devise=devise)
        chiffres = en_chiffres(valeur, devise=devise_courte)
        presence_lettres = _normaliser(lettres) in normalise
        presence_chiffres = _normaliser(chiffres) in normalise or \
            _normaliser(en_chiffres(valeur, devise='')) in normalise
        if presence_lettres and (presence_chiffres or not exiger_chiffres):
            continue
        divergences.append(Divergence(
            repere=str(repere), montant=valeur, lettres_attendues=lettres,
            chiffres_attendus=chiffres, lettres_presentes=presence_lettres,
            chiffres_presents=presence_chiffres))
    return tuple(divergences)


def exiger_concordance(texte_rendu, montants, **options):
    """Version BLOQUANTE : lève `ConcordanceRompue` au premier écart."""
    divergences = controler_concordance(texte_rendu, montants, **options)
    if divergences:
        raise ConcordanceRompue(' ; '.join(d.motif for d in divergences))
    return True


# ------------------------------------------------------------ publication
@dataclass(frozen=True)
class VersionPubliee:
    """Le SEUL endroit où les lettres sont gelées : la pièce déposée.

    Une fois le pli parti, le document ne doit plus bouger — même si le
    dossier évolue. La version publiée fige donc le texte ET l'empreinte du
    contexte qui l'a produit (AOF111), de sorte qu'on sache toujours de quel
    état du dossier la pièce déposée parle.
    """

    empreinte_contexte: str
    lettres: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    chiffres: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)

    def lettre_de(self, repere):
        return dict(self.lettres).get(str(repere), '')

    def vers_dict(self):
        return {'empreinte_contexte': self.empreinte_contexte,
                'lettres': dict(self.lettres), 'chiffres': dict(self.chiffres)}


def geler_pour_publication(empreinte, montants, *, devise=DEVISE_DEFAUT,
                           devise_courte='DH'):
    """Fige les lettres AU MOMENT du dépôt — et à ce moment-là seulement."""
    paires = list(montants.items() if hasattr(montants, 'items') else montants)
    return VersionPubliee(
        empreinte_contexte=str(empreinte),
        lettres=tuple((str(repere), en_lettres(valeur, devise=devise))
                      for repere, valeur in paires),
        chiffres=tuple((str(repere), en_chiffres(valeur,
                                                 devise=devise_courte))
                       for repere, valeur in paires))
