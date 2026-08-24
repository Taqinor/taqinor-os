# -*- coding: utf-8 -*-
"""PV38 — la NOTE DE CALCUL : une ligne GÉNÉRÉE par nombre calculé.

Même règle que ``core/calepinage/electrique.py::note_de_calcul`` : **aucun
nombre n'est écrit en dur dans une phrase**. Chaque ligne est un gabarit dont
tous les nombres viennent du calcul, si bien qu'une note ne peut pas dire autre
chose que ce que le moteur a calculé — le mode de défaillance classique d'une
note rédigée à la main, où l'on corrige le calcul sans corriger la phrase.

Un test le VÉRIFIE mécaniquement : il analyse l'AST de ce fichier et échoue si
un littéral de chaîne contient le moindre chiffre.

La note est destinée au dossier technique : elle est en FRANÇAIS, elle nomme les
grandeurs et leurs unités, et elle finit par les refus et les alertes — un
lecteur qui s'arrête à la première page doit quand même voir ce qui coince.
"""

from core.electrique.types import fr, fr_a, fr_v

__all__ = ["note_de_calcul"]


def _plafond(borne):
    """« … modules au plus », ou l'aveu que la fiche ne permet pas de le dire.

    Une borne à ``None`` n'est pas une borne à zéro : c'est une tension absente
    des fiches. La note l'ÉCRIT plutôt que de laisser croire à une limite
    calculée (règle fondateur « zéro chiffre inventé »).
    """
    if borne is None:
        return "borne NON VÉRIFIABLE, tension absente de la fiche"
    return "%d modules au plus" % borne


def _plancher(borne):
    """« … modules au moins », même règle que ``_plafond``."""
    if borne is None:
        return "borne NON VÉRIFIABLE, tension absente de la fiche"
    return "%d modules au moins" % borne


def note_de_calcul(entree, resultat_chaines=None, evaluation=None,
                   resultat_protections=None, resultat_cables=None,
                   resultat_nomenclature=None):
    """Rend la note ligne à ligne (tuple de chaînes), du champ au bordereau."""
    lignes = []
    module = entree.module
    onduleur = entree.onduleur

    lignes.append(
        "%d modules × %s Wc = %s kWc crête installés"
        % (entree.nb_modules, fr(module.pmax_wc, 0),
           fr(entree.puissance_kwc, 2)))

    fenetre = resultat_chaines.fenetre if resultat_chaines else None
    if fenetre is not None:
        lignes.append(
            "fenêtre de tension entre %s °C et %s °C : %s"
            % (fr(fenetre.temp_froid_c, 0), fr(fenetre.temp_chaud_c, 0),
               fenetre.texte))
        lignes.append(
            "borne haute — Voc à froid %s par module, tension maximale "
            "onduleur %s : %s"
            % (fr_v(fenetre.voc_froid_unitaire_v, 2),
               fr_v(onduleur.v_max_abs), _plafond(fenetre.max_par_voc)))
        lignes.append(
            "borne haute — Vmp à froid %s par module, haut de plage MPPT %s : "
            "%s"
            % (fr_v(fenetre.vmp_froid_unitaire_v, 2),
               fr_v(onduleur.mppt_v_max), _plafond(fenetre.max_par_mppt)))
        lignes.append(
            "borne basse — Vmp à chaud %s par module, bas de plage MPPT %s : "
            "%s"
            % (fr_v(fenetre.vmp_chaud_unitaire_v, 2),
               fr_v(onduleur.mppt_v_min), _plancher(fenetre.min_par_mppt)))
        lignes.append(
            "borne basse — tension de démarrage onduleur %s : %s"
            % (fr_v(onduleur.tension_demarrage_v),
               _plancher(fenetre.min_par_demarrage)))

    if resultat_chaines is not None:
        if resultat_chaines.longueur_forcee is not None:
            if resultat_chaines.longueur_forcee_acceptee:
                lignes.append(
                    "longueur de chaîne imposée de %d modules : ACCEPTÉE, elle "
                    "tient dans la plage admissible"
                    % resultat_chaines.longueur_forcee)
            else:
                lignes.append(
                    "longueur de chaîne imposée de %d modules : REFUSÉE, la "
                    "longueur physique est retenue à la place"
                    % resultat_chaines.longueur_forcee)

        for repartition in resultat_chaines.repartitions:
            groupe = _groupe(entree, repartition.pan)
            lignes.append(
                "pan « %s » (azimut %s°, inclinaison %s°) : %d modules → %d "
                "chaîne(s) de %d modules sur l'entrée MPPT %s"
                % (repartition.pan,
                   fr(groupe.azimut_deg if groupe else 0.0, 0),
                   fr(groupe.inclinaison_deg if groupe else 0.0, 0),
                   repartition.nb_modules, repartition.nb_chaines,
                   repartition.longueur_chaine,
                   ", ".join(str(m) for m in repartition.mppt)))
            if repartition.reste:
                lignes.append(
                    "pan « %s » : %d module(s) en réserve d'appoint, hors "
                    "chaîne" % (repartition.pan, repartition.reste))

        if resultat_chaines.chaines:
            plus_longue = max(resultat_chaines.chaines,
                              key=lambda c: c.nb_modules)
            plus_courte = min(resultat_chaines.chaines,
                              key=lambda c: c.nb_modules)
            lignes.append(
                "%d chaîne(s) au total, %s kWc raccordés en chaîne"
                % (resultat_chaines.nb_chaines,
                   fr(resultat_chaines.puissance_kwc, 2)))
            lignes.append(
                "Voc à froid de la plus longue chaîne %s, sous la tension "
                "maximale onduleur %s"
                % (fr_v(plus_longue.voc_froid_v), fr_v(onduleur.v_max_abs)))
            lignes.append(
                "Vmp à chaud de la plus courte chaîne %s, au-dessus du bas de "
                "plage MPPT %s"
                % (fr_v(plus_courte.vmp_chaud_v), fr_v(onduleur.mppt_v_min)))
            lignes.append(
                "Isc module %s, Imp module %s — courant d'entrée MPPT "
                "admissible %s"
                % (fr_a(module.isc_a, 2), fr_a(module.imp_a, 2),
                   fr_a(onduleur.i_max_mppt_a)))

    if evaluation is not None and evaluation.nombre:
        lignes.append(
            "%d onduleur(s) de %s kW = %s kW AC"
            % (evaluation.nombre, fr(evaluation.ac_kw_unitaire, 1),
               fr(evaluation.puissance_ac_kw, 1)))
        if evaluation.plafond_kwc_par_onduleur:
            lignes.append(
                "%s kWc par onduleur, plafond de dossier %s kWc"
                % (fr(evaluation.dc_par_onduleur_kwc, 2),
                   fr(evaluation.plafond_kwc_par_onduleur, 1)))
        for ratio in (evaluation.ratio_dc_ac, evaluation.ratio_ac_dc):
            if ratio is not None:
                lignes.append("ratio %s = %s — %s"
                              % (ratio.nom, ratio.texte,
                                 ratio.fourchette_texte))

    for protection in (resultat_protections.protections
                       if resultat_protections else ()):
        lignes.append(
            "protection %s — %s : %s, quantité %d (%s)"
            % (protection.repere, protection.designation, protection.calibre,
               protection.quantite, protection.regle_source))

    for cable in (resultat_cables.cables if resultat_cables else ()):
        lignes.append(
            "câble %s — %s : %s mm² sur %s m, Ib %s, In %s, Iz %s, chute de "
            "tension %s %% pour une cible de %s %% (critère dimensionnant : %s)"
            % (cable.repere, cable.designation, fr(cable.section_mm2, 1),
               fr(cable.longueur_m, 1), fr_a(cable.ib_a),
               fr_a(cable.in_a) if cable.in_a is not None else "sans objet",
               fr_a(cable.iz_a), fr(cable.chute_tension_pct, 2),
               fr(cable.chute_cible_pct, 1), cable.critere_dimensionnant))

    for justification in (resultat_protections.justifications
                          if resultat_protections is not None else ()):
        lignes.append("RÈGLE EXAMINÉE, SANS OBJET — %s" % justification)

    if resultat_nomenclature is not None and resultat_nomenclature.lignes:
        lignes.append("bordereau : %d ligne(s) de fournitures et quantités"
                      % len(resultat_nomenclature.lignes))

    for bloquant in _verdicts(resultat_chaines, evaluation,
                              resultat_protections, resultat_cables,
                              bloquants=True):
        lignes.append("REFUSÉ — %s" % bloquant)
    for alerte in _verdicts(resultat_chaines, evaluation, resultat_protections,
                            resultat_cables, bloquants=False):
        lignes.append("ALERTE — %s" % alerte)

    return tuple(lignes)


def _groupe(entree, label):
    for groupe in entree.groupes:
        if groupe.label == label:
            return groupe
    return None


def _verdicts(*resultats, **options):
    """Bloquants (ou alertes) de tous les résultats, dans l'ordre, sans doublon."""
    attribut = "bloquants" if options.get("bloquants") else "alertes"
    vus = set()
    ordonnes = []
    for resultat in resultats:
        for message in getattr(resultat, attribut, ()) or ():
            if message not in vus:
                vus.add(message)
                ordonnes.append(message)
    return tuple(ordonnes)
