# -*- coding: utf-8 -*-
"""``core.electrique`` — le moteur de CONCEPTION ÉLECTRIQUE PV, paquet PUR.

Frère de ``core.calepinage`` : là où le calepinage répond « combien de modules
tiennent sur cette toiture et où », celui-ci répond « comment on les câble » —
chaînes, onduleurs, protections, sections de câble, nomenclature, schéma
unifilaire. Les deux consommateurs (``apps.ao`` pour la réponse à appel
d'offres, ``apps.ventes`` pour le devis/villa) ne peuvent pas s'importer l'un
l'autre : le moteur vit donc dans la couche fondation ``core``, et sa PURETÉ est
la contrepartie :

* stdlib UNIQUEMENT — zéro ``django``, zéro ``rest_framework``, zéro ``apps.*``,
  zéro autre module de ``core`` ;
* zéro I/O — le moteur ne lit ni n'écrit aucun fichier ; le rendu du schéma
  unifilaire retourne du TEXTE SVG que l'appelant écrit où il veut ;
* zéro globale mutable — toute configuration passe par une ``EntreeElectrique``
  immuable passée en ARGUMENT ;
* AUCUN PRIX — le moteur ne manipule que des grandeurs électriques publiques et
  des quantités. Le chiffrage reste l'affaire du devis.

Bénéfice décisif, identique à celui du calepinage : le paquet est testable SANS
base de données, donc ses tests tournent hors du gate migrations — le poste de
coût CI dominant.

Chaque constante NORMATIVE du moteur cite sa source en commentaire (NF C 15-100,
UTE C 15-712-1, IEC 62548, EN 50618) : un calibre ou une section qu'on ne sait
pas rattacher à une règle est un calibre qu'on ne sait pas défendre devant un
bureau de contrôle.

**Point d'entrée unique : ``concevoir(entree)``** — une ``EntreeElectrique`` en
entrée, un ``ResultatElectrique`` complet en sortie (chaînes, conformité, les
deux ratios, protections, câbles, bordereau, note de calcul, et la projection
``tiroirs`` prête à afficher).

La pureté est armée en CI par le contrat import-linter
``electrique-est-un-noyau-pur`` ET par ``core/tests/test_electrique_purete.py``
(analyse AST : tout import interdit rend le test ROUGE).
"""

import dataclasses

from core.electrique.cables import dimensionner_cables
from core.electrique.chaines import concevoir_chaines
from core.electrique.nomenclature import nomenclature
from core.electrique.note import note_de_calcul
from core.electrique.onduleurs import dimensionner_onduleurs
from core.electrique.protections import concevoir_protections
from core.electrique.types import (
    Cable,
    Chaine,
    Conformite,
    EntreeElectrique,
    GroupePan,
    LigneNomenclature,
    Protection,
    Ratio,
    ResultatElectrique,
    SpecModule,
    SpecOnduleur,
    fr,
)
from core.electrique.version import (
    SCHEMA_VERSION,
    VERSION_MOTEUR,
    compatible,
    version_tuple,
)

__all__ = [
    "SCHEMA_VERSION",
    "VERSION_MOTEUR",
    "compatible",
    "version_tuple",
    "concevoir",
    "projeter_tiroirs",
    "Cable",
    "Chaine",
    "Conformite",
    "EntreeElectrique",
    "GroupePan",
    "LigneNomenclature",
    "Protection",
    "Ratio",
    "ResultatElectrique",
    "SpecModule",
    "SpecOnduleur",
]


def concevoir(entree):
    """PV38 — la conception électrique COMPLÈTE d'une entrée, en un appel.

    Enchaîne les six étages du moteur — chaînes (PV34), onduleurs (PV34),
    protections (PV35), câbles (PV36), bordereau (PV37), note de calcul — puis
    rend un ``ResultatElectrique`` immuable. Ne lève jamais : une entrée
    dégradée produit un résultat vide et une conformité qui DIT pourquoi.

    La puissance DC servant aux ratios est celle RÉELLEMENT raccordée en chaîne
    (les modules en réserve d'appoint ne sont câblés à rien : les compter
    gonflerait artificiellement le ratio DC/AC).
    """
    resultat_chaines = concevoir_chaines(entree)
    puissance_dc = (resultat_chaines.puissance_kwc
                    if resultat_chaines.chaines else entree.puissance_kwc)
    evaluation = dimensionner_onduleurs(entree, puissance_dc)
    resultat_protections = concevoir_protections(entree, resultat_chaines,
                                                 evaluation)
    resultat_cables = dimensionner_cables(entree, resultat_chaines,
                                          resultat_protections)
    resultat_nomenclature = nomenclature(entree, resultat_chaines,
                                         resultat_protections, resultat_cables)

    sources = (resultat_chaines, evaluation, resultat_protections,
               resultat_cables, resultat_nomenclature)
    bloquants = _cumuler(sources, "bloquants")
    alertes = tuple(a for a in _cumuler(sources, "alertes")
                    if a not in bloquants)
    conformite = Conformite(conforme=not bloquants, bloquants=bloquants,
                            alertes=alertes)

    note = note_de_calcul(entree, resultat_chaines, evaluation,
                          resultat_protections, resultat_cables,
                          resultat_nomenclature)

    resultat = ResultatElectrique(
        chaines=resultat_chaines.chaines,
        conformite=conformite,
        ratio_dc_ac=evaluation.ratio_dc_ac,
        ratio_ac_dc=evaluation.ratio_ac_dc,
        protections=resultat_protections.protections,
        cables=resultat_cables.cables,
        bom=resultat_nomenclature.lignes,
        note=note,
        version_moteur=VERSION_MOTEUR,
        schema_version=SCHEMA_VERSION,
    )
    return dataclasses.replace(
        resultat,
        tiroirs=projeter_tiroirs(entree, resultat_chaines, evaluation,
                                 conformite))


def _cumuler(resultats, attribut):
    """Messages de tous les étages, dans l'ordre, sans doublon."""
    vus = set()
    ordonnes = []
    for resultat in resultats:
        for message in getattr(resultat, attribut, ()) or ():
            if message not in vus:
                vus.add(message)
                ordonnes.append(message)
    return tuple(ordonnes)


# ─────────────────────────────────────────────────────────────────────────────
# Projection « tiroirs » — le CONTRAT de charge utile de l'écran.
#
# `frontend/src/features/ao/calepinage/TiroirElectrique.jsx` lit EXACTEMENT :
#   donnees.chaine.{libelle_taille, reste_texte}
#   donnees.onduleurs.{nombre_texte, puissance_texte, plafond_texte}
#   donnees.ratio_dc_ac.{texte, fourchette_texte}
#   donnees.conformite.{conforme, bloquant, alerte,
#                       repartition_proposee{texte, patch}}
# et rien d'autre. Le moteur produit ces clés-là, ni plus ni moins : une clé en
# trop est du code mort côté écran, une clé en moins est une ligne vide.
# Le `patch` de la répartition proposée est étalé tel quel dans le `onChange` de
# l'écran, il doit donc porter la clé de saisie de l'écran (`taille_chaine`).
# ─────────────────────────────────────────────────────────────────────────────
def projeter_tiroirs(entree, resultat_chaines, evaluation, conformite):
    """Charge utile PRÊTE À AFFICHER du tiroir « Contraintes électriques »."""
    return {"electrique": {
        "chaine": {
            "libelle_taille": _libelle_chaines(resultat_chaines),
            "reste_texte": _reste_texte(resultat_chaines),
        },
        "onduleurs": {
            "nombre_texte": _nombre_texte(evaluation),
            "puissance_texte": _puissance_texte(evaluation),
            "plafond_texte": _plafond_texte(evaluation),
        },
        "ratio_dc_ac": {
            "texte": (evaluation.ratio_dc_ac.texte
                      if evaluation.ratio_dc_ac else ""),
            "fourchette_texte": (evaluation.ratio_dc_ac.fourchette_texte
                                 if evaluation.ratio_dc_ac else ""),
        },
        "conformite": {
            "conforme": conformite.conforme,
            "bloquant": conformite.bloquant,
            "alerte": conformite.alerte,
            "repartition_proposee": _proposition(entree, resultat_chaines),
        },
    }}


def _pluriel(nombre, singulier, pluriel=None):
    if abs(nombre) <= 1:
        return "%d %s" % (nombre, singulier)
    return "%d %s" % (nombre, pluriel or (singulier + "s"))


def _libelle_chaines(resultat_chaines):
    """« 2 chaînes de 12 modules » — ou le détail par pan si elles diffèrent."""
    if resultat_chaines is None or not resultat_chaines.chaines:
        return ""
    longueurs = {r.longueur_chaine for r in resultat_chaines.repartitions}
    total = _pluriel(resultat_chaines.nb_chaines, "chaîne")
    if len(longueurs) == 1:
        return "%s de %s" % (total, _pluriel(longueurs.pop(), "module"))
    detail = ", ".join(
        "%s %d × %d" % (r.pan, r.nb_chaines, r.longueur_chaine)
        for r in resultat_chaines.repartitions)
    return "%s (%s)" % (total, detail)


def _reste_texte(resultat_chaines):
    """Le reste n'est jamais caché — mais on n'écrit rien quand il est nul."""
    if resultat_chaines is None or not resultat_chaines.reste_total:
        return ""
    return "%s en réserve d'appoint" % _pluriel(resultat_chaines.reste_total,
                                                "module")


def _nombre_texte(evaluation):
    if evaluation is None or not evaluation.nombre:
        return ""
    return _pluriel(evaluation.nombre, "onduleur")


def _puissance_texte(evaluation):
    if evaluation is None or not evaluation.nombre \
            or evaluation.ac_kw_unitaire <= 0:
        return ""
    if evaluation.nombre == 1:
        return "%s kW AC" % fr(evaluation.ac_kw_unitaire, 1)
    return "%d × %s kW = %s kW AC" % (evaluation.nombre,
                                      fr(evaluation.ac_kw_unitaire, 1),
                                      fr(evaluation.puissance_ac_kw, 1))


def _plafond_texte(evaluation):
    if evaluation is None or not evaluation.nombre:
        return ""
    par_onduleur = "%s kWc par onduleur" % fr(evaluation.dc_par_onduleur_kwc, 1)
    if not evaluation.plafond_kwc_par_onduleur:
        return par_onduleur
    return "%s (plafond %s kWc)" % (
        par_onduleur, fr(evaluation.plafond_kwc_par_onduleur, 0))


def _proposition(entree, resultat_chaines):
    """Répartition CONFORME à proposer, ou ``None`` s'il n'y a rien à proposer.

    Une proposition n'est offerte que si elle CHANGE quelque chose. Deux cas :

    * une longueur IMPOSÉE a été refusée — la proposition remplace la valeur
      SAISIE par l'utilisateur (même si le calcul est déjà retombé sur la
      longueur physique, le champ de l'écran, lui, porte encore la valeur
      refusée et le blocage subsiste tant qu'elle y est) ;
    * le dossier est bloqué sans longueur imposée — on ne propose que si la
      répartition physique diffère de celle en cours. Un bouton qui réapplique
      la valeur déjà en place est pire qu'une absence de bouton.
    """
    if resultat_chaines is None or not resultat_chaines.bloquants:
        return None
    physique = concevoir_chaines(
        dataclasses.replace(entree, longueur_chaine_forcee=None))
    if physique.bloquants or not physique.repartitions:
        return None
    longueurs = {r.longueur_chaine for r in physique.repartitions}
    if len(longueurs) != 1:
        return None
    longueur = longueurs.pop()
    refus_de_longueur_imposee = (
        resultat_chaines.longueur_forcee is not None
        and not resultat_chaines.longueur_forcee_acceptee)
    if refus_de_longueur_imposee:
        if resultat_chaines.longueur_forcee == longueur:
            return None
    else:
        actuelles = {r.longueur_chaine for r in resultat_chaines.repartitions}
        if actuelles == {longueur}:
            return None
    return {
        "texte": _libelle_chaines(physique),
        "patch": {"taille_chaine": longueur},
    }
