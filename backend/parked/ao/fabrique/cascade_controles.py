"""AOF158 — garde-fou de crédibilité de la cascade de prix.

Un solveur qui atteint sa cible peut parfaitement produire un prix absurde :
répartir 4 166 600 DH sur un bordereau dont la structure a changé peut donner
un module à 6 000 DH ou une station météo à 4 000. La cible serait tenue, la
marge aussi, et l'offre serait écartée — ou gagnée sur un prix intenable.

Le garde-fou compare donc chaque PU sorti de la cascade à la **fourchette de sa
famille**, alimentée par la bibliothèque de prix (AOF124) — c'est-à-dire par
des prix RÉELLEMENT pratiqués, avec leur date et leur dossier. Une fourchette
non alimentée est un contrôle décoratif : ici, chaque bande publie son nombre
d'observations et sa fiabilité, et le rapport le dit.

**Trié par IMPACT, pas par écart relatif.** Un module à +2 % sur 560 unités
pèse plus qu'un afficheur à +40 % sur une unité. Le rapport met en tête ce qui
coûte le plus cher au total : c'est la seule façon de le rendre actionnable un
soir de dépôt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Tuple

from .bibliotheque_prix import fourchettes, hors_bande
from .cascade import (SEUIL_PSYCHOLOGIQUE_TTC, prix_non_ronds,
                      verifier_invariant)

NIVEAU_INFO = 'info'
NIVEAU_ALERTE = 'alerte'
NIVEAU_REFUS = 'refus'


@dataclass(frozen=True)
class Controle:
    """Un constat sur la cascade — jamais une opinion."""

    code: str
    niveau: str
    motif: str
    impact: Decimal = Decimal('0')

    def vers_dict(self):
        return {'code': self.code, 'niveau': self.niveau,
                'motif': self.motif, 'impact': str(self.impact)}


@dataclass(frozen=True)
class Rapport:
    """Le verdict du garde-fou, trié par impact décroissant."""

    controles: Tuple[Controle, ...] = field(default_factory=tuple)

    @property
    def refus(self):
        return tuple(c for c in self.controles if c.niveau == NIVEAU_REFUS)

    @property
    def alertes(self):
        return tuple(c for c in self.controles if c.niveau == NIVEAU_ALERTE)

    @property
    def publiable(self):
        return not self.refus

    def vers_dict(self):
        return {'publiable': self.publiable,
                'controles': [c.vers_dict() for c in self.controles]}


def controler(cascade, observations=(), *,
              seuil_psychologique=SEUIL_PSYCHOLOGIQUE_TTC,
              refuser_hors_bande=False):
    """Contrôle une cascade : invariant, crédibilité, seuil, arrondis.

    :param cascade: résultat de `cascade.resoudre`.
    :param observations: historique de prix (AOF124) alimentant les bandes.
    :param refuser_hors_bande: `True` bloque au lieu d'alerter (une société
        peut vouloir interdire tout PU hors bande fiable).
    """
    controles = []

    # 1. L'invariant dur. Il a déjà été asserté à la résolution ; on le rejoue
    #    ici parce que les lignes ont pu être retouchées entre-temps.
    try:
        verifier_invariant(cascade.lignes, cascade.cible_ht)
    except AssertionError as exc:
        controles.append(Controle('invariant_rompu', NIVEAU_REFUS, str(exc)))

    # 2. Le seuil psychologique.
    if seuil_psychologique is not None and \
            cascade.cible_ttc >= Decimal(str(seuil_psychologique)):
        controles.append(Controle(
            'seuil_psychologique', NIVEAU_ALERTE,
            'total TTC %s au niveau ou au-dessus du seuil %s'
            % (cascade.cible_ttc, seuil_psychologique),
            impact=cascade.cible_ttc - Decimal(str(seuil_psychologique))))

    # 3. La crédibilité des PU, bande par bande.
    bandes = fourchettes(observations)
    for ecart in hors_bande(cascade.lignes, bandes):
        niveau = NIVEAU_REFUS if (refuser_hors_bande and ecart['fiable']) \
            else NIVEAU_ALERTE
        controles.append(Controle(
            'prix_hors_bande', niveau,
            'PU %s hors de la bande %s–%s de la famille « %s » (%s)'
            % (ecart['prix_unitaire'], ecart['bas'], ecart['haut'],
               ecart['famille'], ecart['source']),
            impact=abs(ecart['impact'])))

    # 4. Les prix qui ne tombent pas sur leur pas métier. La ligne
    #    d'ajustement est ATTENDUE hors pas : elle porte le résidu.
    for hors_pas in prix_non_ronds(cascade):
        if hors_pas['ligne_ajustement']:
            controles.append(Controle(
                'residu_sur_ligne_ajustement', NIVEAU_INFO,
                'la ligne « %s » porte le résidu d\'arrondi (PU %s, pas %s)'
                % (hors_pas['cle'], hors_pas['prix_unitaire'],
                   hors_pas['pas'])))
        else:
            controles.append(Controle(
                'prix_non_rond', NIVEAU_ALERTE,
                'PU %s non aligné sur le pas métier %s (ligne « %s »)'
                % (hors_pas['prix_unitaire'], hors_pas['pas'],
                   hors_pas['cle'])))

    # 5. Les familles sans historique : le contrôle ne peut RIEN dire, et il
    #    le dit. Un garde-fou muet passe pour un garde-fou vert.
    familles_couvertes = set(bandes)
    familles_lignes = {str(ligne.get('famille') or '')
                       for ligne in cascade.lignes
                       if ligne.get('famille')}
    sans_bande = sorted(familles_lignes - familles_couvertes)
    if sans_bande:
        controles.append(Controle(
            'famille_sans_historique', NIVEAU_INFO,
            'aucune fourchette de référence pour : %s — le contrôle de '
            'crédibilité ne s\'applique pas à ces lignes'
            % ', '.join(sans_bande)))

    controles.sort(key=lambda c: (_rang(c.niveau), -c.impact))
    return Rapport(controles=tuple(controles))


def _rang(niveau):
    return {NIVEAU_REFUS: 0, NIVEAU_ALERTE: 1, NIVEAU_INFO: 2}.get(niveau, 3)


def exiger_publiable(rapport):
    """Porte : lève si un refus subsiste."""
    if not rapport.publiable:
        raise AssertionError(
            'cascade non publiable — %s'
            % ' ; '.join(c.motif for c in rapport.refus))
    return True
