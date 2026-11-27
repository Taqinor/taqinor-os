"""Le MODULE (panneau) retenu par l'étude C&I — extrait tel quel de ``etude_ci.lire_catalogue_ci`` (D-ACAL-169).

Règle d'aujourd'hui, inchangée : parmi les panneaux du catalogue de la société, celui à puissance PUBLIÉE d'abord
(ADEV78 — sans Pmax, aucun panneau ne se compte), puis tarifé, puis la plus haute Pmax, puis le plus petit id.
D-ACAL-169 : le panneau par défaut de la société (``panneau_defaut``, passé seulement pour une étude SANS devis)
passe devant s'il passe l'acceptation de CE moteur — Pmax publiée ET prix de vente — ; sinon la règle d'aujourd'hui
et la phrase qui dit pourquoi, dans les alertes de l'étude. Même émetteur de journal qu'``etude_ci``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger('apps.ventes.domain.etude_ci')

#: Ce que l'étude C&I exige d'un panneau qu'elle compte : la clé de tri ``(Pmax publiée, tarifé, Pmax, -id)``.
RAISON_REFUS_CI = 'Pmax non publiée ou prix de vente absent'


def module_ci_retenu(objets, *, panneau_defaut=None, alertes=None):
    """``(module, module_spec)`` de l'étude C&I parmi ``objets`` (``{id: Produit}`` du catalogue de la société)."""
    from apps.stock.selectors import specs_for_produit
    from apps.ventes.conception.porte_calepinage import specs_module_du_calepinage as specs_module

    from .catalogue import classer_produit
    from .panneau_defaut import choisir_avec_defaut

    module = module_spec = None
    candidats = []
    for produit in objets.values():
        role = getattr(produit, 'role_devis', None) or classer_produit(produit.nom)
        if role != 'panneau':
            continue
        try:
            specs = specs_for_produit(produit) or {}
        except Exception:  # fiche illisible
            logger.warning("etude_ci.lire_catalogue_ci : erreur ignorée (mode dégradé)", exc_info=True)
            specs = {}
        pmax = _num(specs.get('pmax_wc'))
        prix = bool(produit.prix_vente and produit.prix_vente > 0)
        # ADEV78 — un module à puissance PUBLIÉE passe devant un module tarifé
        # sans Pmax (sans Pmax, aucun panneau ne se compte).
        candidats.append(((bool(pmax), prix, pmax or 0, -produit.id), produit, specs))
    choisi, motif = choisir_avec_defaut(panneau_defaut, candidats, lambda cle: cle[0] and cle[1],
                                        moteur="l'étude C&I", raison=RAISON_REFUS_CI)
    if motif and alertes is not None:
        from .etude_ci import _alerte
        alertes.append(_alerte('panneau_par_defaut', 'module', motif))
    if candidats:
        _cle, produit, specs = choisi or max(candidats, key=lambda c: c[0])
        module = {
            'produit': produit.id, 'designation': produit.nom,
            'pmax_wc': _num(specs.get('pmax_wc')),
            'prix_connu': bool(produit.prix_vente and produit.prix_vente > 0),
            'prix_vente_ht': produit.prix_vente,
            'tva_pct': getattr(produit, 'tva', None),
            # ADEV82 — le module porte aussi ses paliers (prix de la taille).
            'paliers_prix_vente': list(getattr(produit, 'paliers_prix_vente', None) or []),
            'longueur_mm': _num(specs.get('longueur_mm')),
            'largeur_mm': _num(specs.get('largeur_mm')),
            'poids_kg': _num(specs.get('poids_kg')),
        }
        # ADEV87 — la fiche électrique du module retenu (chaînes).
        module_spec = specs_module(specs, produit.nom)[0] if specs else None
    return module, module_spec


def _num(valeur):
    from .etude_ci import _num as num
    return num(valeur)
