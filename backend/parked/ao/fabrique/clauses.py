"""AOF126 — clause de réserve : UN texte, DEUX insertions, identité octet-à-octet.

**Ce que cette clause protège.** C'est elle qui rend un bâtiment « TENDU » non
bloquant : on s'engage sur le maximum qu'un relevé préliminaire permet
d'implanter, et le décompte final porte sur les quantités RÉELLEMENT posées.
Sans elle, un module de moins au relevé contradictoire devient un manquement
contractuel ; avec elle, c'est un décompte.

**Pourquoi le contrôle est octet-à-octet.** La clause figure à DEUX endroits :
en pied du bordereau des prix et dans la lettre de soumission. Deux occurrences
d'un texte juridique, ce sont deux occasions de diverger — et une divergence
d'un seul mot (« pourra » / « pourrait », « exclusivement » supprimé) change la
portée de l'engagement. Le contrôle compare donc les octets, pas le sens, et
signale la position du premier caractère qui diffère.

**Conséquence pratique.** Modifier le texte au niveau société marque TOUTES les
pièces qui le portent comme à régénérer (`pieces_dependantes`) — la clause ne
peut pas être à jour dans la lettre et périmée dans le bordereau.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Tuple

#: Le texte de RÉFÉRENCE, tel qu'il a été rédigé pour le dossier réel.
#: Il n'est jamais reformulé par une pièce : une pièce le CITE.
CLAUSE_RESERVE_QUANTITES = (
    "Les quantités du présent bordereau correspondent au maximum que nos "
    "études préliminaires permettent d'implanter sur les toitures. L'étude "
    "d'exécution définitive, établie après relevé contradictoire complet des "
    "toitures, pourra conduire à installer un nombre de modules inférieur ; "
    "le marché étant à prix unitaires, le décompte final portera "
    "exclusivement sur les quantités réellement installées et réceptionnées."
)

CODE_RESERVE = 'reserve_quantites'

#: Les DEUX pièces qui doivent porter la clause, à l'identique.
EMPLACEMENTS_OBLIGATOIRES = ('bordereau', 'lettre_soumission')

#: Types de marché qui rendent la clause obligatoire.
MARCHES_A_PRIX_UNITAIRES = ('unitaires', 'prix_unitaires', 'bordereau')


class ClauseAbsente(AssertionError):
    """Une pièce obligatoire ne porte pas la clause — dépôt refusé."""


class ClauseDivergente(AssertionError):
    """Deux occurrences de la clause diffèrent — dépôt refusé."""


def texte_clause(*, texte_societe=None, code=CODE_RESERVE):
    """Le texte à insérer : celui de la société, sinon celui de référence.

    Le paramétrage par société est prévu (formulations d'avocat différentes),
    mais il reste UN texte pour tout le dossier — jamais un par pièce.
    """
    if code != CODE_RESERVE:
        raise KeyError('clause inconnue : %r' % code)
    if texte_societe is not None and str(texte_societe).strip():
        return str(texte_societe)
    return CLAUSE_RESERVE_QUANTITES


def clause_obligatoire(type_prix):
    """La clause est-elle exigible pour ce type de marché ?"""
    return str(type_prix or '').strip().lower() in MARCHES_A_PRIX_UNITAIRES


@dataclass(frozen=True)
class Occurrence:
    """La clause telle qu'elle figure DANS une pièce donnée."""

    piece: str
    texte: Optional[str]

    @property
    def presente(self):
        return bool(self.texte and self.texte.strip())


@dataclass(frozen=True)
class Divergence:
    """Deux occurrences qui ne sont pas identiques, et OÙ elles divergent."""

    piece_a: str
    piece_b: str
    position: int
    extrait_a: str
    extrait_b: str

    @property
    def motif(self):
        return ('la clause diffère entre « %s » et « %s » au caractère %d : '
                '« …%s… » contre « …%s… »'
                % (self.piece_a, self.piece_b, self.position,
                   self.extrait_a, self.extrait_b))

    def vers_dict(self):
        return {'piece_a': self.piece_a, 'piece_b': self.piece_b,
                'position': self.position, 'extrait_a': self.extrait_a,
                'extrait_b': self.extrait_b, 'motif': self.motif}


@dataclass(frozen=True)
class Rapport:
    """Le verdict : la clause est-elle présente et identique partout ?"""

    manquantes: Tuple[str, ...] = field(default_factory=tuple)
    divergences: Tuple[Divergence, ...] = field(default_factory=tuple)

    @property
    def conforme(self):
        return not self.manquantes and not self.divergences

    def motifs(self):
        return tuple(
            ['clause absente de la pièce « %s »' % piece
             for piece in self.manquantes]
            + [d.motif for d in self.divergences])

    def vers_dict(self):
        return {'conforme': self.conforme,
                'manquantes': list(self.manquantes),
                'divergences': [d.vers_dict() for d in self.divergences],
                'motifs': list(self.motifs())}


def _premier_ecart(a, b):
    """Position (1-indexée) du premier caractère qui diffère, sinon `None`."""
    octets_a = unicodedata.normalize('NFC', a)
    octets_b = unicodedata.normalize('NFC', b)
    for position, (ca, cb) in enumerate(zip(octets_a, octets_b), start=1):
        if ca != cb:
            return position
    if len(octets_a) != len(octets_b):
        return min(len(octets_a), len(octets_b)) + 1
    return None


def _extrait(texte, position, largeur=24):
    debut = max(0, position - 1 - largeur // 2)
    return texte[debut:debut + largeur]


def controler(occurrences, *, emplacements=EMPLACEMENTS_OBLIGATOIRES,
              reference=None):
    """Vérifie présence ET identité octet-à-octet de la clause.

    :param occurrences: mapping `pièce → texte de la clause dans cette pièce`
        (ou itérable d'`Occurrence`).
    :param emplacements: pièces qui DOIVENT la porter.
    :param reference: texte attendu ; par défaut, celui de la première pièce
        présente (c'est la cohérence interne qui est contrôlée, la référence
        n'étant qu'un point de comparaison).
    """
    trouvees = _normaliser_occurrences(occurrences)
    manquantes = tuple(piece for piece in emplacements
                       if not trouvees.get(piece, Occurrence(piece,
                                                             None)).presente)

    presentes = [(piece, occ.texte) for piece, occ in sorted(trouvees.items())
                 if occ.presente]
    if reference is None and presentes:
        reference = presentes[0][1]

    divergences = []
    if reference is not None:
        for piece, texte in presentes:
            position = _premier_ecart(reference, texte)
            if position is None:
                continue
            divergences.append(Divergence(
                piece_a=presentes[0][0] if presentes else 'référence',
                piece_b=piece, position=position,
                extrait_a=_extrait(reference, position),
                extrait_b=_extrait(texte, position)))
    return Rapport(manquantes=manquantes, divergences=tuple(divergences))


def _normaliser_occurrences(occurrences):
    if hasattr(occurrences, 'items'):
        return {str(piece): Occurrence(str(piece), texte)
                for piece, texte in occurrences.items()}
    return {occ.piece: occ for occ in occurrences or ()}


def exiger(occurrences, *, type_prix='unitaires',
           emplacements=EMPLACEMENTS_OBLIGATOIRES, reference=None):
    """Porte de DÉPÔT : lève si la clause manque ou diverge.

    Un marché qui n'est pas à prix unitaires n'exige pas la clause : la porte
    laisse alors passer sans rien inventer.
    """
    if not clause_obligatoire(type_prix):
        return True
    rapport = controler(occurrences, emplacements=emplacements,
                        reference=reference)
    if rapport.manquantes:
        raise ClauseAbsente(
            'dépôt refusé — clause de réserve des quantités absente de : %s'
            % ', '.join(rapport.manquantes))
    if rapport.divergences:
        raise ClauseDivergente(
            'dépôt refusé — %s' % ' ; '.join(d.motif
                                             for d in rapport.divergences))
    return True


def pieces_dependantes(pieces=EMPLACEMENTS_OBLIGATOIRES):
    """Les pièces à régénérer quand le texte de la clause change.

    Rendre cette liste explicite est ce qui évite le scénario le plus
    coûteux : une clause corrigée dans la lettre et laissée périmée dans le
    bordereau, c'est-à-dire deux engagements contradictoires dans le même pli.
    """
    return tuple(pieces)


def inserer(contexte_pieces, *, texte_societe=None):
    """Pose LE MÊME texte dans chaque pièce qui doit le porter.

    :param contexte_pieces: itérable de codes de pièces.
    :returns: mapping `pièce → texte`, identique par construction.
    """
    texte = texte_clause(texte_societe=texte_societe)
    return {str(piece): texte for piece in contexte_pieces or ()}
