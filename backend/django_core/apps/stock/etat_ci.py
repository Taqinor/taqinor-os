"""État C&I d'un produit — règles partagées par Stock (CCAT1, CCAT2).

Un seul endroit pour « le prix est-il connu ? » : le filtre « C&I à compléter »
(``selectors.etat_ci_produit``) et le catalogue de l'étude
(``selectors.produits_ci``) lisaient deux règles différentes. Lecture seule ;
seule lecture cross-app : le repli par mots du nom, via ``apps.ventes.selectors``
(jamais ``ventes.domain`` ni ses modèles).
"""
import logging

from core.product_roles import ROLES_CI_BAREME_COFFRET

logger = logging.getLogger(__name__)


def prix_connu_ci(produit, role):
    """Le prix du produit est-il connu pour le moteur C&I ? Prix de vente saisi
    (> 0), OU — pour un coffret tarifé au barème (``ROLES_CI_BAREME_COFFRET``,
    décision fondateur du 26/10/2026) — un prix fixe ou par panneau saisi : le
    moteur le chiffre (``moteur_ci.composition._appliquer_bareme_coffret``).
    Jamais de prix d'achat."""
    if produit.prix_vente and produit.prix_vente > 0:
        return True
    return (role in ROLES_CI_BAREME_COFFRET
            and (produit.prix_fixe_ht is not None
                 or produit.prix_par_panneau_ht is not None))


# ═══════════════════════════════════════════════════════════════════════════
# CCAT2 — hybrides et batteries de l'option « avec batterie »
# ═══════════════════════════════════════════════════════════════════════════
#
# Un onduleur hybride et une batterie n'ont pas de rôle C&I (``role_ci_pour``
# rend ``(None, None)`` pour l'hybride) : ils restaient INVISIBLES du filtre
# « C&I à compléter » alors que l'option « avec batterie » du devis C&I les
# exige. Mêmes règles que le catalogue du moteur
# (``ventes.domain.etude_ci_batterie.catalogue_batterie_ci``), sans l'importer.

LIBELLE_HYBRIDE = 'Onduleur hybride (option avec batterie)'
LIBELLE_BATTERIE = 'Batterie (option avec batterie)'
#: HT24 (fondateur 24/11/2026) — la famille HAUTE tension de l'option.
LIBELLE_HYBRIDE_HT = 'Onduleur hybride haute tension (option avec batterie)'
LIBELLE_BATTERIE_HT = 'Batterie haute tension (option avec batterie)'
MOTIF_SANS_PRIX = 'prix de vente non saisi'
#: HT24 — les champs de fiche d'une grappe en série, aux noms du formulaire.
CHAMPS_GRAPPE = (('serie_min_modules', 'modules en série par grappe (mini)'),
                 ('serie_max_modules', 'modules en série par grappe (maxi)'),
                 ('v_module', "tension d'un module"))
CHAMPS_PORT_HT = (('bat_nb_entrees', 'entrées batterie'),
                  ('max_parallele', 'appareils en parallèle (maxi)'))


def _role_effectif(produit):
    """``(role_devis, source)`` — déclaré > catégorie > nom ; le repli par mots
    du nom est celui du moteur, lu par le sélecteur de ventes (même lecture
    cross-app que ``serializers.ProduitSerializer._role_resolu``)."""
    from apps.ventes.selectors import classer_produit_nom
    from core.product_roles import role_effectif
    categorie = getattr(produit, 'categorie', None)
    return role_effectif(getattr(produit, 'role_devis', None),
                         getattr(categorie, 'type_equipement', None),
                         getattr(produit, 'nom', ''), classer_produit_nom)


def _num(valeur):
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def _manque_fiche_batterie(produit):
    """Ce qui manque à la fiche d'une batterie (``''`` = complète) : capacité
    utile (``kwh_usable``, sinon nominale × DoD) et tension nominale."""
    from .selectors import specs_for_produit
    fiche = getattr(produit, 'fiche_technique', None)
    if getattr(fiche, 'type_fiche', None) != 'batterie':
        return 'capacité utile, tension nominale'
    specs = specs_for_produit(produit) or {}
    nominal, dod = _num(specs.get('kwh_nominal')), _num(specs.get('dod_pct'))
    utile = _num(specs.get('kwh_usable')) or (
        nominal * dod / 100.0 if nominal and dod else None)
    manque = []
    if not utile:
        manque.append('capacité utile')
    if _num(specs.get('v_nominal')) is None:
        manque.append('tension nominale')
    return ', '.join(manque)


def _prix_vente_saisi(produit):
    return bool(produit.prix_vente and produit.prix_vente > 0)


def _specs_batterie(produit):
    from .selectors import specs_for_produit
    fiche = getattr(produit, 'fiche_technique', None)
    return (specs_for_produit(produit) or {}) if getattr(
        fiche, 'type_fiche', None) == 'batterie' else {}


def _batterie_haute_tension(produit):
    """Pack HAUTE tension : fiche qui déclare une grappe en série (HT24), sinon
    tension nominale > port BT, sinon « haute tension » dans le nom quand la
    tension est volontairement omise (repli des fiches non complétées —
    ``BAT-DYN-HV-16``, ``seed_catalogue`` : la renseigner à 51,2 V ferait entrer
    le pack dans la fenêtre des hybrides BT) — même repli que
    ``ventes.domain.catalogue._is_battery_basse_tension``."""
    from core.product_roles import TENSION_PORT_BT_MAX_V

    from .selectors import _norme
    specs = _specs_batterie(produit)
    if any(specs.get(cle) is not None for cle, _lib in CHAMPS_GRAPPE):
        return True
    v_nominal = _num(specs.get('v_nominal'))
    if v_nominal is not None:
        return v_nominal > TENSION_PORT_BT_MAX_V
    return 'haute tension' in _norme(getattr(produit, 'nom', ''))


def _motif_batterie_ht(produit):
    """HT24 — ce qui manque à un pack haute tension pour l'option : la
    grappe en série, la capacité utile, le prix (``None`` = utilisable)."""
    specs = _specs_batterie(produit)
    manque = [lib for cle, lib in CHAMPS_GRAPPE if _num(specs.get(cle)) is None]
    nominal, dod = _num(specs.get('kwh_nominal')), _num(specs.get('dod_pct'))
    if not (_num(specs.get('kwh_usable')) or (nominal * dod / 100.0 if nominal and dod else None)):
        manque.append('capacité utile')
    if manque:
        return 'fiche incomplète : ' + ', '.join(manque)
    return None if _prix_vente_saisi(produit) else MOTIF_SANS_PRIX


def _motif_port_ht(produit):
    """HT24 — la fiche d'un hybride haute tension publie-t-elle ses entrées
    batterie et sa limite de parallèle ? (sans elles, le moteur retient une
    grappe par appareil et un seul appareil, et le dit)."""
    from .selectors import specs_for_produit
    specs = specs_for_produit(produit) or {}
    manque = [lib for cle, lib in CHAMPS_PORT_HT if specs.get(cle) is None]
    return 'fiche incomplète : ' + ', '.join(manque) if manque else None


def _motif_batterie(produit):
    manque = _manque_fiche_batterie(produit)
    if manque:
        return 'fiche incomplète : ' + manque
    return None if _prix_vente_saisi(produit) else MOTIF_SANS_PRIX


def _etat(role_ci, libelle, classement, produit, motif):
    return {'role_ci': role_ci, 'libelle': libelle, 'classement': classement,
            'prix_connu': _prix_vente_saisi(produit),
            'eligible_ci': motif is None, 'motif_exclusion': motif}


def etat_option_batterie(produit):
    """L'état d'un onduleur hybride ou d'une batterie vis-à-vis de l'option
    « avec batterie » C&I, à la forme de ``etat_ci_produit`` — basse tension
    ou, depuis HT24 (24/11/2026), HAUTE tension (libellé dédié, motif = le
    champ de fiche précis qui manque) ; ``None`` pour un autre produit.
    Lecture seule, jamais de prix d'achat."""
    from core.product_roles import TENSION_PORT_BT_MAX_V

    from .selectors import plage_batterie_onduleur
    role, source = _role_effectif(produit)
    if role == 'onduleur_hybride':
        fiche = getattr(produit, 'fiche_technique', None)
        motif, libelle = None, LIBELLE_HYBRIDE
        if getattr(fiche, 'type_fiche', None) != 'onduleur':
            motif = 'fiche onduleur absente'
        else:
            plage = plage_batterie_onduleur(produit)
            haute = plage is not None and plage[1] > TENSION_PORT_BT_MAX_V
            libelle = LIBELLE_HYBRIDE_HT if haute else LIBELLE_HYBRIDE
            if plage is None:
                motif = 'plage de tension batterie non publiée'
            elif not 0 < plage[1]:
                return None
            elif not (_num(fiche.ond_ac_kw) or 0) > 0:
                # Revue CCAT2 — ``moteur_ci.onduleurs.combiner_onduleurs``
                # écarte aussi un hybride sans puissance AC ni phase publiée.
                motif = 'fiche incomplète : puissance AC'
            elif fiche.ond_phases is None:
                motif = 'phase non publiée'
            elif not _prix_vente_saisi(produit):
                motif = MOTIF_SANS_PRIX
            elif haute:
                motif = _motif_port_ht(produit)
        return _etat('onduleur_hybride', libelle, source, produit, motif)
    if role == 'batterie' or getattr(produit, 'role_ci', '') == 'batterie_ci':
        if _batterie_haute_tension(produit):
            return _etat('batterie', LIBELLE_BATTERIE_HT,
                         source if role == 'batterie' else 'declare', produit,
                         _motif_batterie_ht(produit))
        return _etat('batterie', LIBELLE_BATTERIE,
                     source if role == 'batterie' else 'declare', produit,
                     _motif_batterie(produit))
    return None


LIBELLE_PANNEAU = 'Panneau (devis C&I)'


def etat_panneau(produit):
    """CCAT11 — l'état d'un panneau vis-à-vis du devis C&I, à la forme de
    ``etat_ci_produit`` ; sinon ``None``. Mêmes règles que le catalogue du
    moteur (``ventes.domain.etude_ci.lire_catalogue_ci``) : sans puissance
    Pmax publiée aucun panneau ne se compte, sans prix le module n'est pas
    chiffré — le devis C&I est bloqué dans les deux cas."""
    from .selectors import specs_for_produit
    role, source = _role_effectif(produit)
    if role != 'panneau':
        return None
    try:
        specs = specs_for_produit(produit) or {}
    except Exception:  # fiche illisible : même repli que le moteur
        logger.warning('Fiche illisible pour le produit %s', produit.pk,
                       exc_info=True)
        specs = {}
    pmax = _num(specs.get('pmax_wc'))
    if not pmax or pmax <= 0:
        motif = 'fiche incomplète : puissance (Pmax)'
    elif not _prix_vente_saisi(produit):
        motif = MOTIF_SANS_PRIX
    else:
        motif = None
    return _etat('panneau', LIBELLE_PANNEAU, source, produit, motif)


def etat_ci_complet(produit):
    """``etat_ci_produit`` (rôles C&I) sinon l'état de l'option « avec
    batterie », sinon celui du panneau (CCAT11). Une batterie au rôle ``batterie_ci`` garde son état C&I mais
    sa fiche et son prix sont aussi contrôlés (le moteur l'écarte sinon)."""
    from .selectors import etat_ci_produit
    etat = etat_ci_produit(produit)
    if etat is None:
        return etat_option_batterie(produit) or etat_panneau(produit)
    if etat['role_ci'] == 'batterie_ci' and etat['eligible_ci']:
        motif = (_motif_batterie_ht(produit) if _batterie_haute_tension(produit)
                 else _motif_batterie(produit))
        if motif:
            etat = dict(etat, eligible_ci=False, motif_exclusion=motif)
    if etat['role_ci'] in ('boitier_batterie_ht', 'rack_batterie_ht') and not etat['prix_connu']:
        # HT24 — boîtier de contrôle et rack d'une grappe haute tension, composés
        # en LIGNE de l'option « avec batterie » : sans prix, ils la bloquent.
        etat = dict(etat, eligible_ci=False, motif_exclusion=MOTIF_SANS_PRIX)
    return etat
