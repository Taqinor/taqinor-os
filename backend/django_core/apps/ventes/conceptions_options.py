# -*- coding: utf-8 -*-
"""D-ACAL-158 (fondateur, 26/11/2026) — la conception électrique de CHAQUE option
d'un devis à deux options, rangée à l'envoi (déplacée hors de
``electrical_service`` pour qu'il reste sous le seuil de 2 000 lignes du garde
C20 FICHIER_MUR). Les
lecteurs (``electrical_service._document_de_l_option``, ``annexes_par_option``),
l'envoi (``domain.envoi.geler_document_engage``) et le POST
``conception-electrique`` l'importent ici, à l'appel (aucune façade)."""
import contextlib
import logging

from apps.ventes import electrical_service as E

#: Même journal que ``electrical_service`` (les avertissements d'envoi s'y lisent).
logger = logging.getLogger("apps.ventes.electrical_service")


# ── D-ACAL-158 — UNE CONCEPTION RANGÉE PAR OPTION, À L'ENVOI ────────────────
#
# Fondateur, 26/11/2026 : à l'envoi d'un devis à deux options, la conception de
# l'option que ``electrical_design`` ne porte pas est rangée aussi, dans une
# entrée INTERNE de ``clauses_appliquees`` (même mécanique que les réglages
# figés, ADVS2) : ``electrical_design``, ``electrical_design_hash`` et la
# fonction d'empreinte ne changent pas. Écrite seulement au passage d'un
# brouillon vers envoyé/accepté (``domain.envoi.geler_document_engage``) puis
# suivie par les corrections sur place d'un devis qui la porte : un devis
# envoyé avant n'en reçoit jamais, sa page et son PDF restent ceux reçus.

def _entree_conceptions_figees(devis):
    """L'entrée rangée à l'envoi (aussi sur un mono-option, ``options: {}``), ou
    ``None`` : brouillon (par prudence : aucune copie — révision, duplication —
    ne reporte ``clauses_appliquees``, ``domain.creation_clone.cloner_devis``) ou
    devis envoyé avant D-ACAL-158."""
    from apps.ventes.domain.envoi import TYPE_CONCEPTIONS_OPTIONS_FIGEES
    if getattr(devis, "statut", None) == "brouillon":
        return None
    for c in (getattr(devis, "clauses_appliquees", None) or []):
        if isinstance(c, dict) and c.get("type") == TYPE_CONCEPTIONS_OPTIONS_FIGEES:
            return c
    return None


def _conceptions_figees(devis):
    """``{clé d'option: {design, hash}}`` rangées à l'envoi (``{}`` sinon)."""
    options = (_entree_conceptions_figees(devis) or {}).get("options")
    if not isinstance(options, dict):
        return {}
    return {cle: valeur for cle, valeur in options.items()
            if isinstance(valeur, dict) and isinstance(valeur.get("design"), dict)}


#: Repères posés par ``core/electrique/protections.py`` pour deux surcharges de
#: SITE que ``source_entree`` ne nomme pas : la prise de terre (posée seulement
#: sur ``inclure_prise_terre``) et le parafoudre DC (posé, liaison DC sous son
#: seuil, seulement sur ``zone_keraunique``).
_REPERE_PRISE_TERRE = "T1"
_REPERE_PARAFOUDRE_DC = "PDC1"


class SurchargesIrreproductibles(Exception):
    """Les surcharges de l'étude rangée ne se relisent pas sur elle."""


def _surcharges_de_site(design):
    """Les surcharges de SITE de l'étude rangée (POST ``conception-electrique``),
    relues sur ELLE — la seule source : régime et longueurs quand
    ``source_entree`` les dit « surcharge » (valeurs de ``parametres``), prise
    de terre et zone kéraunique par les organes qu'elles seules posent. Les
    grandeurs propres à l'onduleur ou au stockage d'une option (``phases``,
    ``batterie``, ``plafond_kwc_par_onduleur``, ``longueur_chaine_forcee``) ne
    passent jamais d'une option à l'autre. Lève ``SurchargesIrreproductibles``
    quand des températures ont été saisies : leurs valeurs ne sont pas rangées,
    l'autre option ne peut pas être conçue sur le même site."""
    from core.electrique.protections import LONGUEUR_DC_SANS_PARAFOUDRE_M

    if not isinstance(design, dict) or not design:
        return {}
    source = design.get("source_entree") if isinstance(design.get("source_entree"), dict) else {}
    parametres = design.get("parametres") if isinstance(design.get("parametres"), dict) else {}
    if source.get("temperatures") == E.SOURCE_SURCHARGE:
        raise SurchargesIrreproductibles("températures saisies non rangées sur l'étude")
    surcharges = {}
    if source.get("regime") == E.SOURCE_SURCHARGE and parametres.get("regime"):
        surcharges["regime"] = parametres["regime"]
    if source.get("longueurs") == E.SOURCE_SURCHARGE:
        surcharges.update({cle: parametres[cle] for cle in ("dc_m", "ac_m")
                           if parametres.get(cle) is not None})
    reperes = {str((p or {}).get("repere") or "") for p in (design.get("protections") or [])
               if isinstance(p, dict)}
    if _REPERE_PRISE_TERRE in reperes:
        surcharges["inclure_prise_terre"] = True
    if (_REPERE_PARAFOUDRE_DC in reperes
            and E._flottant(parametres.get("dc_m"), 0.0) <= LONGUEUR_DC_SANS_PARAFOUDRE_M):
        surcharges["zone_keraunique"] = True
    return surcharges


def _conception_de_l_option(devis, variante, figee=None, surcharges=None):
    """``{design, hash}`` de l'option ``variante``, par les fonctions de l'étude
    rangée (``E.construire_entree_et_source`` → ``concevoir`` →
    ``E.projeter_contrat``, empreinte ``E.empreinte_entree``) sous la variante
    imposée et avec les ``surcharges`` de site de l'étude rangée ; ``None``
    quand elle n'est pas dessinable (fiche incomplète, aucun module, bloquant).
    ``figee`` (celle déjà rangée) est rendue telle quelle quand les entrées
    n'ont pas bougé — ou, comme ACAL165 (sans surcharge), quand seule la source
    calepinage est arrivée depuis."""
    from core.electrique import concevoir

    with E._variante_imposee(variante):
        entree, source, lie = E.construire_entree_et_source(devis, surcharges or None)
        empreinte = E.empreinte_entree(devis, entree, source if lie else None)
        hash_fige = (figee or {}).get("hash")
        if hash_fige and (hash_fige == empreinte or (lie and not surcharges and E.empreinte_entree(
                devis, E.construire_entree_et_source(devis, None, avec_calepinage=False)[0]) == hash_fige)):
            return figee
        if E.motifs_fiche_incomplete(devis) or not entree.groupes:
            return None
        # Revue D-ACAL-158 (2) — les groupes viennent des pans du calepinage,
        # sans égard à l'option : une option qui ne pose pas ce nombre de
        # panneaux (8 « sans », 12 « avec ») n'est pas rangée — jamais un dessin
        # incertain chez le client (D-ACAL-142). Même test que les chaînes du
        # calepinage (``_chaines_du_calepinage``).
        from apps.ventes.domain.dimensionnement_devis import comptes_panneaux_valides
        if sum(g.nb_modules for g in entree.groupes) not in comptes_panneaux_valides(devis, variante):
            return None
        design = E._etude_dessinable(
            devis, E.projeter_contrat(entree, concevoir(entree), source_entree=source))
    return None if design is None else {"design": design, "hash": empreinte}


def _ranger_conceptions_figees(devis, entree):
    """Remplace l'entrée dans ``clauses_appliquees`` relu EN BASE (une
    correction re-gèle les clauses sur une autre instance) ; aucune écriture
    quand rien ne change. Rend ``True`` quand la liste a été réécrite."""
    from apps.ventes.domain.envoi import TYPE_CONCEPTIONS_OPTIONS_FIGEES
    base = getattr(devis, "clauses_appliquees", None)
    if getattr(devis, "pk", None):
        from apps.ventes.models import Devis
        base = (Devis.objects.filter(pk=devis.pk)
                .values_list("clauses_appliquees", flat=True).first())
    base = list(base or [])
    cible = [c for c in base if not (
        isinstance(c, dict) and c.get("type") == TYPE_CONCEPTIONS_OPTIONS_FIGEES)]
    cible += [entree] if entree is not None else []
    if cible == base:
        devis.clauses_appliquees = cible
        return False
    ancien, devis.clauses_appliquees = devis.clauses_appliquees, cible
    if getattr(devis, "pk", None):
        try:
            devis.save(update_fields=["clauses_appliquees"])
        except Exception:
            devis.clauses_appliquees = ancien      # l'instance ne garde pas une écriture défaite
            raise
    return True


def figer_conceptions_des_options(devis, *, garder=False):
    """D-ACAL-158 — range la conception de chaque option IMPOSÉE (celle que
    ``electrical_design`` ne porte pas) d'un devis à deux options ; rend
    ``{clé: {design, hash}}``. L'entrée est TOUJOURS écrite, mono-option
    comprise (``options: {}``) : elle marque « envoyé sous D-ACAL-158 », pour
    qu'un devis qui gagne sa seconde option par une correction après l'envoi
    reçoive aussi son second schéma (revue 3). Une option incalculable n'est pas rangée — la page
    client ne montre alors rien pour elle (D-ACAL-142) — et l'envoi ne
    s'arrête jamais : ne lève pas, journalise. ``garder`` (correction sur place)
    reprend les conceptions déjà rangées dont les entrées n'ont pas bougé ; à
    l'envoi, tout est recalculé (une révision, qui ne copie pas ``clauses_appliquees``, range celles de SON envoi).
    Aucun statut, aucune ligne, aucun prix (règle #4).

    Revue (4) — tout se passe dans un point de sauvegarde (un par option, un
    autour de l'ensemble) : une erreur de base ici est défaite sans empoisonner
    la transaction de l'envoi, qui continue."""
    try:
        with _point_de_sauvegarde(devis):
            return _figer_conceptions(devis, garder)
    except Exception:  # noqa: BLE001 — journalisé, l'envoi continue (D-ENF22-BLE001)
        logger.warning("D-ACAL-158 : conceptions des options non rangées pour %s",
                       getattr(devis, "reference", "?"), exc_info=True)
        return {}


def _point_de_sauvegarde(devis):
    """Un ``transaction.atomic()`` (point de sauvegarde dans l'envoi) pour un
    devis en base ; rien pour un devis non enregistré (aucune base touchée)."""
    if getattr(devis, "pk", None):
        from django.db import transaction
        return transaction.atomic()
    return contextlib.nullcontext()


def _figer_conceptions(devis, garder):
    """Le corps de :func:`figer_conceptions_des_options` (peut lever)."""
    from apps.ventes.domain.envoi import TYPE_CONCEPTIONS_OPTIONS_FIGEES
    reference = getattr(devis, "reference", "?")
    try:
        imposees = [v for v, imposee in E._variantes_du_schema(devis) if imposee]
    except Exception:  # noqa: BLE001 — journalisé, l'envoi continue (D-ENF22-BLE001)
        logger.warning("D-ACAL-158 : options du devis %s illisibles", reference, exc_info=True)
        imposees = []
    anciennes = _conceptions_figees(devis) if garder else {}
    options = {}
    a_concevoir = imposees
    try:
        surcharges = _surcharges_de_site(E.conception_electrique_stockee(devis))
    except SurchargesIrreproductibles as raison:
        logger.warning("D-ACAL-158 : aucune autre option rangée pour %s (%s)", reference, raison)
        a_concevoir, surcharges = [], {}
    for variante in a_concevoir:
        cle = E._cle_option(variante)
        try:
            with _point_de_sauvegarde(devis):
                conception = _conception_de_l_option(devis, variante, anciennes.get(cle), surcharges)
        except Exception:  # noqa: BLE001 — journalisé, l'option n'est pas rangée (D-ENF22-BLE001)
            logger.warning("D-ACAL-158 : conception « %s » impossible pour %s",
                           cle, reference, exc_info=True)
            conception = None
        if conception is None:
            logger.warning("D-ACAL-158 : conception électrique « %s » non rangée pour le "
                           "devis %s (option non dessinable)", cle, reference)
            continue
        options[cle] = conception
    _ranger_conceptions_figees(devis, {"type": TYPE_CONCEPTIONS_OPTIONS_FIGEES, "options": options})
    return options


def suivre_conceptions_figees(devis):
    """D-ACAL-158 — un devis envoyé SOUS cette règle (il porte l'entrée) dont
    l'étude rangée vient d'être refaite (lignes corrigées sur place, surcharges
    POSTées) : la conception de l'autre option suit, sur le même site. Un
    brouillon ou un devis envoyé avant n'en a aucune : rien. Ne lève jamais."""
    if _entree_conceptions_figees(devis) is not None:
        figer_conceptions_des_options(devis, garder=True)
