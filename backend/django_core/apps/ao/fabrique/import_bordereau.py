"""AOF121 — import du bordereau ACHETEUR (BPU/DQE) et VERROUILLAGE.

**Pourquoi c'est la fonction n°1.** Le benchmark montre que l'import du cadre
DQE/BPU est la première fonction de TOUS les outils BTP de réponse aux appels
d'offres (Vecteur Plus, écosystème Libel, EDAO). Sans elle, l'app ne sait que
FABRIQUER un bordereau depuis nos propres lignes — ce qui ne répond qu'aux
consultations sans cadre imposé, c'est-à-dire à une minorité des marchés
publics.

**Le verrou.** La checklist partenaire du dossier réel dit, en capitales, « NE
MODIFIER AUCUN PRIX NI AUCUNE QUANTITÉ » du cadre remis par l'acheteur. Une
désignation retouchée, une unité « harmonisée » ou une quantité « corrigée »
suffisent à faire écarter l'offre pour non-conformité. Le module rend donc les
trois champs structurants (désignation, unité, quantité) TECHNIQUEMENT
inéditables : `appliquer()` lève sur toute tentative. Nos prix ne se posent que
dans les colonnes de PU.

**Les écarts ne se fusionnent jamais en silence.** Une ligne issue de notre
calepinage sans correspondance dans le cadre acheteur est LISTÉE comme écart à
arbitrer. La fusionner automatiquement dans la ligne « la plus proche » est
exactement la façon dont une quantité change sans que personne ne le décide.

Le module est PUR : la lecture du fichier passe par `apps.dataimport.parsing`
(primitive plateforme, importée paresseusement), tout le reste travaille sur
des lignes déjà extraites.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

#: Source de quantité d'une ligne de bordereau (miroir du champ de modèle
#: `LigneBordereau.quantite_source`, AOF120 — l'autre lane).
SOURCE_ACHETEUR = 'acheteur'
SOURCE_CALEPINAGE = 'calepinage'
SOURCE_MANUELLE = 'manuelle'
SOURCE_CATALOGUE = 'catalogue'

#: Champs du cadre acheteur qu'on ne touche JAMAIS.
CHAMPS_VERROUILLES = ('numero', 'designation', 'unite', 'quantite')

#: Champs que NOUS remplissons.
CHAMPS_EDITABLES = ('prix_unitaire', 'observation', 'produit')

#: Alias d'en-tête → champ. En-têtes normalisés (minuscules, sans accents).
ALIAS = {
    'numero': ('numero', 'n', 'no', 'num', 'item', 'rang', 'prix',
               'numero_prix', 'n_prix', 'ref', 'reference'),
    'designation': ('designation', 'libelle', 'description', 'nature',
                    'designation_des_prestations', 'designation_des_ouvrages',
                    'intitule'),
    'unite': ('unite', 'u', 'un', 'unite_de_mesure', 'ud'),
    'quantite': ('quantite', 'qte', 'qty', 'quantites', 'q'),
    'prix_unitaire': ('prix_unitaire', 'pu', 'pu_ht', 'prix_unitaire_ht',
                      'prix_unitaire_en_chiffres'),
}


class MappingIncomplet(ValueError):
    """Le fichier ne porte pas les colonnes minimales d'un cadre BPU/DQE."""


class ChampVerrouille(PermissionError):
    """Tentative de modification d'un champ du cadre acheteur."""


def normaliser_entete(valeur):
    """Minuscules, sans accents, séparateurs → `_` (patron `dataimport`)."""
    texte = unicodedata.normalize('NFKD', str(valeur or ''))
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r'[^0-9a-zA-Z]+', '_', texte.lower()).strip('_')
    return texte


def _decimal(valeur):
    """Quantité/prix → `Decimal`. Accepte « 1 234,50 » et « 1,234.50 »."""
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, Decimal):
        return valeur
    if isinstance(valeur, (int, float)):
        return Decimal(str(valeur))
    texte = str(valeur).strip()
    texte = re.sub(r'[\s  ]', '', texte)
    if ',' in texte and '.' in texte:
        texte = (texte.replace(',', '') if texte.rfind('.') > texte.rfind(',')
                 else texte.replace('.', '').replace(',', '.'))
    else:
        texte = texte.replace(',', '.')
    texte = re.sub(r'[^0-9.\-]', '', texte)
    try:
        return Decimal(texte) if texte not in ('', '-', '.') else None
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class LigneCadre:
    """Une ligne du cadre ACHETEUR — structure gelée, PU à nous."""

    numero: str
    designation: str
    unite: str
    quantite: Optional[Decimal]
    prix_unitaire: Optional[Decimal] = None
    observation: str = ''
    produit: str = ''
    quantite_source: str = SOURCE_ACHETEUR
    verrouillee: bool = True
    ligne_fichier: Optional[int] = None

    @property
    def total(self):
        """Total de ligne — `None` tant que le PU n'est pas posé."""
        if self.quantite is None or self.prix_unitaire is None:
            return None
        return self.quantite * self.prix_unitaire

    @property
    def cle(self):
        """L'identité d'une ligne du cadre : son numéro, sinon sa désignation."""
        return self.numero or normaliser_entete(self.designation)

    def appliquer(self, **modifications):
        """Modifie les SEULS champs éditables — lève sur un champ verrouillé."""
        if self.verrouillee:
            interdits = sorted(set(modifications) & set(CHAMPS_VERROUILLES))
            if interdits:
                raise ChampVerrouille(
                    'cadre acheteur : %s ne peut pas être modifié (ligne %s) — '
                    'la consultation impose de ne changer ni désignation, ni '
                    'unité, ni quantité' % (', '.join(interdits), self.cle))
        inconnus = sorted(set(modifications) - set(CHAMPS_EDITABLES))
        if inconnus:
            raise ChampVerrouille(
                'champs non éditables sur une ligne de cadre : %s'
                % ', '.join(inconnus))
        return replace(self, **modifications)

    def vers_dict(self):
        return {'numero': self.numero, 'designation': self.designation,
                'unite': self.unite,
                'quantite': None if self.quantite is None
                else str(self.quantite),
                'prix_unitaire': None if self.prix_unitaire is None
                else str(self.prix_unitaire),
                'observation': self.observation, 'produit': self.produit,
                'quantite_source': self.quantite_source,
                'verrouillee': self.verrouillee,
                'ligne_fichier': self.ligne_fichier}


@dataclass(frozen=True)
class Apercu:
    """Ce que l'utilisateur VOIT avant de valider un import."""

    mapping: dict
    colonnes_ignorees: Tuple[str, ...] = ()
    lignes: Tuple[LigneCadre, ...] = ()
    anomalies: Tuple[str, ...] = ()
    total_lignes: int = 0

    @property
    def importable(self):
        return bool(self.lignes) and not any(
            a.startswith('BLOQUANT') for a in self.anomalies)


@dataclass(frozen=True)
class Rapprochement:
    """Cadre acheteur ↔ lignes issues de notre calepinage."""

    appariees: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    ecarts_a_arbitrer: Tuple[dict, ...] = field(default_factory=tuple)
    cadre_non_servi: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def arbitrage_requis(self):
        return bool(self.ecarts_a_arbitrer or self.cadre_non_servi)


def lire_fichier(contenu, nom_fichier):
    """`(en-têtes, lignes)` via la primitive plateforme `dataimport.parsing`.

    Import PARESSEUX : le module reste utilisable (et testable) sans toucher
    au reste du dépôt, et aucune lecture bas niveau n'est re-codée ici (ARC13).
    """
    from apps.dataimport.parsing import iter_rows
    return iter_rows(contenu, nom_fichier)


def detecter_mapping(entetes):
    """Devine la correspondance colonne ↔ champ à partir des en-têtes."""
    mapping = {}
    for entete in entetes or ():
        normalise = normaliser_entete(entete)
        if not normalise:
            continue
        for champ, alias in ALIAS.items():
            if champ in mapping:
                continue
            if normalise in alias or any(normalise.startswith(a + '_')
                                         for a in alias):
                mapping[champ] = entete
                break
    return mapping


def _valeur(ligne, mapping, champ):
    entete = mapping.get(champ)
    if entete is None:
        return None
    return ligne.get(entete)


def apercu(entetes, lignes, mapping=None, *, limite=None):
    """Prépare l'import : mapping, lignes lues, anomalies — SANS rien écrire."""
    mapping = dict(mapping or detecter_mapping(entetes))
    anomalies = []
    for obligatoire in ('designation', 'quantite'):
        if obligatoire not in mapping:
            anomalies.append(
                'BLOQUANT : colonne « %s » introuvable dans le fichier'
                % obligatoire)
    ignorees = tuple(e for e in (entetes or ())
                     if e not in set(mapping.values()))

    lues, vues = [], {}
    for index, brute in enumerate(lignes or (), start=1):
        designation = str(_valeur(brute, mapping, 'designation') or '').strip()
        numero = str(_valeur(brute, mapping, 'numero') or '').strip()
        if not designation and not numero:
            continue
        quantite = _decimal(_valeur(brute, mapping, 'quantite'))
        ligne = LigneCadre(
            numero=numero, designation=designation,
            unite=str(_valeur(brute, mapping, 'unite') or '').strip(),
            quantite=quantite,
            prix_unitaire=_decimal(_valeur(brute, mapping, 'prix_unitaire')),
            ligne_fichier=index)
        if not designation:
            anomalies.append('ligne %d : désignation vide' % index)
        if quantite is None:
            anomalies.append('ligne %d (%s) : quantité illisible'
                             % (index, numero or designation))
        if ligne.cle in vues:
            anomalies.append(
                'ligne %d : numéro « %s » déjà présent ligne %d'
                % (index, ligne.cle, vues[ligne.cle]))
        else:
            vues[ligne.cle] = index
        lues.append(ligne)

    return Apercu(mapping=mapping, colonnes_ignorees=ignorees,
                  lignes=tuple(lues if limite is None else lues[:limite]),
                  anomalies=tuple(anomalies), total_lignes=len(lues))


def importer(entetes, lignes, mapping=None):
    """Cadre acheteur → lignes VERROUILLÉES. Lève si le cadre est illisible."""
    vue = apercu(entetes, lignes, mapping)
    bloquants = [a for a in vue.anomalies if a.startswith('BLOQUANT')]
    if bloquants:
        raise MappingIncomplet(' ; '.join(bloquants))
    return vue.lignes


def reporter_prix(lignes, prix_par_cle):
    """Pose NOS prix dans les seules colonnes de PU. Rien d'autre ne bouge."""
    reportees = []
    for ligne in lignes:
        prix = prix_par_cle.get(ligne.cle)
        if prix is None:
            reportees.append(ligne)
            continue
        reportees.append(ligne.appliquer(prix_unitaire=_decimal(prix)))
    return tuple(reportees)


def fusionner(existantes, importees):
    """Ré-import IDEMPOTENT : rejouer le même cadre ne change rien.

    Le cadre de l'acheteur fait foi sur la structure ; nos PU déjà saisis sont
    CONSERVÉS. Une ligne dont la structure a bougé (avenant, rectificatif) est
    reprise depuis le nouveau cadre ET signalée : la modification est visible,
    jamais silencieuse.
    """
    par_cle = {ligne.cle: ligne for ligne in existantes or ()}
    fusionnees, modifications, ajouts = [], [], []
    for ligne in importees:
        ancienne = par_cle.pop(ligne.cle, None)
        if ancienne is None:
            fusionnees.append(ligne)
            ajouts.append(ligne.cle)
            continue
        if (ancienne.designation, ancienne.unite, ancienne.quantite) != \
                (ligne.designation, ligne.unite, ligne.quantite):
            modifications.append(ligne.cle)
        fusionnees.append(replace(
            ligne, prix_unitaire=ancienne.prix_unitaire,
            observation=ancienne.observation, produit=ancienne.produit))
    retirees = tuple(sorted(par_cle))
    return tuple(fusionnees), {'ajouts': tuple(ajouts),
                               'modifications': tuple(modifications),
                               'retirees': retirees}


def rapprocher(cadre, lignes_calepinage, *, appariement=None):
    """Confronte le cadre acheteur à nos lignes issues du calepinage.

    Aucune fusion automatique : ce qui ne s'apparie pas est LISTÉ.

    :param appariement: mapping optionnel `clé de notre ligne → clé du cadre`,
        arbitré par un humain lors d'un import précédent.
    """
    appariement = dict(appariement or {})
    cles_cadre = {ligne.cle for ligne in cadre}
    appariees, ecarts, servies = [], [], set()

    for ligne in lignes_calepinage or ():
        cle = str(ligne.get('cle') or ligne.get('numero')
                  or normaliser_entete(ligne.get('designation', '')))
        cible = appariement.get(cle, cle if cle in cles_cadre else None)
        if cible and cible in cles_cadre:
            appariees.append((cle, cible))
            servies.add(cible)
            continue
        ecarts.append({
            'cle': cle,
            'designation': str(ligne.get('designation', '')),
            'quantite': ligne.get('quantite'),
            'motif': 'aucune ligne du cadre acheteur ne correspond — à '
                     'arbitrer (jamais fusionnée automatiquement)'})

    return Rapprochement(
        appariees=tuple(appariees), ecarts_a_arbitrer=tuple(ecarts),
        cadre_non_servi=tuple(sorted(cles_cadre - servies)))
