"""AOF124 — bibliothèque de prix : proposer un PU depuis l'historique RÉEL.

**Pourquoi ce module existe avant la cascade.** La cascade de prix inverse
(AOF158) répartit le total sur les PU « par homothétie » et compare le résultat
à des « fourchettes par famille ». Une fourchette qu'aucune donnée n'alimente
est un contrôle décoratif : il passe toujours, donc il ne contrôle rien. Ce
module est la source de ces fourchettes — et, accessoirement, la fonction que
le benchmark identifie comme standard du marché BTP (proposer un prix depuis
l'historique).

**Ce qui entre et ce qui n'entre pas.** Le module agrège des OBSERVATIONS de
prix de vente : PU des AO antérieurs et des devis acceptés, avec leur date,
leur dossier d'origine et, quand il est connu, l'écart au moins-disant
(`ResultatAO.ecart_prix`). Il refuse toute donnée de coût de revient : la
proposition de prix est une aide au chiffrage commercial, pas une lecture de
marge — et son résultat finit dans un écran que tout le palier commercial voit.

Le module est PUR : les observations sont fournies par la couche Django
(`ventes.selectors` / historique AO), jamais lues par un import de modèle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

CENTIME = Decimal('0.01')

SOURCE_AO = 'ao'
SOURCE_DEVIS = 'devis'
SOURCES = (SOURCE_AO, SOURCE_DEVIS)

#: En dessous de ce nombre d'observations, une fourchette n'est pas fiable :
#: elle est publiée avec `fiable=False` plutôt que tue (savoir qu'on ne sait
#: pas vaut mieux que ne rien afficher).
SEUIL_FIABILITE = 3

#: Motifs de refus — les mêmes que partout dans la fabrique.
_MOTS_DE_COUT = ('prix_achat', 'cout', 'coût', 'marge', 'benefice', 'bénéfice',
                 'coefficient')


class ObservationInvalide(ValueError):
    """Une observation porte une donnée qui n'a rien à faire ici."""


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def _jour(valeur):
    if valeur in (None, ''):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur)[:10])


@dataclass(frozen=True)
class Observation:
    """UN prix unitaire réellement pratiqué, avec sa provenance."""

    reference: str
    famille: str
    prix_unitaire: Decimal
    date: Optional[date] = None
    dossier: str = ''
    source: str = SOURCE_AO
    unite: str = 'U'
    designation: str = ''
    ecart_moins_disant: Optional[Decimal] = None

    def vers_dict(self):
        return {'reference': self.reference, 'famille': self.famille,
                'prix_unitaire': str(self.prix_unitaire),
                'date': self.date.isoformat() if self.date else None,
                'dossier': self.dossier, 'source': self.source,
                'unite': self.unite, 'designation': self.designation,
                'ecart_moins_disant': None if self.ecart_moins_disant is None
                else str(self.ecart_moins_disant)}


def normaliser(observations):
    """Documents bruts → `Observation`. Refuse toute donnée de coût."""
    normalisees = []
    for brute in observations or ():
        if hasattr(brute, 'reference'):
            normalisees.append(brute)
            continue
        interdits = sorted(cle for cle in brute
                           if any(mot in str(cle).lower()
                                  for mot in _MOTS_DE_COUT))
        if interdits:
            raise ObservationInvalide(
                'la bibliothèque de prix ne reçoit AUCUNE donnée de coût ; '
                'champs refusés : %s' % ', '.join(interdits))
        prix = _d(brute.get('prix_unitaire'))
        if prix is None:
            continue
        normalisees.append(Observation(
            reference=str(brute.get('reference') or ''),
            famille=str(brute.get('famille') or ''),
            prix_unitaire=prix, date=_jour(brute.get('date')),
            dossier=str(brute.get('dossier') or ''),
            source=str(brute.get('source') or SOURCE_AO),
            unite=str(brute.get('unite') or 'U'),
            designation=str(brute.get('designation') or ''),
            ecart_moins_disant=_d(brute.get('ecart_moins_disant'))))
    return tuple(normalisees)


@dataclass(frozen=True)
class Proposition:
    """Le PU proposé à la création d'une ligne, AVEC sa justification.

    Un prix proposé sans sa date ni son dossier d'origine est un prix qu'on ne
    peut pas défendre en négociation — donc un prix qu'on ne devrait pas
    proposer.
    """

    prix_unitaire: Decimal
    unite: str
    date: Optional[date]
    dossier: str
    source: str
    methode: str
    nb_observations: int
    ecart_moins_disant: Optional[Decimal] = None

    @property
    def justification(self):
        """Phrase GÉNÉRÉE — « 2 950,00 DH/U (AO du 27/07/2026, dossier …) »."""
        elements = []
        if self.date:
            elements.append('du %s' % self.date.strftime('%d/%m/%Y'))
        if self.dossier:
            elements.append('dossier %s' % self.dossier)
        detail = ' — %s %s' % (
            'AO' if self.source == SOURCE_AO else 'devis accepté',
            ', '.join(elements)) if elements else ''
        return '%s/%s%s' % (_montant(self.prix_unitaire), self.unite, detail)

    def vers_dict(self):
        return {'prix_unitaire': str(self.prix_unitaire), 'unite': self.unite,
                'date': self.date.isoformat() if self.date else None,
                'dossier': self.dossier, 'source': self.source,
                'methode': self.methode,
                'nb_observations': self.nb_observations,
                'ecart_moins_disant': None if self.ecart_moins_disant is None
                else str(self.ecart_moins_disant),
                'justification': self.justification}


def _montant(valeur):
    return '{:,.2f}'.format(valeur).replace(',', ' ').replace('.', ',') + ' DH'


def _tri_recent(observation):
    """Le plus RÉCENT d'abord ; une observation sans date passe en dernier."""
    return (observation.date is not None,
            observation.date or date.min)


def proposer(observations, *, reference=None, famille=None):
    """Le PU à proposer pour une nouvelle ligne — ou `None`.

    Priorité : le dernier prix pratiqué sur LA MÊME référence produit ; à
    défaut, la médiane de la famille (une médiane résiste à un prix aberrant
    là où une moyenne le propage).
    """
    normalisees = normaliser(observations)
    if reference:
        memes = [o for o in normalisees if o.reference == reference]
        if memes:
            recente = sorted(memes, key=_tri_recent)[-1]
            return Proposition(
                prix_unitaire=recente.prix_unitaire, unite=recente.unite,
                date=recente.date, dossier=recente.dossier,
                source=recente.source, methode='dernier prix de la référence',
                nb_observations=len(memes),
                ecart_moins_disant=recente.ecart_moins_disant)
    if famille:
        memes = [o for o in normalisees if o.famille == famille]
        if memes:
            recente = sorted(memes, key=_tri_recent)[-1]
            return Proposition(
                prix_unitaire=mediane([o.prix_unitaire for o in memes]),
                unite=recente.unite, date=recente.date,
                dossier=recente.dossier, source=recente.source,
                methode='médiane de la famille', nb_observations=len(memes))
    return None


def mediane(valeurs):
    """Médiane exacte en `Decimal`, arrondie au centime."""
    triees = sorted(valeurs)
    if not triees:
        return None
    milieu = len(triees) // 2
    if len(triees) % 2:
        return triees[milieu].quantize(CENTIME, rounding=ROUND_HALF_UP)
    return ((triees[milieu - 1] + triees[milieu]) / Decimal('2')).quantize(
        CENTIME, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Fourchette:
    """La bande de crédibilité d'une famille — l'entrée du garde-fou AOF158."""

    famille: str
    bas: Decimal
    haut: Decimal
    mediane: Decimal
    nb_observations: int
    unite: str = 'U'
    dossiers: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def fiable(self):
        return self.nb_observations >= SEUIL_FIABILITE

    def contient(self, prix):
        return self.bas <= _d(prix) <= self.haut

    @property
    def libelle_source(self):
        """D'où vient la bande — un contrôle sans source ne se conteste pas."""
        return '%d observation(s)%s' % (
            self.nb_observations,
            ' (%s)' % ', '.join(self.dossiers) if self.dossiers else '')

    def vers_dict(self):
        return {'famille': self.famille, 'bas': str(self.bas),
                'haut': str(self.haut), 'mediane': str(self.mediane),
                'nb_observations': self.nb_observations, 'unite': self.unite,
                'fiable': self.fiable, 'dossiers': list(self.dossiers),
                'source': self.libelle_source}


def fourchettes(observations, *, marge_relative=Decimal('0.20')):
    """Bandes de crédibilité PAR FAMILLE, alimentées par l'historique réel.

    :param marge_relative: élargissement appliqué autour des extrêmes observés
        (un historique court ne borne pas le marché ; borner trop serré
        transformerait le garde-fou en refus permanent).
    """
    normalisees = normaliser(observations)
    par_famille = {}
    for observation in normalisees:
        if not observation.famille:
            continue
        par_famille.setdefault(observation.famille, []).append(observation)

    bandes = {}
    for famille, groupe in sorted(par_famille.items()):
        prix = [o.prix_unitaire for o in groupe]
        bas = (min(prix) * (Decimal('1') - marge_relative)).quantize(
            CENTIME, rounding=ROUND_HALF_UP)
        haut = (max(prix) * (Decimal('1') + marge_relative)).quantize(
            CENTIME, rounding=ROUND_HALF_UP)
        bandes[famille] = Fourchette(
            famille=famille, bas=bas, haut=haut, mediane=mediane(prix),
            nb_observations=len(groupe), unite=groupe[-1].unite,
            dossiers=tuple(sorted({o.dossier for o in groupe if o.dossier})))
    return bandes


def hors_bande(lignes, bandes):
    """Les lignes dont le PU sort de sa bande — triées par IMPACT décroissant.

    Trier par impact (quantité × écart) et non par écart relatif est ce qui
    rend le rapport utilisable : c'est la ligne qui coûte le plus cher au
    total qu'il faut regarder d'abord, pas la plus petite qui dérive le plus.
    """
    ecarts = []
    for ligne in lignes or ():
        famille = str(ligne.get('famille') or '')
        bande = bandes.get(famille)
        prix = _d(ligne.get('prix_unitaire'))
        if bande is None or prix is None or bande.contient(prix):
            continue
        borne = bande.bas if prix < bande.bas else bande.haut
        quantite = _d(ligne.get('quantite')) or Decimal('0')
        ecarts.append({
            'cle': str(ligne.get('cle') or ligne.get('numero') or ''),
            'famille': famille, 'prix_unitaire': prix,
            'bas': bande.bas, 'haut': bande.haut,
            'ecart': (prix - borne).quantize(CENTIME),
            'impact': ((prix - borne) * quantite).quantize(CENTIME),
            'fiable': bande.fiable, 'source': bande.libelle_source})
    return tuple(sorted(ecarts, key=lambda e: abs(e['impact']), reverse=True))
