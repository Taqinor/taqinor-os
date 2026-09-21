"""CALX183 — AGRÉGER LA PRODUCTION PAR CHAÎNE, MPPT ET ONDULEUR.

CE QUI MANQUAIT
---------------
``services/chaines.py::affectation`` recalcule à chaque lecture la table
module → chaîne → MPPT → onduleur (elle n'est jamais persistée), et
``services/ombrage_chaines.py`` s'en sert pour signaler la chaîne la plus
ombrée. Mais aucune ÉNERGIE n'était jamais agrégée à ce niveau — alors que
c'est EXACTEMENT la maille où se lisent l'écrêtage et le mismatch : un MPPT
suit le point de puissance de la chaîne la plus faible, et un onduleur écrête
la somme de ses MPPT. Une production publiée seulement par pan ou en total ne
montre ni l'un ni l'autre.

LA RÈGLE DURE : LECTURE SEULE, JAMAIS UN RECALCUL
---------------------------------------------------
Ce module ne simule rien. Il lit DEUX sources déjà publiées :

* la table d'affectation RÉELLE (``services/chaines.py::affectation``,
  affectation MANUELLE comprise) — jamais une partition recalculée ici, qui
  serait par construction une AUTRE partition que celle dimensionnée ;
* la simulation module par module
  (``services/simulation_modules.py::production_module_par_module``) — son
  ``par_module`` porte déjà l'énergie et l'accès solaire de chaque module.

Il les CROISE, et c'est tout. Le ``total`` publié est celui de la simulation,
repris tel quel : le recalculer ferait un second total, donc une seconde
vérité.

CE QUI FAIT OMETTRE LE BLOC
-----------------------------
* affectation non calculable ⇒ bloc OMIS avec le motif que
  ``services/chaines.py`` publie (fiche incomplète, aucun pan posé, aucune
  chaîne) — jamais une agrégation sur une partition inventée ;
* ``par_module`` vide (plafond de simulation franchi, aucun pan, aucune
  météo) ⇒ bloc OMIS avec le motif de la simulation ;
* un module affecté dont l'énergie manque ⇒ la chaîne publie ``p50_kwh`` à
  ``None`` en nommant le module, jamais une somme partielle.

LES DEUX PERTES DE LA MAILLE CHAÎNE (D-CALX 7)
------------------------------------------------
``perte_mismatch_pct`` et ``perte_ecretage_pct`` sont LUES dans la cascade de
pertes de la chaîne (liste plate ``pertes``, D-CALX 11) : l'étape
``mismatch_ombrage`` — la seule dispersion que la chaîne de pertes calcule
PAR CHAÎNE (``chaine_pertes.ORDRE_ETAPES`` : « dispersion I-V créée par
l'ombre, par chaîne ») — et l'étape ``ecretage``. Sans cascade fournie pour
cette chaîne, ou quand l'étape est elle-même omise, la clé vaut ``None`` avec
son motif : aucune perte n'est jamais forfaitisée, et ``0 %`` se lirait
« mesuré à zéro ».

Aucun prix, aucune maille d'argent (D-CALX 5). Fonctions PURES : ni base, ni
réseau, ni horloge.
"""
from __future__ import annotations

__all__ = [
    'ETAPE_MISMATCH', 'ETAPE_ECRETAGE', 'affectation_du_calepinage',
    'agregation_production',
]

#: L'étape de la chaîne de pertes qui porte la dispersion PAR CHAÎNE
#: (``chaine_pertes.ORDRE_ETAPES``). ``mismatch_fabricant`` est une
#: dispersion de LOT, la même pour tout le champ : elle ne dit rien d'une
#: chaîne en particulier et n'est donc pas lue ici.
ETAPE_MISMATCH = 'mismatch_ombrage'

#: L'étape de plafonnement en sortie d'onduleur.
ETAPE_ECRETAGE = 'ecretage'

#: Le motif publié quand aucune table d'affectation n'est exploitable.
MOTIF_SANS_AFFECTATION = (
    "aucune table d'affectation n'est calculable : sans le rattachement "
    "module → chaîne → MPPT → onduleur, la production ne peut être agrégée "
    "à aucune de ces trois mailles.")

#: Le motif publié quand la simulation module par module n'a rien rendu.
MOTIF_SANS_PAR_MODULE = (
    "la simulation module par module ne publie aucun module : il n'y a pas "
    "d'énergie à répartir entre les chaînes.")

#: Le motif publié quand la cascade d'une chaîne n'a pas été fournie.
MOTIF_SANS_CASCADE = (
    "aucune cascade de pertes n'est fournie pour cette chaîne : le mismatch "
    "et l'écrêtage ne sont pas lus, et aucune valeur n'est supposée.")


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _arrondi(valeur, decimales=3):
    return None if valeur is None else round(valeur, decimales)


def affectation_du_calepinage(conception, entree_electrique=None):
    """La table d'affectation RÉELLE d'un calepinage, ou son motif.

    Args:
        conception: la ``Conception`` de CAL124 (``services/chaines.py``).
        entree_electrique: l'entrée enregistrée du calepinage — seule la clé
            ``affectation_manuelle`` (CAL234) y est lue.

    Returns:
        ``{affectation, motif, avertissements}``. ``motif`` non vide veut
        dire : il n'y a pas de table, et voici POURQUOI (le motif vient de
        ``services/chaines.py``, jamais d'ici).

    Enveloppe MINCE : elle ne calcule rien, elle lit.
    """
    from .chaines import (
        AffectationInvalide, affectation, normaliser_affectation_imposee,
    )

    avertissements = []
    if conception is None:
        return {'affectation': (), 'motif': MOTIF_SANS_AFFECTATION,
                'avertissements': ()}
    if getattr(conception, 'fiche_incomplete', False):
        return {'affectation': (),
                'motif': 'fiche incomplète — %s'
                         % ', '.join(conception.manquantes),
                'avertissements': ()}
    if conception.resultat is None or not conception.chaines:
        motif = (conception.alertes[0] if conception.alertes
                 else "aucune chaîne calculée : il n'y a rien à agréger")
        return {'affectation': (), 'motif': motif, 'avertissements': ()}

    donnees = entree_electrique if isinstance(entree_electrique, dict) else {}
    try:
        # CAL234 — l'affectation MANUELLE enregistrée écrase l'automatique,
        # et c'est ELLE qui sert à l'agrégation.
        imposee = normaliser_affectation_imposee(
            donnees.get('affectation_manuelle'))
    except AffectationInvalide as refus:
        # Une proposition devenue illisible ne fait pas tomber l'agrégation :
        # la table repart de l'automatique, et le refus se LIT.
        imposee, avertissements = (), [str(refus)]
    return {'affectation': affectation(conception, imposee=imposee),
            'motif': '', 'avertissements': tuple(avertissements)}


def _perte_de_l_etape(cascade, poste):
    """``(perte_pct, motif)`` d'une étape de la cascade — jamais un forfait.

    Une étape absente, OMISE, ou sans pourcentage lisible rend ``None`` avec
    son motif : ``0 %`` se lirait « mesuré à zéro » (D-CALX 7).
    """
    for etape in cascade or ():
        if not isinstance(etape, dict) or etape.get('etape') != poste:
            continue
        if etape.get('motif_omission'):
            return (None, etape['motif_omission'])
        valeur = _nombre(etape.get('perte_pct'))
        if valeur is None:
            return (None, "l'étape « %s » ne publie aucun pourcentage de "
                          "perte." % poste)
        return (valeur, '')
    return (None, "l'étape « %s » n'est pas présente dans la cascade de "
                  "cette chaîne." % poste)


def _energies(production):
    """``{module: ligne}`` de la simulation — lecture seule."""
    lignes = (production or {}).get('par_module') or []
    return {str(ligne.get('module')): ligne for ligne in lignes
            if isinstance(ligne, dict) and ligne.get('module')}


def _motif_de_la_simulation(production):
    """Le motif que la SIMULATION publie quand elle n'a rien à répartir."""
    production = production or {}
    entree = production.get('entree') or {}
    for cle in ('motif_troncature', 'motif_energie'):
        if entree.get(cle):
            return entree[cle]
    return production.get('motif') or MOTIF_SANS_PAR_MODULE


def _cumuler(groupe, ligne):
    """Ajoute un module à un groupe d'agrégation (énergie + accès)."""
    groupe['modules'] += 1
    energie = _nombre(ligne.get('p50_kwh'))
    if energie is None:
        groupe['energie_illisible'] = True
        groupe['modules_sans_energie'].append(ligne.get('module'))
    else:
        groupe['kwh'] += energie
    acces = _nombre(ligne.get('acces_solaire_pct'))
    if acces is not None:
        groupe['acces'].append(acces)


def _groupe_neuf(**identite):
    groupe = {'modules': 0, 'kwh': 0.0, 'acces': [],
              'energie_illisible': False, 'modules_sans_energie': []}
    groupe.update(identite)
    return groupe


def _publier(groupe, cles):
    """La forme publiée d'un groupe : identité, modules, énergie, accès."""
    publie = {cle: groupe.get(cle) for cle in cles}
    publie.update({
        'modules': groupe['modules'],
        'p50_kwh': (None if groupe['energie_illisible']
                    else _arrondi(groupe['kwh'])),
        'acces_min': (min(groupe['acces']) if groupe['acces'] else None),
    })
    return publie


def agregation_production(production, affectation, *, cascades=None):
    """CALX183 — la production agrégée par chaîne, par MPPT et par onduleur.

    Args:
        production: le dict rendu par
            ``services/simulation_modules.py::production_module_par_module``
            (``par_module`` / ``total`` / ``entree``). LU, jamais recalculé.
        affectation: la table RÉELLE de ``services/chaines.py::affectation``
            (ou le ``affectation`` rendu par
            :func:`affectation_du_calepinage`).
        cascades: ``{numéro de chaîne: [étapes de la cascade]}`` — la liste
            plate ``pertes`` de CHAQUE chaîne (D-CALX 11). Absente, les deux
            pertes de la maille chaîne sont omises avec leur motif.

    Returns:
        ``{par_chaine, par_mppt, par_onduleur, hors_chaine, total,
        motif, omissions}``. ``par_chaine`` porte, par ligne :
        ``{chaine, pan, onduleur, mppt, modules, p50_kwh,
        perte_mismatch_pct, perte_ecretage_pct, acces_min}``.

    Fonction PURE : aucune base, aucun réseau, aucune horloge.
    """
    total = (production or {}).get('total') or {}
    vide = {'par_chaine': [], 'par_mppt': [], 'par_onduleur': [],
            'hors_chaine': {'modules': 0, 'p50_kwh': None}, 'total': total,
            'omissions': []}
    if not affectation:
        return dict(vide, motif=MOTIF_SANS_AFFECTATION)
    energies = _energies(production)
    if not energies:
        return dict(vide, motif=_motif_de_la_simulation(production))

    chaines, mppts, onduleurs = {}, {}, {}
    ordre_chaines, ordre_mppts, ordre_onduleurs = [], [], []
    hors = _groupe_neuf()
    omissions = []
    affectes = set()

    for ligne in affectation:
        if not isinstance(ligne, dict):
            continue
        module = str(ligne.get('module') or '')
        energie = energies.get(module)
        if energie is None:
            omissions.append(
                "%s est affecté mais absent de la simulation module par "
                "module : son énergie n'est pas connue." % module)
            continue
        affectes.add(module)
        numero = ligne.get('chaine')
        if numero is None:
            # La « réserve d'appoint » du noyau : posée, câblée à rien. Elle
            # compte dans le total, jamais dans une chaîne.
            _cumuler(hors, energie)
            continue
        cle_chaine = (ligne.get('pan'), numero)
        if cle_chaine not in chaines:
            chaines[cle_chaine] = _groupe_neuf(
                chaine=numero, pan=ligne.get('pan'),
                onduleur=ligne.get('onduleur'), mppt=ligne.get('mppt'))
            ordre_chaines.append(cle_chaine)
        _cumuler(chaines[cle_chaine], energie)

        cle_mppt = (ligne.get('onduleur'), ligne.get('mppt'))
        if cle_mppt not in mppts:
            mppts[cle_mppt] = _groupe_neuf(onduleur=ligne.get('onduleur'),
                                           mppt=ligne.get('mppt'))
            ordre_mppts.append(cle_mppt)
        _cumuler(mppts[cle_mppt], energie)

        cle_onduleur = ligne.get('onduleur')
        if cle_onduleur not in onduleurs:
            onduleurs[cle_onduleur] = _groupe_neuf(onduleur=cle_onduleur)
            ordre_onduleurs.append(cle_onduleur)
        _cumuler(onduleurs[cle_onduleur], energie)

    for module in energies:
        if module not in affectes:
            _cumuler(hors, energies[module])

    par_chaine = []
    for cle in ordre_chaines:
        groupe = chaines[cle]
        publie = _publier(groupe, ('chaine', 'pan', 'onduleur', 'mppt'))
        mismatch, motif_mismatch = _perte_de_l_etape(
            (cascades or {}).get(groupe['chaine']), ETAPE_MISMATCH)
        ecretage, motif_ecretage = _perte_de_l_etape(
            (cascades or {}).get(groupe['chaine']), ETAPE_ECRETAGE)
        if not cascades or groupe['chaine'] not in cascades:
            motif_mismatch = motif_ecretage = MOTIF_SANS_CASCADE
        publie['perte_mismatch_pct'] = mismatch
        publie['perte_ecretage_pct'] = ecretage
        publie['motif_mismatch'] = motif_mismatch
        publie['motif_ecretage'] = motif_ecretage
        par_chaine.append(publie)
        for module in groupe['modules_sans_energie']:
            omissions.append(
                "chaîne %s : l'énergie de %s n'est pas lisible — la chaîne "
                "ne publie aucune somme partielle."
                % (groupe['chaine'], module))

    return {
        'par_chaine': par_chaine,
        'par_mppt': [_publier(mppts[cle], ('onduleur', 'mppt'))
                     for cle in ordre_mppts],
        'par_onduleur': [_publier(onduleurs[cle], ('onduleur',))
                         for cle in ordre_onduleurs],
        'hors_chaine': {
            'modules': hors['modules'],
            'p50_kwh': (None if hors['energie_illisible']
                        else _arrondi(hors['kwh'])),
        },
        # Le total est celui de la SIMULATION, repris tel quel : le
        # recalculer ferait une seconde vérité.
        'total': total,
        'motif': '',
        'omissions': omissions,
    }
