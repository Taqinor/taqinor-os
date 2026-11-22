"""Ce que la LISTE des calepinages lit SANS rien recalculer : kWc posé, production
annuelle déjà enregistrée, effectifs par statut.

* ``kwc`` — le MÊME calcul que la présentation et les exports
  (``mesures.mesures_du_document`` : la fiche du module de chaque pan du document),
  jamais une simulation. ``None`` quand le document ne dit rien.
* ``production_kwh_an`` — le P50 déjà ENREGISTRÉ par la dernière simulation
  (``resultat.production.total.p50_kwh``). La liste ne charge jamais ``resultat``
  (série horaire, ACAL122) : la valeur est extraite EN SQL (:func:`annoter`),
  aucune requête de plus par ligne. La péremption exacte (empreinte complète)
  coûterait la conception entière de chaque ligne : la liste ne retient que le
  signe qu'elle voit — un nombre de modules poses par la simulation qui n'est plus
  celui du document ⇒ ``None``. L'écran de résultats reste l'arbitre de la fraîcheur.
* ``compteurs_statut`` — les calepinages visibles, comptés par statut DÉRIVÉ en UNE
  requête groupée (même annotation que le filtre ``?statut=``).
"""
from __future__ import annotations

from django.db.models import Count
from django.db.models.fields.json import KeyTextTransform

from .approbation import annoter_statut_derive

#: Les statuts dérivés servis (``approbation.STATUT_*``), dans l'ordre des puces.
STATUTS_COMPTES = ('brouillon', 'valide', 'perime', 'refuse')

_ATTR_P50 = '_liste_p50_texte'
_ATTR_MODULES_SIMULES = '_liste_modules_simules_texte'


def annoter(queryset):
    """Extrait en SQL le P50 enregistré et le nombre de modules simulés (clés du
    JSON ``resultat``) sans charger ``resultat`` : zéro requête par ligne."""
    production = KeyTextTransform('production', 'resultat')
    total = KeyTextTransform('total', production)
    return queryset.annotate(
        **{_ATTR_P50: KeyTextTransform('p50_kwh', total),
           _ATTR_MODULES_SIMULES: KeyTextTransform(
               'modules', KeyTextTransform('pose', 'resultat'))})


def _nombre(texte):
    try:
        valeur = float(texte)
    except (TypeError, ValueError):
        return None
    return valeur if valeur == valeur and valeur > 0 else None  # ni NaN ni 0 inventé


def _mesures(calepinage):
    """``mesures_du_document`` du document stocké, lu UNE fois par ligne."""
    memo = getattr(calepinage, '_liste_mesures', None)
    if memo is None:
        from .mesures import mesures_du_document

        document = getattr(calepinage, 'roof_layout', None)
        memo = mesures_du_document(document) if isinstance(document, dict) and document else {}
        try:
            calepinage._liste_mesures = memo
        except AttributeError:  # objet figé : pas de mémo, rien de faux
            pass
    return memo


def kwc_pose(calepinage):
    """kWc du document de pose, arrondi au centième ; ``None`` s'il est inconnu."""
    kwc = _mesures(calepinage).get('kwc')
    return round(float(kwc), 2) if isinstance(kwc, (int, float)) and kwc > 0 else None


def production_annuelle(calepinage):
    """P50 enregistré (kWh/an, entier) ; ``None`` sans simulation lisible ou quand le
    nombre de modules simulés n'est plus celui du document."""
    if not hasattr(calepinage, _ATTR_P50):
        return None  # ligne non annotée (détail, écriture) : la liste est seule à le servir
    p50 = _nombre(getattr(calepinage, _ATTR_P50))
    if p50 is None:
        return None
    simules = _nombre(getattr(calepinage, _ATTR_MODULES_SIMULES, None))
    poses = _mesures(calepinage).get('modules')
    if simules is not None and poses is not None and int(simules) != int(poses):
        return None
    return int(round(p50))


def compteurs_statut(lignes):
    """``{tous, brouillon, valide, perime, refuse}`` de ``lignes`` — un queryset DÉJÀ
    borné société, vue du responsable, recherche et filtres, SAUF le statut : UNE
    requête groupée."""
    groupes = (annoter_statut_derive(lignes).order_by()
               .values('statut_derive').annotate(n=Count('id')))
    comptes = {statut: 0 for statut in STATUTS_COMPTES}
    for groupe in groupes:
        comptes[groupe['statut_derive']] = groupe['n']
    return {'tous': sum(comptes.values()), **comptes}
