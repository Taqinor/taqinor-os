"""Barème transport par ville — application aux lignes de devis.

Le barème lui-même (ancres fondateur du 07/09/2026, formule, résolution des
villes) vit dans ``apps.parametres.transport_bareme`` (app fondation). Ici,
uniquement son APPLICATION aux deux formes de lignes de ce domaine :

* les lignes SÉRIALISÉES du dry-run ``POST /ventes/devis/composition/``,
  avant que l'écran ne les affiche ;
* les ``LigneDevis`` d'un devis fraîchement créé (devis automatique /
  tunnel), AVANT le rafraîchissement des études (le prix du transport entre
  dans le total TTC, donc dans le prix/kWc et le payback).

Ville inconnue (ou vide) ⇒ AUCUNE écriture : la ligne garde le prix
catalogue — jamais un prix deviné (règle « zéro chiffre inventé »).

La ligne Transport est reconnue par sa désignation (mot « transport »,
accents ignorés) — le même mot-clé que la classification de l'écran
(``solar.js``) et du moteur PDF (``quote_engine/builder.py``).
"""
from __future__ import annotations

import unicodedata
from decimal import Decimal

from apps.parametres.transport_bareme import prix_transport_ht


def _sans_accents(texte):
    txt = unicodedata.normalize('NFKD', str(texte or '').lower())
    return ''.join(c for c in txt if not unicodedata.combining(c))


def est_ligne_transport(designation):
    return 'transport' in _sans_accents(designation)


def repricer_transport_lignes_dict(lignes, ville):
    """Reprice la ligne Transport dans les lignes SÉRIALISÉES du dry-run
    (``POST /ventes/devis/composition/`` — dicts ``role``/``prix_unitaire_ht``/
    ``prix_unitaire_ttc``/``taux_tva``, contrat ``devis_composition.json``).
    Rend le nombre de lignes modifiées ; ville inconnue ⇒ 0, rien n'est écrit.
    """
    if not isinstance(lignes, list):
        return 0
    prix = prix_transport_ht(ville)
    if prix is None:
        return 0
    modifiees = 0
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        if (ligne.get('role') != 'transport'
                and not est_ligne_transport(ligne.get('designation', ''))):
            continue
        try:
            taux = Decimal(str(ligne.get('taux_tva') or '20'))
        except ArithmeticError:
            taux = Decimal('20')
        ht = Decimal(prix)
        ligne['prix_unitaire_ht'] = str(ht.quantize(Decimal('0.01')))
        ligne['prix_unitaire_ttc'] = str(
            (ht * (1 + taux / 100)).quantize(Decimal('0.01')))
        modifiees += 1
    return modifiees


def repricer_transport_devis(devis):
    """Reprice la (les) ligne(s) Transport d'un devis SAUVÉ au barème de la
    ville de son lead. Rend le nombre de lignes modifiées (0 si ville
    inconnue, pas de lead, ou pas de ligne Transport)."""
    lead = getattr(devis, 'lead', None)
    ville = getattr(lead, 'ville', '') or ''
    prix = prix_transport_ht(ville)
    if prix is None:
        return 0
    prix = Decimal(prix)
    modifiees = 0
    for ligne in devis.lignes.all():
        if not est_ligne_transport(ligne.designation):
            continue
        if ligne.prix_unitaire == prix:
            continue
        ligne.prix_unitaire = prix
        ligne.save(update_fields=['prix_unitaire'])
        modifiees += 1
    return modifiees
