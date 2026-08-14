# -*- coding: utf-8 -*-
"""AOF57 — schéma JSON VERSIONNÉ + hash d'entrée au MILLIMÈTRE.

Le contrat JSON est la FRONTIÈRE entre le moteur et la persistance. Il doit
être publié AVANT que la lane des modèles avance, sinon elle recodera son
propre format de rangée et le moteur héritera d'un adaptateur permanent.

**Le hash ne voit JAMAIS un float brut.** Le poste de travail est Windows, la
CI et la production sont Linux : deux additions flottantes menées dans un ordre
différent donnent ``10.760000000000001`` ici et ``10.76`` là-bas. Un hash
calculé dessus ferait croire à deux relevés différents pour la même toiture.
Toutes les longueurs sont donc converties en ENTIERS DE MILLIMÈTRES avant
hachage, et les autres nombres arrondis à 1e-6.

Tout artefact rendu porte le couple ``(hash_entree, version_moteur)`` : deux
planches identiques à l'œil peuvent sortir de deux moteurs différents, et sans
ce couple personne ne sait laquelle fait foi.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple

from core.calepinage.surfaces.arc import SurfaceArc
from core.calepinage.surfaces.base import Coupure
from core.calepinage.surfaces.multi import Palier, SurfaceMultiNiveaux
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    Axe,
    Kit,
    ModePose,
    NatureZone,
    Obstacle,
    OrientationModule,
    Parametres,
    Provenance,
    Rives,
    TypeObstacle,
    Zone,
)
from core.calepinage.units import en_mm, en_metres
from core.calepinage.version import SCHEMA_VERSION, VERSION_MOTEUR

__all__ = [
    "EntreeCalepinage", "ResultatCalepinage", "hash_entree", "migrer",
    "surface_vers_dict", "surface_depuis_dict", "SCHEMA_VERSION",
    "SchemaIncompatible",
]

#: Clés dont la valeur est une LONGUEUR (donc hachée en millimètres entiers).
_CLES_LONGUEUR = frozenset({
    "x0", "x1", "y0", "y1", "position", "origine", "sommets", "contour",
    "trous", "longueur_m", "largeur_m", "developpe_m", "rayon_ext_m",
    "epaisseur_m", "hauteur_m", "retrait_m", "degagement_m", "laterale_m",
    "extremite_m", "acrotere_m", "joint_m", "allee_m", "pas_recherche_m",
    "module_long_m", "module_court_m", "faitage_m", "marge_troncon_min_m",
    "marge_bande_min_m", "rangees_imposees",
})


class SchemaIncompatible(ValueError):
    """Le document JSON n'est pas migrable vers la version courante."""


# --------------------------------------------------------------- primitives
def _rives(r):
    return {"laterale_m": r.laterale_m, "extremite_m": r.extremite_m,
            "acrotere_m": r.acrotere_m, "joint_m": r.joint_m}


def _rives_depuis(d):
    return Rives(laterale_m=d.get("laterale_m", 0.35),
                 extremite_m=d.get("extremite_m", 0.35),
                 acrotere_m=d.get("acrotere_m", 0.0),
                 joint_m=d.get("joint_m", 0.0))


def _coupure(c):
    return {"repere": c.repere, "axe": c.axe, "position": c.position,
            "epaisseur_m": c.epaisseur_m}


def _coupure_depuis(d):
    return Coupure(repere=d["repere"], axe=d["axe"], position=d["position"],
                   epaisseur_m=d.get("epaisseur_m", 0.0))


def _commun_surface(s):
    return {"repere": s.repere, "rives": _rives(s.rives),
            "axe_rangee": s.axe_rangee.value, "niveau": s.niveau,
            "pente_deg": s.pente_deg, "azimut_deg": s.azimut_deg,
            "origine": list(s.origine),
            "coupures": [_coupure(c) for c in s.coupures_declarees]}


def _commun_depuis(d):
    return dict(repere=d["repere"], rives=_rives_depuis(d.get("rives", {})),
                axe_rangee=Axe(d.get("axe_rangee", "NORD_SUD")),
                niveau=d.get("niveau", 0),
                pente_deg=d.get("pente_deg", 0.0),
                azimut_deg=d.get("azimut_deg", 180.0),
                origine=tuple(d.get("origine", (0.0, 0.0))),
                coupures_declarees=tuple(_coupure_depuis(c)
                                         for c in d.get("coupures", ())))


def surface_vers_dict(s):
    """Sérialise une surface — le TYPE est explicite, jamais deviné."""
    base = _commun_surface(s)
    if isinstance(s, SurfaceRectangle):
        base.update(type="rectangle", longueur_m=s.longueur_m,
                    largeur_m=s.largeur_m)
    elif isinstance(s, SurfacePolygone):
        base.update(type="polygone",
                    contour=[list(p) for p in s.contour],
                    trous=[[list(p) for p in t] for t in s.trous])
    elif isinstance(s, SurfaceArc):
        base.update(type="arc", rayon_ext_m=s.rayon_ext_m,
                    largeur_m=s.largeur_m, developpe_m=s.developpe_m)
    elif isinstance(s, SurfaceMultiNiveaux):
        base.update(type="multi_niveaux", largeur_m=s.largeur_m,
                    paliers=[{"repere": p.repere, "x0": p.x0, "x1": p.x1,
                              "niveau": p.niveau, "pente_deg": p.pente_deg,
                              "azimut_deg": p.azimut_deg}
                             for p in s.paliers])
    else:
        raise SchemaIncompatible("surface non sérialisable : %r"
                                 % (type(s).__name__,))
    return base


def surface_depuis_dict(d):
    champs = _commun_depuis(d)
    genre = d.get("type")
    if genre == "rectangle":
        return SurfaceRectangle(longueur_m=d["longueur_m"],
                                largeur_m=d["largeur_m"], **champs)
    if genre == "polygone":
        return SurfacePolygone(
            contour=tuple(tuple(p) for p in d["contour"]),
            trous=tuple(tuple(tuple(p) for p in t)
                        for t in d.get("trous", ())), **champs)
    if genre == "arc":
        return SurfaceArc(rayon_ext_m=d["rayon_ext_m"],
                          largeur_m=d["largeur_m"],
                          developpe_m=d["developpe_m"], **champs)
    if genre == "multi_niveaux":
        return SurfaceMultiNiveaux(
            largeur_m=d["largeur_m"],
            paliers=tuple(Palier(repere=p["repere"], x0=p["x0"], x1=p["x1"],
                                 niveau=p.get("niveau", 0),
                                 pente_deg=p.get("pente_deg", 0.0),
                                 azimut_deg=p.get("azimut_deg", 180.0))
                          for p in d["paliers"]), **champs)
    raise SchemaIncompatible("type de surface inconnu : %r" % (genre,))


def _obstacle(o):
    return {"repere": o.repere, "x0": o.x0, "x1": o.x1, "y0": o.y0,
            "y1": o.y1, "type_obstacle": o.type_obstacle.value,
            "provenance": o.provenance.value, "degagement_m": o.degagement_m,
            "hauteur_m": o.hauteur_m, "regle_appliquee": o.regle_appliquee}


def _obstacle_depuis(d):
    return Obstacle(repere=d["repere"], x0=d["x0"], x1=d["x1"], y0=d["y0"],
                    y1=d["y1"],
                    type_obstacle=TypeObstacle(d.get("type_obstacle",
                                                     "NATURE_INCONNUE")),
                    provenance=Provenance(d.get("provenance", "RELEVE")),
                    degagement_m=d.get("degagement_m"),
                    hauteur_m=d.get("hauteur_m"),
                    regle_appliquee=d.get("regle_appliquee", ""))


def _zone(z):
    return {"repere": z.repere, "nature": z.nature.value,
            "sommets": [list(p) for p in z.sommets],
            "hauteur_m": z.hauteur_m, "retrait_m": z.retrait_m}


def _zone_depuis(d):
    return Zone(repere=d["repere"], nature=NatureZone(d["nature"]),
                sommets=tuple(tuple(p) for p in d["sommets"]),
                hauteur_m=d.get("hauteur_m"),
                retrait_m=d.get("retrait_m", 0.0))


def _kit(k):
    return {"code": k.code, "libelle": k.libelle,
            "module_long_m": k.module_long_m,
            "module_court_m": k.module_court_m,
            "puissance_module_wc": k.puissance_module_wc,
            "inclinaison_deg": k.inclinaison_deg,
            "orientation": k.orientation.value,
            "modules_par_table": k.modules_par_table,
            "faitage_m": k.faitage_m}


def _kit_depuis(d):
    return Kit(code=d["code"], libelle=d.get("libelle", ""),
               module_long_m=d["module_long_m"],
               module_court_m=d["module_court_m"],
               puissance_module_wc=d["puissance_module_wc"],
               inclinaison_deg=d["inclinaison_deg"],
               orientation=OrientationModule(d["orientation"]),
               modules_par_table=d.get("modules_par_table", 2),
               faitage_m=d.get("faitage_m", 0.0))


def _parametres(p):
    document = {"kits": [k.code for k in p.kits], "rives": _rives(p.rives),
                "axe_rangee": p.axe_rangee.value,
                "mode_pose": p.mode_pose.value,
                "allee_m": p.allee_m,
                "degagement_defaut_m": p.degagement_defaut_m,
                "degagement_nature_inconnue_m": p.degagement_nature_inconnue_m,
                "pas_recherche_m": p.pas_recherche_m,
                "engagement_modules": p.engagement_modules,
                "plafond_kwc": p.plafond_kwc,
                "marge_troncon_min_m": p.marge_troncon_min_m,
                "marge_bande_min_m": p.marge_bande_min_m,
                "graine": p.graine}
    # Champ OMIS quand il ne dit rien (PV29). Le hash d'entrée est figé dans
    # les golden : écrire ``"rangees_imposees": null`` dans TOUS les documents
    # ferait bouger l'empreinte de relevés que personne n'a touchés. Absent
    # signifie « pas de plan imposé », exactement comme ``None``.
    if p.rangees_imposees:
        document["rangees_imposees"] = [[y0, code]
                                        for y0, code in p.rangees_imposees]
    return document


def _parametres_depuis(d, kits):
    par_code = {k.code: k for k in kits}
    return Parametres(
        kits=tuple(par_code[c] for c in d["kits"]),
        rives=_rives_depuis(d.get("rives", {})),
        axe_rangee=Axe(d.get("axe_rangee", "NORD_SUD")),
        mode_pose=ModePose(d.get("mode_pose",
                                 ModePose.RANGEES_EXPLICITES_DP.value)),
        allee_m=d.get("allee_m", 0.60),
        degagement_defaut_m=d.get("degagement_defaut_m", 0.30),
        degagement_nature_inconnue_m=d.get("degagement_nature_inconnue_m",
                                           0.50),
        pas_recherche_m=d.get("pas_recherche_m", 0.01),
        engagement_modules=d.get("engagement_modules"),
        plafond_kwc=d.get("plafond_kwc"),
        marge_troncon_min_m=d.get("marge_troncon_min_m", 0.02),
        marge_bande_min_m=d.get("marge_bande_min_m", 0.04),
        rangees_imposees=_rangees_imposees_depuis(d.get("rangees_imposees")),
        graine=d.get("graine", 0))


def _rangees_imposees_depuis(brut):
    """``[[y0, code], …]`` -> ``((y0, code), …)`` — absent ou vide vaut ``None``.

    Les tuples (et non des listes) parce qu'un ``Parametres`` doit rester
    HACHABLE : c'est la clé de mémoïsation du moteur.
    """
    if not brut:
        return None
    return tuple((float(r[0]), str(r[1])) for r in brut)


# ------------------------------------------------------------------- entrée
@dataclass(frozen=True)
class EntreeCalepinage:
    """L'entrée COMPLÈTE d'un calepinage — la frontière moteur/persistance."""

    repere: str
    surfaces: Tuple[object, ...]
    kits: Tuple[Kit, ...]
    parametres: Parametres
    obstacles: Tuple[Obstacle, ...] = ()
    zones: Tuple[Zone, ...] = ()
    engagements: Tuple[Tuple[str, int], ...] = ()
    schema_version: int = SCHEMA_VERSION

    def vers_dict(self):
        return {
            "schema_version": self.schema_version,
            "repere": self.repere,
            "surfaces": [surface_vers_dict(s) for s in self.surfaces],
            "kits": [_kit(k) for k in self.kits],
            "parametres": _parametres(self.parametres),
            "obstacles": [_obstacle(o) for o in self.obstacles],
            "zones": [_zone(z) for z in self.zones],
            "engagements": [list(e) for e in self.engagements],
        }

    @classmethod
    def depuis_dict(cls, document):
        document = migrer(document)
        kits = tuple(_kit_depuis(k) for k in document["kits"])
        return cls(
            repere=document["repere"],
            surfaces=tuple(surface_depuis_dict(s)
                           for s in document["surfaces"]),
            kits=kits,
            parametres=_parametres_depuis(document["parametres"], kits),
            obstacles=tuple(_obstacle_depuis(o)
                            for o in document.get("obstacles", ())),
            zones=tuple(_zone_depuis(z) for z in document.get("zones", ())),
            engagements=tuple(tuple(e)
                              for e in document.get("engagements", ())),
            schema_version=document["schema_version"])

    def vers_json(self, indent=None):
        """JSON canonique (clés triées) — le moteur ne l'ÉCRIT nulle part."""
        return json.dumps(self.vers_dict(), sort_keys=True, indent=indent,
                          ensure_ascii=False)

    @classmethod
    def depuis_json(cls, texte):
        return cls.depuis_dict(json.loads(texte))

    @property
    def hash_entree(self):
        return hash_entree(self)


def _canoniser(valeur, longueur=False):
    """Rend une valeur DÉTERMINISTE : longueurs en mm entiers, reste à 1e-6."""
    if isinstance(valeur, bool) or valeur is None:
        return valeur
    if isinstance(valeur, float):
        return en_mm(valeur) if longueur else round(valeur, 6)
    if isinstance(valeur, int):
        return en_mm(float(valeur)) if longueur else valeur
    if isinstance(valeur, (list, tuple)):
        return [_canoniser(v, longueur) for v in valeur]
    if isinstance(valeur, dict):
        return {cle: _canoniser(val, longueur or cle in _CLES_LONGUEUR)
                for cle, val in sorted(valeur.items())}
    return valeur


def hash_entree(entree):
    """SHA-256 déterministe : clés triées, longueurs arrondies au MILLIMÈTRE.

    Identique sur Windows et sur Linux pour le même relevé — c'est la seule
    raison d'être de la conversion en entiers de millimètres.
    """
    document = entree.vers_dict() if hasattr(entree, "vers_dict") else entree
    canonique = _canoniser(document)
    texte = json.dumps(canonique, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True)
    return hashlib.sha256(texte.encode("ascii")).hexdigest()


def migrer(document, vers=SCHEMA_VERSION):
    """Migration de schéma v(n-1) → v(n). Refuse ce qu'elle ne sait pas migrer."""
    document = dict(document)
    version = document.get("schema_version")
    if version is None:
        raise SchemaIncompatible("document sans schema_version")
    if version > vers:
        raise SchemaIncompatible(
            "document en schéma v%d, moteur en v%d : le moteur est plus ancien "
            "que le document" % (version, vers))
    while version < vers:
        # Aucune migration n'existe encore (schéma v1) : la boucle est la
        # place PRÉVUE pour la première, pas un oubli.
        raise SchemaIncompatible(
            "aucune migration connue de v%d vers v%d" % (version, version + 1))
    document["schema_version"] = vers
    return document


# ------------------------------------------------------------------ résultat
@dataclass(frozen=True)
class ResultatCalepinage:
    """Sortie SÉRIALISABLE — elle porte TOUJOURS (hash_entree, version_moteur)."""

    hash_entree: str
    modules: int
    kwc: float
    rangees: Tuple[Tuple[float, str], ...] = ()
    methode: str = ""
    optimal: bool = False
    version_moteur: str = VERSION_MOTEUR
    schema_version: int = SCHEMA_VERSION
    plancher: Optional[int] = None
    verdict: str = ""

    def vers_dict(self):
        return {"schema_version": self.schema_version,
                "hash_entree": self.hash_entree,
                "version_moteur": self.version_moteur,
                "modules": self.modules, "kwc": round(self.kwc, 6),
                "rangees": [[r[0], r[1]] for r in self.rangees],
                "methode": self.methode, "optimal": self.optimal,
                "plancher": self.plancher, "verdict": self.verdict}

    @classmethod
    def depuis_dict(cls, document):
        document = migrer(document)
        return cls(hash_entree=document["hash_entree"],
                   modules=document["modules"], kwc=document["kwc"],
                   rangees=tuple((r[0], r[1])
                                 for r in document.get("rangees", ())),
                   methode=document.get("methode", ""),
                   optimal=document.get("optimal", False),
                   version_moteur=document.get("version_moteur",
                                               VERSION_MOTEUR),
                   schema_version=document["schema_version"],
                   plancher=document.get("plancher"),
                   verdict=document.get("verdict", ""))

    @classmethod
    def depuis_resultat(cls, entree, resultat, plancher=None, verdict=""):
        kit = entree.parametres.kits[0]
        return cls(hash_entree=hash_entree(entree),
                   modules=resultat.modules,
                   kwc=resultat.modules * kit.puissance_module_wc / 1000.0,
                   rangees=tuple(resultat.rangees),
                   methode=resultat.preuve.methode.value,
                   optimal=resultat.optimal, plancher=plancher,
                   verdict=verdict)


def longueur_depuis_mm(millimetres):
    """Inverse de la canonisation — utile aux tests et aux migrations."""
    return en_metres(millimetres)
