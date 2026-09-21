"""AOF119 — contrôle d'approvisionnement du matériel retenu.

**Le constat.** La planche du dossier FRDISI porte, gravé à côté du plan, un
argument commercial fort : « les 2 kits sont ceux des bâtiments DÉJÀ
approvisionnés — AUCUN approvisionnement nouveau ». Cette phrase a été écrite
à la main. Or l'ERP connaît le stock, le catalogue, ses produits ARCHIVÉS et
ses produits délibérément sans prix (11 pompes OSP livrées sans prix, 6
coffrets placeholders archivés par le seeder). Le benchmark note par ailleurs
que tous les outils de proposition du marché manquent de profondeur
approvisionnement.

**La règle du module.** L'argument n'est pas rédigé : il est FOURNI OU REFUSÉ.
`argument_aucun_approvisionnement()` retourne la phrase seulement si le
contrôle la confirme, et sinon `None` accompagné des motifs. Une phrase
d'argumentaire qu'on ne peut pas prouver ne doit pas exister dans le dossier —
c'est le genre d'affirmation qu'un maître d'ouvrage vérifie.

**Lecture du stock.** Le module ne touche PAS l'ORM : il reçoit l'état du
catalogue en paramètre, tel que `stock.selectors` le publie (jamais un import
de `apps.stock.models` — contrat import-linter). Aucune donnée de coût n'entre
ni ne sort : `prix_achat` n'a rien à faire dans un contrôle qui alimente une
pièce lue par le maître d'ouvrage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

#: Gravités, de la plus faible à la plus forte.
INFO = 'info'
AVERTISSEMENT = 'avertissement'
BLOCAGE = 'blocage'
GRAVITES = (INFO, AVERTISSEMENT, BLOCAGE)

#: Champs qu'un état de catalogue peut porter. Tout le reste est IGNORÉ —
#: en particulier `prix_achat`, qui ne doit jamais transiter par ici.
CHAMPS_ETAT = ('existe', 'archive', 'prix_renseigne', 'disponible',
               'delai_jours', 'deja_approvisionne', 'designation')

#: Le texte EXACT de l'argument. Il est unique et n'est jamais reformulé.
PHRASE_ARGUMENT = (
    "Le matériel retenu est celui des bâtiments déjà approvisionnés : la "
    "présente offre n'appelle aucun approvisionnement nouveau.")


class EtatCatalogueInvalide(ValueError):
    """L'état fourni contient une donnée qui n'a pas à circuler ici."""


@dataclass(frozen=True)
class Controle:
    """Un constat sur UN équipement retenu — jamais une opinion."""

    reference: str
    role: str
    gravite: str
    motif: str
    designation: str = ''
    quantite: Optional[float] = None

    def vers_dict(self):
        return {'reference': self.reference, 'role': self.role,
                'gravite': self.gravite, 'motif': self.motif,
                'designation': self.designation, 'quantite': self.quantite}


@dataclass(frozen=True)
class Rapport:
    """Le résultat du contrôle : des constats et UNE décision d'argument."""

    controles: Tuple[Controle, ...] = field(default_factory=tuple)

    @property
    def avertissements(self):
        return tuple(c for c in self.controles if c.gravite == AVERTISSEMENT)

    @property
    def blocages(self):
        return tuple(c for c in self.controles if c.gravite == BLOCAGE)

    @property
    def argument_disponible(self):
        """L'argument n'est disponible que si RIEN ne le contredit."""
        return not (self.avertissements or self.blocages)

    def motifs(self):
        return tuple(c.motif for c in self.controles if c.gravite != INFO)

    def vers_dict(self):
        return {'controles': [c.vers_dict() for c in self.controles],
                'argument_disponible': self.argument_disponible,
                'motifs': list(self.motifs())}


def _etat(catalogue, equipement):
    """Retrouve l'état d'un équipement — par référence, sinon par désignation."""
    for cle in (equipement.get('reference'), equipement.get('produit'),
                equipement.get('designation')):
        if cle and cle in catalogue:
            return catalogue[cle]
    return None


def _valider_catalogue(catalogue):
    interdits = set()
    for etat in (catalogue or {}).values():
        if not hasattr(etat, 'keys'):
            continue
        interdits |= {cle for cle in etat
                      if 'prix_achat' in str(cle)
                      or 'cout' in str(cle).lower()
                      or 'marge' in str(cle).lower()}
    if interdits:
        raise EtatCatalogueInvalide(
            'le contrôle d\'approvisionnement ne reçoit AUCUNE donnée de '
            'coût ; champs refusés : %s' % ', '.join(sorted(interdits)))


def controler(equipements, catalogue, *, delai_marche_jours=None):
    """Contrôle les équipements RETENUS contre l'état du catalogue.

    :param equipements: itérable de mappings `{role, reference, designation,
        quantite}` — les équipements retenus dans le dossier.
    :param catalogue: mapping `référence → état`, publié par
        `stock.selectors` (clés de `CHAMPS_ETAT`).
    :param delai_marche_jours: délai d'exécution du marché ; un délai
        d'approvisionnement supérieur est signalé.
    :returns: `Rapport`.
    """
    _valider_catalogue(catalogue)
    controles = []
    for equipement in equipements or ():
        reference = str(equipement.get('reference')
                        or equipement.get('produit') or '')
        role = str(equipement.get('role', ''))
        besoin = equipement.get('quantite')
        etat = _etat(catalogue, equipement)
        designation = str(equipement.get('designation', ''))

        if etat is None or not etat.get('existe', True):
            controles.append(Controle(
                reference, role, AVERTISSEMENT,
                'produit inconnu du catalogue : %s' % (reference or designation),
                designation, besoin))
            continue

        designation = designation or str(etat.get('designation', ''))
        if etat.get('archive'):
            controles.append(Controle(
                reference, role, AVERTISSEMENT,
                'produit ARCHIVÉ retenu dans le dossier : %s'
                % (designation or reference), designation, besoin))
        if etat.get('prix_renseigne') is False:
            controles.append(Controle(
                reference, role, AVERTISSEMENT,
                'produit sans prix catalogue : %s — le PU du bordereau ne peut '
                'pas être proposé automatiquement'
                % (designation or reference), designation, besoin))

        disponible = etat.get('disponible')
        if not etat.get('deja_approvisionne'):
            if disponible is None:
                controles.append(Controle(
                    reference, role, AVERTISSEMENT,
                    'disponibilité inconnue : %s' % (designation or reference),
                    designation, besoin))
            elif besoin is not None and disponible < besoin:
                controles.append(Controle(
                    reference, role, AVERTISSEMENT,
                    'approvisionnement nouveau requis : %s (besoin %s, '
                    'disponible %s)' % (designation or reference, _n(besoin),
                                        _n(disponible)), designation, besoin))
            else:
                controles.append(Controle(
                    reference, role, INFO,
                    'couvert par le stock : %s' % (designation or reference),
                    designation, besoin))
        else:
            controles.append(Controle(
                reference, role, INFO,
                'déjà approvisionné : %s' % (designation or reference),
                designation, besoin))

        delai = etat.get('delai_jours')
        if delai_marche_jours is not None and delai is not None and \
                delai > delai_marche_jours:
            controles.append(Controle(
                reference, role, AVERTISSEMENT,
                'délai d\'approvisionnement %s j supérieur au délai du marché '
                '%s j : %s' % (_n(delai), _n(delai_marche_jours),
                               designation or reference), designation, besoin))
    return Rapport(controles=tuple(controles))


def argument_aucun_approvisionnement(rapport):
    """La phrase d'argument — ou `None` si le contrôle ne la confirme pas.

    C'est la fonction entière du module : elle rend l'argument INDISPONIBLE
    tant qu'il n'est pas vrai, au lieu de laisser une pièce l'affirmer.
    """
    if rapport.argument_disponible:
        return PHRASE_ARGUMENT
    return None


def _n(valeur):
    if isinstance(valeur, float) and valeur == int(valeur):
        return str(int(valeur))
    return str(valeur)
