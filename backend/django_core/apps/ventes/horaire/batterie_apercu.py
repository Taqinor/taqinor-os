"""RHOR9 — la batterie de l'aperçu horaire lue sur les FICHES quand aucun devis
n'est encore enregistré.

Rendu réel (RGEN, lead 2141) : pendant la création d'un devis, l'écran envoie
la capacité NOMINALE lue sur le nom de ses lignes (« Dyness 5 kWh » → 5) et
l'aperçu tournait à 5 kWh × rendement de référence 0,90, pendant que le devis
automatique tourne à la capacité UTILE de la fiche × le rendement publié
(0,98) — économie « avec » 30 571 à l'écran contre 30 585 au PDF.

L'écran envoie désormais ses lignes « avec » batterie
(``batteries: [{produit, quantite}]``, contrat
``contract_samples/etude_horaire.json`` → ``notes.corps_batteries``) ; ce
module en tire capacité utile, puissances et rendement avec les MÊMES
lecteurs que le bloc d'un devis enregistré (``horaire.batterie_lignes``,
``dimensionnement.capacite_utile_batterie``) — jamais une seconde règle.
Produits lus par le sélecteur de ``stock``, bornés à la société de la
requête : un identifiant d'une autre société est ignoré.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

logger = logging.getLogger("apps.ventes.etude_horaire")


def _lignes_du_corps(batteries, company):
    """Lignes en mémoire (``designation``, ``produit``, ``quantite``) des
    batteries envoyées par l'écran ; produits hors société ignorés."""
    from apps.stock.selectors import get_produit_scoped
    lignes = []
    for entree in batteries or ():
        if not isinstance(entree, dict):
            continue
        try:
            pk = int(entree.get('produit'))
            quantite = float(entree.get('quantite') or 0)
        except (TypeError, ValueError):
            continue
        if quantite <= 0:
            continue
        produit = get_produit_scoped(company, pk)
        if produit is None:
            continue
        lignes.append(SimpleNamespace(
            designation=getattr(produit, 'nom', '') or '', produit=produit,
            quantite=quantite, variante=''))
    return lignes


def batterie_des_produits(batteries, company):
    """Arguments batterie de :func:`etude_horaire.calculer_etude_horaire`
    pour les lignes « avec » envoyées par l'écran, ou ``None`` (rien de
    lisible : l'appelant garde la capacité du corps). Ne lève jamais."""
    try:
        from apps.ventes.dimensionnement import capacite_utile_batterie
        from apps.ventes.horaire.batterie_lignes import (
            puissances_batterie_des_lignes, rendement_batterie_des_lignes)
        from apps.ventes.services import classer_produit
        lignes = [ligne for ligne in _lignes_du_corps(batteries, company)
                  if classer_produit(ligne.designation) == 'batterie']
        capacite = sum(
            float(capacite_utile_batterie(ligne.produit, ligne.designation)
                  or 0) * ligne.quantite
            for ligne in lignes)
        if capacite <= 0:
            return None
        puissances = puissances_batterie_des_lignes(lignes)
        rendement = rendement_batterie_des_lignes(lignes)
        return {
            'batterie_kwh_utile': capacite,
            'batterie_puissance_decharge_kw': puissances['packs_decharge_kw'],
            'batterie_puissance_decharge_onduleur_kw':
                puissances['ond_decharge_kw'],
            'batterie_puissance_charge_kw': puissances['charge_kw'],
            'batterie_rendement': rendement['rendement'],
            'batterie_rendement_source': rendement['source'],
        }
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais : corps seul (D-ENF22-BLE001)
        logger.warning('batteries de l\'aperçu illisibles', exc_info=True)
        return None
