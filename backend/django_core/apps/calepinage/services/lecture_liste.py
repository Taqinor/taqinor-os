"""Ce que la LISTE des calepinages lit SANS rien recalculer : kWc posé, production
annuelle déjà enregistrée, effectifs par statut.

* ``kwc`` — le MÊME calcul que la présentation et les exports
  (``mesures.mesures_du_document`` : la fiche du module de chaque pan du document,
  puis — quand elle décrit CE document, même nombre de modules — le bloc ``pose`` du
  résultat enregistré, lu EN SQL comme le P50). Sans cette seconde lecture, un document
  dont les pans ne portent pas de puissance de module (documents anciens) n'avait aucun
  kWc sur sa carte alors que la simulation le connaît. ``None`` quand rien ne le dit.
* ``production_kwh_an`` — le P50 déjà ENREGISTRÉ par la dernière simulation
  (``resultat.production.total.p50_kwh``). La liste ne charge jamais ``resultat``
  (série horaire, ACAL122) : la valeur est extraite EN SQL (:func:`annoter`),
  aucune requête de plus par ligne. La péremption exacte (empreinte complète)
  coûterait la conception entière de chaque ligne : la liste ne retient que le
  signe qu'elle voit — un nombre de modules poses par la simulation qui n'est plus
  celui du document ⇒ ``None``. L'écran de résultats reste l'arbitre de la fraîcheur.
* ``compteurs_statut`` — les calepinages visibles, comptés par statut DÉRIVÉ en UNE
  requête groupée (même annotation que le filtre ``?statut=``).
* ``points_a_regler`` (ACAL1333) — le DERNIER verdict « Prêt à envoyer ? » rangé par
  la lecture complète (:func:`ranger_verdict`), lu sur la colonne déjà chargée
  (:func:`verdict_range`) : la liste ne lance aucun contrôle.
"""
from __future__ import annotations

from django.db.models import Count
from django.db.models.fields.json import KeyTextTransform

from .approbation import annoter_statut_derive
from .valeurs import nombre

#: Les statuts dérivés servis (``approbation.STATUT_*``), dans l'ordre des puces.
STATUTS_COMPTES = ('brouillon', 'valide', 'perime', 'refuse')

_ATTR_P50 = '_liste_p50_texte'
_ATTR_MODULES_SIMULES = '_liste_modules_simules_texte'
_ATTR_KWC_SIMULE = '_liste_kwc_simule_texte'


def annoter(queryset):
    """Extrait en SQL le P50 enregistré, le nombre de modules et le kWc simulés (clés
    du JSON ``resultat``, bloc ``pose`` = ``chaines.bloc_pose``) sans charger
    ``resultat`` : zéro requête par ligne."""
    production = KeyTextTransform('production', 'resultat')
    total = KeyTextTransform('total', production)
    pose = KeyTextTransform('pose', 'resultat')
    return queryset.annotate(
        **{_ATTR_P50: KeyTextTransform('p50_kwh', total),
           _ATTR_MODULES_SIMULES: KeyTextTransform('total_modules', pose),
           _ATTR_KWC_SIMULE: KeyTextTransform('kwc', pose)})


def _positif(texte):
    """La lecture du module (``valeurs.nombre``), réservée aux valeurs > 0 : ni NaN ni 0 inventé."""
    valeur = nombre(texte)
    return valeur if valeur is not None and valeur > 0 else None


def _mesures(calepinage):
    """``mesures_du_document`` du document stocké, lu UNE fois par ligne."""
    memo = getattr(calepinage, '_liste_mesures', None)
    if memo is None:
        from .mesures import mesures_du_document

        document = getattr(calepinage, 'roof_layout', None)
        pose = {'total_modules': _positif(getattr(calepinage, _ATTR_MODULES_SIMULES, None)),
                'kwc': _positif(getattr(calepinage, _ATTR_KWC_SIMULE, None))}
        resultat = {'pose': pose} if all(v is not None for v in pose.values()) else None
        memo = (mesures_du_document(document, resultat)
                if isinstance(document, dict) and document else {})
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
    p50 = _positif(getattr(calepinage, _ATTR_P50))
    if p50 is None:
        return None
    simules = _positif(getattr(calepinage, _ATTR_MODULES_SIMULES, None))
    poses = _mesures(calepinage).get('modules')
    if simules is not None and poses is not None and int(simules) != int(poses):
        return None
    return int(round(p50))


def ranger_verdict(calepinage, reponse):
    """ACAL1333 — range le verdict de la lecture COMPLÈTE de « Prêt à envoyer ? »
    (``pret_a_envoyer.agreger``, sans ``?etape=``) : ``{lu_le, a_regler, bloquants,
    empreinte}``. Écrit par ``update()`` (ni ``updated_at`` ni version ni journal),
    et seulement quand le verdict ou l'empreinte change : relire ne réécrit rien."""
    from django.utils import timezone

    neuf = {'a_regler': int(reponse['nombre_a_regler']),
            'bloquants': int(reponse['nombre_bloquants']),
            'empreinte': calepinage.layout_hash or ''}
    ancien = calepinage.dernier_verdict or {}
    if all(ancien.get(cle) == valeur for cle, valeur in neuf.items()):
        return
    neuf['lu_le'] = timezone.now().isoformat()
    type(calepinage).objects.filter(pk=calepinage.pk).update(dernier_verdict=neuf)
    calepinage.dernier_verdict = neuf


def verdict_range(calepinage):
    """``{points_a_regler, lu_le, perime}`` du verdict rangé, sans aucun contrôle.

    Jamais lu ⇒ trois ``None`` (jamais un 0). Document changé depuis la lecture
    (empreinte différente) ⇒ ``points_a_regler`` ``None`` et ``perime`` vrai."""
    verdict = getattr(calepinage, 'dernier_verdict', None)
    if not isinstance(verdict, dict) or 'a_regler' not in verdict:
        return {'points_a_regler': None, 'lu_le': None, 'perime': None}
    perime = (verdict.get('empreinte') or '') != (calepinage.layout_hash or '')
    points = int(verdict.get('a_regler') or 0) + int(verdict.get('bloquants') or 0)
    return {'points_a_regler': None if perime else points,
            'lu_le': verdict.get('lu_le'), 'perime': perime}


def _contours_geo(document):
    """Les contours ``[(lat, lng)]`` des pans (``zones[].vertices`` en ``[lng, lat]``),
    à défaut le contour du toit (``outline`` en ``[lat, lng]``) ; les points illisibles
    retirés, un contour de moins de trois points ignoré."""
    def lire(brut, ordre):
        points = []
        for point in brut if isinstance(brut, (list, tuple)) else ():
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                a, b = nombre(point[0]), nombre(point[1])
                if a is not None and b is not None:
                    points.append((a, b) if ordre == 'latlng' else (b, a))
        return points if len(points) >= 3 else None

    zones = document.get('zones') if isinstance(document.get('zones'), list) else []
    contours = [c for c in (lire(z.get('vertices'), 'lnglat') for z in zones if isinstance(z, dict)) if c]
    return contours or [c for c in [lire(document.get('outline'), 'latlng')] if c]


def apercu_du_toit(document):
    """ACAL1334/1335 — ``{viewBox: "0 0 100 100", contours}`` : chaque contour de pan
    projeté à plat (mètres locaux) puis ramené de 0 à 100 dans le cadre COMMUN de tous les
    pans, proportions gardées, y vers le bas ; ``None`` sans contour. Aucun chiffre ajouté."""
    import math

    contours = _contours_geo(document) if isinstance(document, dict) else []
    if not contours:
        return None
    tous = [p for c in contours for p in c]
    lat0 = sum(p[0] for p in tous) / len(tous)
    cosinus = math.cos(math.radians(lat0))
    plats = [[(lng * cosinus, -lat) for lat, lng in c] for c in contours]
    xs, ys = [x for c in plats for x, _ in c], [y for c in plats for _, y in c]
    etendue = max(max(xs) - min(xs), max(ys) - min(ys))
    if not etendue > 0:
        return None
    echelle, marge = 92.0 / etendue, 4.0
    dx = marge + (92.0 - (max(xs) - min(xs)) * echelle) / 2
    dy = marge + (92.0 - (max(ys) - min(ys)) * echelle) / 2
    return {'viewBox': '0 0 100 100',
            'contours': [[[round((x - min(xs)) * echelle + dx, 1), round((y - min(ys)) * echelle + dy, 1)]
                          for x, y in c] for c in plats]}


def apercu_toit(calepinage):
    """L'aperçu du toit de la ligne, lu sur le document DÉJÀ chargé (aucune requête)."""
    return apercu_du_toit(getattr(calepinage, 'roof_layout', None))


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
