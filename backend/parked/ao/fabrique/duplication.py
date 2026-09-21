"""AOF130 — duplication d'affaire : le gabarit d'affaire réutilisable.

**Le besoin.** Les écrans de liste proposent une action « dupliquer », et la
distillation demande de formaliser le pack documentaire comme un gabarit
d'affaire réutilisable. Sans elle, chaque nouvel appel d'offres recommence à
zéro : bâtiments, toitures, kits, presets, sections de mémoire, structure de
bordereau — c'est-à-dire précisément le travail que l'app est censée
supprimer.

**Ce qui se copie et ce qui NE se copie JAMAIS.** Une affaire dupliquée hérite
d'une STRUCTURE, jamais d'un RÉSULTAT :

* copiables : géométrie, obstacles, structure du bordereau, gabarit de pack,
  exigences ;
* jamais copiés : variantes calculées (le calepinage se REJOUE — un plan de
  pose est propre à une toiture relevée), économie et coûts de revient, pièces
  générées, référence, statut, dépôt, caution, résultat de la consultation.

**Trois décisions non évidentes.**

1. **Les lignes du cadre ACHETEUR ne sont pas copiées.** Un BPU/DQE appartient
   à SA consultation : le reporter dans une autre affaire y importerait des
   quantités imposées par un autre maître d'ouvrage. Elles sont listées comme
   volontairement écartées, jamais silencieusement reprises.
2. **Les quantités issues du calepinage sont vidées, la ligne est gardée.** On
   conserve la structure (désignation, unité, PU de référence) et on remet la
   quantité à néant : c'est ce qui force le recalcul sans faire perdre le
   chiffrage.
3. **Les pièces jointes sont RÉFÉRENCÉES, pas recopiées en stockage.** Copier
   les octets d'un DCE de 80 Mo à chaque duplication remplirait MinIO pour
   rien ; `records.Attachment` sait pointer le même objet.

Le module est PUR : il produit un PLAN et l'affaire dupliquée sous forme de
mapping. La création réelle (référence via `core.numbering`, trace au chatter
`records`) appartient à la couche Django.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

#: Ce qu'une duplication PEUT reprendre.
COPIABLES = ('geometrie', 'obstacles', 'bordereau', 'gabarit_pack',
             'exigences')

#: Ce qu'une duplication ne reprend JAMAIS, quel que soit le paramétrage.
JAMAIS_COPIES = (
    'reference', 'reference_acheteur', 'statut', 'variantes', 'calepinage',
    'engagements', 'economie', 'lignes_cout_revient', 'pieces_generees',
    'artefacts', 'depot', 'date_depot', 'caution', 'resultat', 'ecart_prix',
    'empreinte', 'chatter',
)

#: Statut d'une affaire neuve.
STATUT_INITIAL = 'identifie'

SOURCE_CALEPINAGE = 'calepinage'
SOURCE_ACHETEUR = 'acheteur'


class OptionDeCopieInconnue(ValueError):
    """Une option de duplication ne correspond à rien de copiable."""


@dataclass(frozen=True)
class PlanDuplication:
    """Ce que la duplication VA faire — lisible avant de l'exécuter."""

    copie: Tuple[str, ...] = field(default_factory=tuple)
    ecarte: Tuple[str, ...] = field(default_factory=tuple)
    lignes_acheteur_ecartees: Tuple[str, ...] = field(default_factory=tuple)
    quantites_a_recalculer: Tuple[str, ...] = field(default_factory=tuple)
    pieces_jointes_referencees: Tuple[str, ...] = field(default_factory=tuple)

    def vers_dict(self):
        return {'copie': list(self.copie), 'ecarte': list(self.ecarte),
                'lignes_acheteur_ecartees':
                    list(self.lignes_acheteur_ecartees),
                'quantites_a_recalculer': list(self.quantites_a_recalculer),
                'pieces_jointes_referencees':
                    list(self.pieces_jointes_referencees)}

    @property
    def resume(self):
        """Phrase de chatter — générée, jamais rédigée."""
        return ('Affaire dupliquée : %s repris ; %d ligne(s) de cadre '
                'acheteur écartée(s), %d quantité(s) à recalculer.'
                % (', '.join(self.copie) or 'aucun élément',
                   len(self.lignes_acheteur_ecartees),
                   len(self.quantites_a_recalculer)))


def _valider(copier):
    inconnues = sorted(set(copier or ()) - set(COPIABLES))
    if inconnues:
        raise OptionDeCopieInconnue(
            'options de duplication inconnues : %s (copiables : %s)'
            % (', '.join(inconnues), ', '.join(COPIABLES)))
    return tuple(cle for cle in COPIABLES if cle in set(copier or ()))


def _cle_ligne(ligne):
    return str(ligne.get('cle') or ligne.get('numero')
               or ligne.get('designation') or '')


def _copier_bordereau(lignes):
    """Structure conservée, résultats de calepinage effacés, cadre écarté."""
    copiees, ecartees, a_recalculer = [], [], []
    for ligne in lignes or ():
        cle = _cle_ligne(ligne)
        if ligne.get('quantite_source') == SOURCE_ACHETEUR or \
                ligne.get('verrouillee'):
            ecartees.append(cle)
            continue
        nouvelle = dict(ligne)
        for champ in ('variante_hash', 'version_moteur', 'numero',
                      'position'):
            nouvelle.pop(champ, None)
        if nouvelle.get('quantite_source') == SOURCE_CALEPINAGE:
            nouvelle['quantite'] = None
            a_recalculer.append(cle)
        copiees.append(nouvelle)
    return tuple(copiees), tuple(ecartees), tuple(a_recalculer)


def plan_de_duplication(affaire, *, copier=COPIABLES):
    """Décrit la duplication SANS l'exécuter — utile à une confirmation d'IHM."""
    retenues = _valider(copier)
    _, ecartees, a_recalculer = _copier_bordereau(
        affaire.get('bordereau') if 'bordereau' in retenues else ())
    jointes = tuple(str(piece.get('reference') or piece.get('id') or '')
                    for piece in affaire.get('pieces_jointes') or ())
    return PlanDuplication(
        copie=retenues,
        ecarte=tuple(cle for cle in JAMAIS_COPIES if cle in affaire),
        lignes_acheteur_ecartees=ecartees,
        quantites_a_recalculer=a_recalculer,
        pieces_jointes_referencees=jointes)


def dupliquer_affaire(affaire, *, copier=COPIABLES, objet=None):
    """Affaire source → affaire NEUVE (mapping), sans aucun résultat hérité.

    :param affaire: mapping de l'affaire source.
    :param copier: sous-ensemble de `COPIABLES`.
    :param objet: objet du nouveau marché ; à défaut, celui de la source
        suffixé — jamais un objet vide, qui ferait une affaire anonyme.
    :returns: `(nouvelle_affaire, plan)`.
    """
    plan = plan_de_duplication(affaire, copier=copier)
    retenues = set(plan.copie)

    nouvelle = {
        'reference': None,      # attribuée par `core.numbering` au service
        'statut': STATUT_INITIAL,
        'objet': objet or _objet_derive(affaire),
        'duplique_de': affaire.get('reference') or affaire.get('id'),
    }
    for cle in ('geometrie', 'obstacles', 'gabarit_pack', 'exigences'):
        if cle in retenues and cle in affaire:
            nouvelle[cle] = _copie_profonde(affaire[cle])
    if 'bordereau' in retenues:
        lignes, _, _ = _copier_bordereau(affaire.get('bordereau'))
        nouvelle['bordereau'] = list(lignes)

    # Les pièces jointes sont RÉFÉRENCÉES : même objet de stockage, nouvelle
    # affaire. Aucun octet n'est recopié.
    if affaire.get('pieces_jointes'):
        nouvelle['pieces_jointes'] = [
            {'reference': str(piece.get('reference') or piece.get('id') or ''),
             'libelle': str(piece.get('libelle', '')),
             'copie_stockage': False}
            for piece in affaire['pieces_jointes']]

    return nouvelle, plan


def _objet_derive(affaire):
    objet = str(affaire.get('objet') or '').strip()
    return ('%s (copie)' % objet) if objet else 'Nouvelle affaire (copie)'


def _copie_profonde(valeur):
    if hasattr(valeur, 'items'):
        return {cle: _copie_profonde(val) for cle, val in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_copie_profonde(item) for item in valeur]
    return valeur


def trace_chatter(affaire, nouvelle, plan):
    """Le message à déposer au chatter `records` — jamais une classe maison."""
    return {
        'type': 'duplication',
        'objet': 'ao.appeloffre',
        'source': affaire.get('reference') or affaire.get('id'),
        'cible': nouvelle.get('duplique_de'),
        'message': plan.resume,
        'detail': plan.vers_dict(),
    }


def controler_absence_de_resultats(nouvelle):
    """Vérifie qu'aucun résultat n'a survécu à la duplication.

    Le contrôle est exposé (et pas seulement testé) parce que le service qui
    exécutera le plan pourra l'appeler avant d'enregistrer : c'est moins cher
    d'échouer à la création que de découvrir un calepinage hérité au dépôt.
    """
    fautes = sorted(cle for cle in JAMAIS_COPIES
                    if cle in nouvelle and nouvelle[cle] not in (None, '', [],
                                                                 {}))
    if 'statut' in fautes and nouvelle.get('statut') == STATUT_INITIAL:
        fautes.remove('statut')
    lignes = nouvelle.get('bordereau') or ()
    for ligne in lignes:
        if ligne.get('quantite_source') == SOURCE_CALEPINAGE and \
                ligne.get('quantite') is not None:
            fautes.append('bordereau:%s (quantité de calepinage héritée)'
                          % _cle_ligne(ligne))
        if ligne.get('variante_hash'):
            fautes.append('bordereau:%s (variante héritée)' % _cle_ligne(ligne))
    return tuple(fautes)
