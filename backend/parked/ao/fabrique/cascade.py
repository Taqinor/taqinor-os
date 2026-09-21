"""AOF158 — cascade de prix INVERSE : un solveur, pas une règle de trois.

**Le sens de marche.** Le moteur de devis part du prix unitaire et remonte au
total. Un appel d'offres part de la MARGE : coût de revient par poste +
bénéfice net HT visé → total HT cible → répartition sur les prix unitaires.
C'est un MODE DE CALCUL SUPPLÉMENTAIRE, pas une variante du même — d'où un
module séparé qui ne touche pas `/proposal` (règle #4).

**Pourquoi ce n'est pas une simple proportion.** Une homothétie brute produit
des prix du type 2 947,33 DH le module. Un bordereau rempli de prix à deux
décimales aléatoires dit à la commission qu'on a réparti un total en marche
arrière — cela décrédibilise l'offre, et cela se voit au premier coup d'œil.
Les prix du bordereau réel sont ronds et crédibles : modules 2 950, onduleurs
78 000, batteries 2 600/kWh, coffret DC 4 500, AC 8 500, TGPV 15 000, station
météo 50 000, afficheur 39 500, études d'exécution 262 000, EMS 200 000, génie
civil 120 000, essais/DOE 70 000.

**L'algorithme.**

1. cible HT = Σ coûts de revient + bénéfice net visé ;
2. facteur d'homothétie = cible / base (base = Σ q × PU de référence) ;
3. chaque PU est multiplié puis ARRONDI au pas métier de son ordre de grandeur
   (50 / 100 / 500 / 1 000 DH — les quatre pas que portent les prix réels) ;
4. l'arrondi crée un résidu de quelques milliers de dirhams : il est reporté
   sur UNE ligne d'ajustement désignée (un poste forfaitaire), jamais dilué ;
5. l'invariant `Σ quantité × PU == cible` est ASSERTÉ au centime à
   l'exécution. Pas un test : une assertion — un bordereau qui rate sa cible
   d'un centime rate sa marge du même montant, et personne ne le verrait.

**Aucun coût ne sort.** Les coûts et le bénéfice sont des ENTRÉES réservées au
directeur (AOF157). `vers_dict()` — ce que voit tout le monde — n'en contient
aucun ; `vers_dict_directeur()` est le seul accès, et son nom rend un usage
accidentel impossible à confondre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple

CENTIME = Decimal('0.01')

#: Pas d'arrondi métier par ordre de grandeur. Les seuils sont CALÉS sur les
#: prix réels du bordereau déposé : 2 950 exige un pas de 50 (il n'est pas
#: multiple de 100), 8 500 et 15 000 tiennent au pas de 100, 39 500 au pas de
#: 500, et tout ce qui dépasse 50 000 est rond au millier.
PAS_METIER = (
    (Decimal('5000'), Decimal('50')),
    (Decimal('20000'), Decimal('100')),
    (Decimal('50000'), Decimal('500')),
    (None, Decimal('1000')),
)

#: Seuil psychologique par défaut : rester SOUS les 5 000 000 DH TTC.
SEUIL_PSYCHOLOGIQUE_TTC = Decimal('5000000')


class CascadeImpossible(ValueError):
    """Les entrées ne permettent pas d'atteindre la cible."""


class AjustementImpossible(CascadeImpossible):
    """Aucune ligne d'ajustement ne peut absorber le résidu exactement."""


class InvariantRompu(AssertionError):
    """`Σ q × PU` ne vaut pas la cible au centime — refusé, jamais absorbé."""


def _d(valeur, defaut=None):
    if valeur is None or valeur == '':
        return defaut
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def pas_de(prix, pas_metier=PAS_METIER):
    """Le pas d'arrondi applicable à un prix, selon son ordre de grandeur."""
    montant = abs(_d(prix, Decimal('0')))
    for seuil, pas in pas_metier:
        if seuil is None or montant < seuil:
            return pas
    return pas_metier[-1][1]


def arrondir_metier(prix, pas_metier=PAS_METIER):
    """Arrondit un prix au pas métier de son ordre de grandeur."""
    montant = _d(prix, Decimal('0'))
    pas = pas_de(montant, pas_metier)
    return (montant / pas).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * pas


def est_sur_le_pas(prix, pas_metier=PAS_METIER):
    montant = _d(prix, Decimal('0'))
    return montant % pas_de(montant, pas_metier) == 0


@dataclass(frozen=True)
class Cascade:
    """Le résultat du solveur. Ce que tout le monde voit ne contient AUCUN coût."""

    cible_ht: Decimal
    cible_ttc: Decimal
    taux_tva: Decimal
    facteur: Decimal
    lignes: Tuple[dict, ...] = field(default_factory=tuple)
    ligne_ajustement: str = ''
    residu_reporte: Decimal = Decimal('0')
    alertes: Tuple[str, ...] = field(default_factory=tuple)
    _couts_ht: Decimal = Decimal('0')
    _benefice_vise: Decimal = Decimal('0')

    @property
    def total_calcule_ht(self):
        return sum((_montant(ligne) for ligne in self.lignes), Decimal('0'))

    @property
    def marge_pct(self):
        """RÉSERVÉ AU DIRECTEUR — ne jamais inclure dans un rendu client."""
        if not self.cible_ht:
            return Decimal('0')
        return (self._benefice_vise / self.cible_ht * Decimal('100')).quantize(
            Decimal('0.1'), rounding=ROUND_HALF_UP)

    def vers_dict(self):
        """Vue COMMUNE : cible, prix, résidu. Aucun coût, aucune marge."""
        return {'cible_ht': str(self.cible_ht),
                'cible_ttc': str(self.cible_ttc),
                'taux_tva': str(self.taux_tva),
                'facteur': str(self.facteur),
                'ligne_ajustement': self.ligne_ajustement,
                'residu_reporte': str(self.residu_reporte),
                'alertes': list(self.alertes),
                'lignes': [_ligne_publique(ligne) for ligne in self.lignes]}

    def vers_dict_directeur(self):
        """Vue DIRECTEUR (`ao_rentabilite_voir`) — la seule qui porte l'économie."""
        return dict(self.vers_dict(), couts_ht=str(self._couts_ht),
                    benefice_vise=str(self._benefice_vise),
                    marge_pct=str(self.marge_pct))


def _ligne_publique(ligne):
    return {cle: (str(val) if isinstance(val, Decimal) else val)
            for cle, val in ligne.items()
            if not str(cle).startswith('_')}


def _montant(ligne):
    quantite = _d(ligne.get('quantite'), Decimal('0'))
    prix = _d(ligne.get('prix_unitaire'), Decimal('0'))
    return (quantite * prix).quantize(CENTIME, rounding=ROUND_HALF_UP)


def _cle(ligne):
    return str(ligne.get('cle') or ligne.get('numero')
               or ligne.get('designation') or '')


def cible(couts, benefice_vise, *, taux_tva=Decimal('20')):
    """Coûts + bénéfice visé → `(cible HT, cible TTC)`.

    :param couts: total HT, ou itérable de mappings `{poste, montant}`.
    """
    total_couts = _total_couts(couts)
    benefice = _d(benefice_vise, Decimal('0'))
    ht = (total_couts + benefice).quantize(CENTIME)
    tva = (ht * _d(taux_tva) / Decimal('100')).quantize(CENTIME,
                                                        rounding=ROUND_HALF_UP)
    return ht, (ht + tva).quantize(CENTIME)


def _total_couts(couts):
    if couts is None:
        return Decimal('0')
    if isinstance(couts, (int, float, str, Decimal)):
        return _d(couts, Decimal('0'))
    if hasattr(couts, 'items'):
        return sum((_d(v, Decimal('0')) for v in couts.values()),
                   Decimal('0'))
    return sum((_d(poste.get('montant'), Decimal('0')) for poste in couts),
               Decimal('0'))


def _choisir_ligne_ajustement(lignes, demandee):
    """Un poste FORFAITAIRE (quantité 1) : lui seul absorbe un résidu exact."""
    if demandee:
        for ligne in lignes:
            if _cle(ligne) == str(demandee):
                return ligne
        raise AjustementImpossible(
            "ligne d'ajustement désignée introuvable : %s" % demandee)
    forfaits = [ligne for ligne in lignes
                if _d(ligne.get('quantite')) == Decimal('1')
                and _d(ligne.get('prix_unitaire'))]
    if not forfaits:
        raise AjustementImpossible(
            "aucune ligne forfaitaire (quantité 1) pour absorber le résidu : "
            "en désigner une explicitement")
    return max(forfaits, key=lambda ligne: _d(ligne.get('prix_unitaire')))


def resoudre(lignes, *, couts, benefice_vise, taux_tva=Decimal('20'),
             ligne_ajustement=None, pas_metier=PAS_METIER,
             seuil_psychologique=SEUIL_PSYCHOLOGIQUE_TTC):
    """Répartit la cible sur les PU. L'invariant est ASSERTÉ, pas espéré.

    :param lignes: bordereau de référence (PU de départ, quantités figées).
    :param couts: coût de revient HT (total ou postes) — entrée DIRECTEUR.
    :param benefice_vise: bénéfice net HT visé — entrée DIRECTEUR.
    :param ligne_ajustement: clé de la ligne qui portera le résidu ; à défaut,
        le plus gros poste forfaitaire.
    :raises InvariantRompu: si `Σ q × PU` rate la cible d'un centime.
    """
    taux = _d(taux_tva, Decimal('20'))
    cible_ht, cible_ttc = cible(couts, benefice_vise, taux_tva=taux)
    lignes = [dict(ligne) for ligne in lignes or ()]
    if not lignes:
        raise CascadeImpossible('aucune ligne à valoriser')

    base = sum((_montant(ligne) for ligne in lignes), Decimal('0'))
    if base <= 0:
        raise CascadeImpossible(
            'le bordereau de référence ne porte aucun prix : la cascade '
            'répartit, elle ne crée pas un chiffrage de rien')
    facteur = (cible_ht / base)

    ajustement = _choisir_ligne_ajustement(lignes, ligne_ajustement)
    cle_ajustement = _cle(ajustement)

    sorties = []
    for ligne in lignes:
        nouvelle = dict(ligne)
        prix = _d(ligne.get('prix_unitaire'))
        if prix is not None:
            nouvelle['prix_unitaire'] = arrondir_metier(prix * facteur,
                                                        pas_metier)
        sorties.append(nouvelle)

    # Le résidu d'arrondi va ENTIÈREMENT sur la ligne désignée.
    autres = sum((_montant(ligne) for ligne in sorties
                  if _cle(ligne) != cle_ajustement), Decimal('0'))
    ligne_cible = next(ligne for ligne in sorties
                       if _cle(ligne) == cle_ajustement)
    quantite = _d(ligne_cible.get('quantite'), Decimal('0'))
    if quantite <= 0:
        raise AjustementImpossible(
            "la ligne d'ajustement « %s » n'a pas de quantité" % cle_ajustement)
    reste = (cible_ht - autres).quantize(CENTIME)
    prix_ajuste = (reste / quantite).quantize(CENTIME, rounding=ROUND_HALF_UP)
    if (prix_ajuste * quantite).quantize(CENTIME) != reste:
        raise AjustementImpossible(
            "le résidu %s ne se répartit pas exactement sur %s unités de "
            "« %s » : désigner une ligne forfaitaire (quantité 1)"
            % (reste, quantite, cle_ajustement))
    residu = (prix_ajuste - _d(ligne_cible['prix_unitaire'],
                               Decimal('0'))) * quantite
    ligne_cible['prix_unitaire'] = prix_ajuste

    total = sum((_montant(ligne) for ligne in sorties), Decimal('0'))
    if total != cible_ht:
        raise InvariantRompu(
            'Σ q × PU = %s alors que la cible est %s (écart %s) — la cascade '
            'refuse de publier un bordereau qui rate sa marge'
            % (total, cible_ht, total - cible_ht))

    alertes = []
    if seuil_psychologique is not None and cible_ttc >= _d(
            seuil_psychologique):
        alertes.append(
            'total TTC %s au-dessus du seuil psychologique %s'
            % (cible_ttc, _d(seuil_psychologique)))
    if prix_ajuste <= 0:
        alertes.append(
            "le report du résidu rend le prix de « %s » nul ou négatif"
            % cle_ajustement)

    return Cascade(cible_ht=cible_ht, cible_ttc=cible_ttc, taux_tva=taux,
                   facteur=facteur, lignes=tuple(sorties),
                   ligne_ajustement=cle_ajustement,
                   residu_reporte=residu.quantize(CENTIME),
                   alertes=tuple(alertes),
                   _couts_ht=_total_couts(couts),
                   _benefice_vise=_d(benefice_vise, Decimal('0')))


def verifier_invariant(lignes, cible_ht):
    """Contrôle autonome : `Σ q × PU == cible` au centime."""
    total = sum((_montant(ligne) for ligne in lignes or ()), Decimal('0'))
    if total != _d(cible_ht):
        raise InvariantRompu('Σ q × PU = %s ≠ cible %s' % (total,
                                                           _d(cible_ht)))
    return True


def prix_non_ronds(cascade, pas_metier=PAS_METIER):
    """Les PU qui ne tombent pas sur leur pas métier.

    La ligne d'ajustement en fait partie par construction : c'est elle qui
    porte le résidu, et c'est le prix à payer pour que le total soit exact.
    Elle est retournée nommément plutôt que masquée.
    """
    hors_pas = []
    for ligne in cascade.lignes:
        prix = _d(ligne.get('prix_unitaire'))
        if prix is None or est_sur_le_pas(prix, pas_metier):
            continue
        hors_pas.append({'cle': _cle(ligne), 'prix_unitaire': prix,
                         'pas': pas_de(prix, pas_metier),
                         'ligne_ajustement':
                             _cle(ligne) == cascade.ligne_ajustement})
    return tuple(hors_pas)


def appliquer(lignes_bordereau, cascade):
    """Reporte les PU de la cascade dans le bordereau — SANS écrire un coût."""
    prix = {_cle(ligne): ligne.get('prix_unitaire')
            for ligne in cascade.lignes}
    sorties = []
    for ligne in lignes_bordereau or ():
        nouvelle = dict(ligne)
        if _cle(ligne) in prix:
            nouvelle['prix_unitaire'] = prix[_cle(ligne)]
        sorties.append(nouvelle)
    return tuple(sorties)
