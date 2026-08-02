"""AOF114 — registre des règles de dérivation : RECALCULÉ, jamais saisi.

**Le constat.** La bascule de batterie du dossier FRDISI n'a pas été un
renommage de désignation : elle a exigé de RECALCULER tout le bilan de
stockage. 3 piles de 6 packs → 96,48 kWh à 307,2 V par banc → 289,4 kWh
installés → couverture nocturne 100 % avec ≈ 5 kWh d'excédent. Chacun de ces
chiffres apparaît dans plusieurs pièces ; chacun devait bouger ensemble. Un
seul champ saisi dans la chaîne, et la pièce qui le porte devient fausse
silencieusement au premier changement d'équipement.

**La règle du module.** Une grandeur dérivée n'existe PAS en champ saisi. Le
registre le fait respecter mécaniquement : `deriver()` REFUSE une entrée qui
porte le nom d'une grandeur dérivée (`ValeurSaisieInterdite`). On ne peut donc
pas « corriger à la main » un kWh installé — on corrige l'équipement, et toute
la chaîne se rejoue.

**Ce que le module ne fait PAS.** Il ne dérive aucun COMPTE DE MODULES : le
nombre de modules vient du moteur de calepinage via le contrat AOF112 et entre
ici comme donnée d'entrée. Le module en dérive l'ÉLECTROTECHNIQUE (chaînes,
onduleurs, ratio DC/AC), ce qui est une autre question.

**Aucune grandeur d'ingénierie ne porte le mot « marge ».** L'excédent de
couverture nocturne (`excedent_nocturne_kwh`) EST une marge au sens technique,
mais les gardes d'étanchéité des pièces client (AOF129, `rendus/note_calcul`)
refusent tout ce qui porte ce mot : elles ne peuvent pas distinguer une marge
commerciale d'une marge d'ingénierie, et c'est très bien — la sévérité de la
garde ne se relâche pas, c'est la grandeur qui se nomme sans ambiguïté.

Toutes les valeurs sont publiées en pleine précision ; l'arrondi d'affichage
appartient à `core.formats_fr`, jamais au calcul.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Tuple

VERSION_REGISTRE = 1


class ValeurSaisieInterdite(ValueError):
    """Une grandeur DÉRIVÉE a été fournie en entrée — donc figée à la main."""


class EntreeManquante(ValueError):
    """Une donnée d'entrée nécessaire à une règle demandée est absente."""


@dataclass(frozen=True)
class Regle:
    """Une grandeur dérivée : son nom, son unité, ses dépendances, son calcul."""

    cle: str
    libelle: str
    unite: str
    depend: Tuple[str, ...]
    calcul: Callable
    format_explication: str = ''

    def applicable(self, valeurs):
        return all(valeurs.get(d) is not None for d in self.depend)


def _regle(cle, libelle, unite, depend, calcul, explication=''):
    return Regle(cle=cle, libelle=libelle, unite=unite, depend=tuple(depend),
                 calcul=calcul, format_explication=explication)


# --------------------------------------------------------------- stockage
def _capacite_pack_kwh(v):
    return v['tension_pack_v'] * v['capacite_pack_ah'] / 1000.0


def _tension_banc_v(v):
    return v['tension_pack_v'] * v['packs_par_pile']


def _capacite_banc_kwh(v):
    return v['capacite_pack_kwh'] * v['packs_par_pile']


def _packs_total(v):
    return int(v['piles'] * v['packs_par_pile'])


def _capacite_installee_kwh(v):
    return v['capacite_banc_kwh'] * v['piles']


def _capacite_utile_kwh(v):
    return v['capacite_installee_kwh'] * v['profondeur_decharge']


def _excedent_nocturne_kwh(v):
    """Ce qui RESTE de capacité utile une fois la nuit couverte.

    Négatif = la nuit n'est pas tenue (c'est le signal que `controles_cps`
    reprend). Grandeur d'INGÉNIERIE : voir l'avertissement de nommage en tête
    de module — jamais « marge ».
    """
    return v['capacite_utile_kwh'] - v['besoin_nocturne_kwh']


def _couverture_nocturne_pct(v):
    besoin = v['besoin_nocturne_kwh']
    if besoin <= 0:
        return 100.0
    return min(100.0, v['capacite_utile_kwh'] / besoin * 100.0)


# ------------------------------------------------------------- électrique
def _chaines_completes(v):
    return int(v['modules_raccordes'] // v['modules_par_chaine'])


def _modules_hors_chaine(v):
    return int(v['modules_raccordes'] % v['modules_par_chaine'])


def _onduleurs_necessaires(v):
    """Le plus petit nombre d'onduleurs tenant le ratio DC/AC maximal du CPS."""
    capacite_ac = v['calibre_onduleur_kw'] * v['ratio_dc_ac_max']
    if capacite_ac <= 0:
        raise EntreeManquante('calibre onduleur ou ratio DC/AC max nul')
    return int(math.ceil(v['puissance_dc_kwc'] / capacite_ac - 1e-9))


def _puissance_ac_kw(v):
    return v['onduleurs_necessaires'] * v['calibre_onduleur_kw']


def _ratio_dc_ac(v):
    if v['puissance_ac_kw'] <= 0:
        raise EntreeManquante('puissance AC nulle')
    return v['puissance_dc_kwc'] / v['puissance_ac_kw']


def _conforme_cps(v):
    return bool(v['ratio_dc_ac_min'] - 1e-9 <= v['ratio_dc_ac']
                <= v['ratio_dc_ac_max'] + 1e-9)


def _production_annuelle_kwh(v):
    return v['puissance_dc_kwc'] * v['productible_kwh_kwc']


#: Le REGISTRE. Ajouter une grandeur au dossier = ajouter une règle ICI ; il
#: n'existe aucun autre endroit où une grandeur dérivée peut naître.
REGLES = (
    _regle('packs_total', 'Nombre total de packs', 'U',
           ('piles', 'packs_par_pile'), _packs_total,
           '{piles} piles × {packs_par_pile} packs'),
    _regle('capacite_pack_kwh', 'Capacité unitaire d\'un pack', 'kWh',
           ('tension_pack_v', 'capacite_pack_ah'), _capacite_pack_kwh,
           '{tension_pack_v} V × {capacite_pack_ah} Ah'),
    _regle('tension_banc_v', 'Tension d\'un banc', 'V',
           ('tension_pack_v', 'packs_par_pile'), _tension_banc_v,
           '{tension_pack_v} V × {packs_par_pile} packs en série'),
    _regle('capacite_banc_kwh', 'Capacité d\'un banc', 'kWh',
           ('capacite_pack_kwh', 'packs_par_pile'), _capacite_banc_kwh,
           '{capacite_pack_kwh} kWh × {packs_par_pile} packs'),
    _regle('capacite_installee_kwh', 'Capacité installée', 'kWh',
           ('capacite_banc_kwh', 'piles'), _capacite_installee_kwh,
           '{capacite_banc_kwh} kWh × {piles} bancs'),
    _regle('capacite_utile_kwh', 'Capacité utile', 'kWh',
           ('capacite_installee_kwh', 'profondeur_decharge'),
           _capacite_utile_kwh,
           '{capacite_installee_kwh} kWh × {profondeur_decharge}'),
    _regle('excedent_nocturne_kwh', 'Excédent sur le besoin nocturne', 'kWh',
           ('capacite_utile_kwh', 'besoin_nocturne_kwh'),
           _excedent_nocturne_kwh,
           '{capacite_utile_kwh} kWh − {besoin_nocturne_kwh} kWh'),
    _regle('couverture_nocturne_pct', 'Couverture du besoin nocturne', '%',
           ('capacite_utile_kwh', 'besoin_nocturne_kwh'),
           _couverture_nocturne_pct,
           '{capacite_utile_kwh} kWh / {besoin_nocturne_kwh} kWh'),
    _regle('chaines_completes', 'Chaînes complètes', 'U',
           ('modules_raccordes', 'modules_par_chaine'), _chaines_completes,
           '{modules_raccordes} / {modules_par_chaine}'),
    _regle('modules_hors_chaine', 'Modules hors chaîne complète', 'U',
           ('modules_raccordes', 'modules_par_chaine'), _modules_hors_chaine,
           'reste de {modules_raccordes} / {modules_par_chaine}'),
    _regle('onduleurs_necessaires', 'Onduleurs', 'U',
           ('puissance_dc_kwc', 'calibre_onduleur_kw', 'ratio_dc_ac_max'),
           _onduleurs_necessaires,
           '{puissance_dc_kwc} kWc / ({calibre_onduleur_kw} kW × '
           '{ratio_dc_ac_max})'),
    _regle('puissance_ac_kw', 'Puissance AC installée', 'kW',
           ('onduleurs_necessaires', 'calibre_onduleur_kw'), _puissance_ac_kw,
           '{onduleurs_necessaires} × {calibre_onduleur_kw} kW'),
    _regle('ratio_dc_ac', 'Ratio DC/AC', '',
           ('puissance_dc_kwc', 'puissance_ac_kw'), _ratio_dc_ac,
           '{puissance_dc_kwc} kWc / {puissance_ac_kw} kW'),
    _regle('conforme_cps', 'Conformité du ratio DC/AC au CPS', '',
           ('ratio_dc_ac', 'ratio_dc_ac_min', 'ratio_dc_ac_max'),
           _conforme_cps,
           '{ratio_dc_ac_min} ≤ {ratio_dc_ac} ≤ {ratio_dc_ac_max}'),
    _regle('production_annuelle_kwh', 'Production annuelle', 'kWh',
           ('puissance_dc_kwc', 'productible_kwh_kwc'),
           _production_annuelle_kwh,
           '{puissance_dc_kwc} kWc × {productible_kwh_kwc} kWh/kWc'),
)

PAR_CLE = {r.cle: r for r in REGLES}

#: Les noms qu'aucune entrée n'a le droit de porter : ce sont des RÉSULTATS.
CLES_DERIVEES = frozenset(PAR_CLE)

#: Valeurs de cadrage — une entrée non fournie les prend, elles ne sont pas des
#: grandeurs dérivées (ce sont des conventions de projet, pas des résultats).
DEFAUTS = {
    'profondeur_decharge': 1.0,
    'modules_par_chaine': 16,
    'ratio_dc_ac_min': 1.0,
    'ratio_dc_ac_max': 1.3,
}


def deriver(entrees, *, cles=None, defauts=DEFAUTS):
    """Rejoue TOUTE la chaîne de dérivation à partir des seules entrées.

    :param entrees: mapping des données SAISIES (équipement, besoins, CPS).
        Aucune clé ne peut être le nom d'une grandeur dérivée.
    :param cles: restreint le calcul à ces grandeurs et à leurs dépendances.
    :raises ValeurSaisieInterdite: une grandeur dérivée a été fournie.
    :returns: mapping {clé dérivée: valeur}, en pleine précision.
    """
    saisies_interdites = sorted(CLES_DERIVEES & set(entrees))
    if saisies_interdites:
        raise ValeurSaisieInterdite(
            'ces grandeurs sont DÉRIVÉES et ne peuvent pas être saisies : %s — '
            'corriger l\'équipement ou le besoin, pas le résultat'
            % ', '.join(saisies_interdites))

    valeurs = dict(defauts or {})
    valeurs.update({cle: val for cle, val in entrees.items()
                    if val is not None})

    demandees = set(cles) if cles else set(CLES_DERIVEES)
    inconnues = sorted(demandees - CLES_DERIVEES)
    if inconnues:
        raise KeyError('grandeurs inconnues du registre : %s'
                       % ', '.join(inconnues))

    derivees = {}
    restantes = [r for r in REGLES if r.cle in _fermeture(demandees)]
    progression = True
    while restantes and progression:
        progression = False
        for regle in list(restantes):
            if not regle.applicable(valeurs):
                continue
            valeur = regle.calcul(valeurs)
            valeurs[regle.cle] = valeur
            derivees[regle.cle] = valeur
            restantes.remove(regle)
            progression = True
    return derivees


def _fermeture(cles):
    """Les grandeurs demandées PLUS toutes celles dont elles dépendent."""
    a_traiter, vues = list(cles), set()
    while a_traiter:
        cle = a_traiter.pop()
        if cle in vues or cle not in PAR_CLE:
            continue
        vues.add(cle)
        a_traiter.extend(PAR_CLE[cle].depend)
    return vues


def chaine_de_derivation(cle):
    """Les grandeurs dérivées dont `cle` dépend, des plus profondes à elle.

    Sert au message « ce chiffre a changé PARCE QUE … » : une pièce périmée
    sans motif s'apprend à ignorer.
    """
    if cle not in PAR_CLE:
        raise KeyError('grandeur inconnue du registre : %s' % cle)
    ordre = []
    for candidate in REGLES:
        if candidate.cle in _fermeture({cle}):
            ordre.append(candidate.cle)
    return tuple(ordre)


def dependants(cle):
    """Toutes les grandeurs dérivées qu'un changement de `cle` fait bouger."""
    touches, progression = {cle}, True
    while progression:
        progression = False
        for regle in REGLES:
            if regle.cle in touches:
                continue
            if touches & set(regle.depend):
                touches.add(regle.cle)
                progression = True
    return tuple(sorted(touches - {cle}))


def explication(cle, entrees, derivees=None):
    """Phrase GÉNÉRÉE expliquant d'où sort un chiffre — jamais rédigée.

    « Capacité installée = 96,48 kWh × 3 bancs = 289,44 kWh ».
    """
    regle = PAR_CLE[cle]
    valeurs = dict(DEFAUTS)
    valeurs.update({k: v for k, v in entrees.items() if v is not None})
    valeurs.update(derivees or deriver(entrees, cles=(cle,)))
    if cle not in valeurs:
        raise EntreeManquante(
            '%s ne peut pas être calculé : dépendances manquantes (%s)'
            % (cle, ', '.join(d for d in regle.depend
                              if valeurs.get(d) is None)))
    detail = regle.format_explication.format(
        **{d: _nombre(valeurs.get(d)) for d in regle.depend})
    unite = (' ' + regle.unite) if regle.unite else ''
    return '%s = %s = %s%s' % (regle.libelle, detail,
                               _nombre(valeurs[cle]), unite)


def _nombre(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return str(valeur)
    if isinstance(valeur, float) and valeur == int(valeur):
        return str(int(valeur))
    if isinstance(valeur, float):
        return ('%.4f' % valeur).rstrip('0').rstrip('.')
    return str(valeur)


def controles_cps(derivees):
    """Les non-conformités au CPS, prêtes à devenir un blocage de dépôt."""
    anomalies = []
    if derivees.get('conforme_cps') is False:
        anomalies.append(
            'ratio DC/AC %.3f hors de la bande imposée par le CPS'
            % derivees.get('ratio_dc_ac', 0.0))
    if derivees.get('modules_hors_chaine'):
        anomalies.append(
            '%d module(s) hors chaîne complète — le schéma unifilaire doit '
            'les rattacher explicitement'
            % derivees['modules_hors_chaine'])
    couverture = derivees.get('couverture_nocturne_pct')
    if couverture is not None and couverture < 100.0:
        anomalies.append(
            'couverture nocturne %.1f %% : le besoin nocturne n\'est pas tenu'
            % couverture)
    return tuple(anomalies)
