"""Barème transport par ville — application à la composition d'un devis.

Le barème lui-même (ancres fondateur du 07/09/2026, formule, résolution des
villes) vit dans ``apps.parametres.transport_bareme`` (app fondation). Ici,
uniquement son APPLICATION, à UN seul endroit : l'étape ``composer`` du
pipeline (``domain.pipeline.composer``), AVANT l'écriture des lignes — donc
avant le cliché de marge et le gel du prix/kWc, et pour TOUTES les origines
(devis automatique, calepinage 3D, dry-run de l'écran). QJR604 : les deux
repricers d'après coup (devis sauvé, lignes sérialisées du dry-run) ont été
supprimés.

Ville inconnue (ou vide) ⇒ AUCUNE écriture : la ligne garde le prix
catalogue — jamais un prix deviné (règle « zéro chiffre inventé »).

La ligne Transport est reconnue par son RÔLE de composition (``transport``) ;
le mot-clé de la désignation n'est qu'un repli historique, pour une
composition qui ne porterait pas ses rôles.
"""
from __future__ import annotations

from decimal import Decimal

from apps.parametres.transport_bareme import prix_transport_ht
from core.money import quantize_mad

#: Le rôle de composition de la ligne Transport (``ROLES_AUTO_COMPOSITION``).
ROLE_TRANSPORT = 'transport'


def ville_du_lead(lead):
    """La ville de calcul du barème, résolue UNE fois côté serveur."""
    # VREF — la ville ERP de rattachement (douar hors gazetier) prime : le
    # barème est défini sur les villes du gazetier, jamais sur un nom libre.
    for champ in ('ville_reference', 'ville'):
        valeur = getattr(lead, champ, '')
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()
    return ''


def _est_transport(role, designation):
    if role:
        return role == ROLE_TRANSPORT
    from .catalogue import _sans_accents
    return ROLE_TRANSPORT in _sans_accents(designation)


def appliquer_bareme_transport(lignes, ville):
    """Rend la composition dont la ligne Transport porte le prix HT du barème
    de ``ville``. Ville inconnue ⇒ la composition est rendue TELLE QUELLE
    (même objet). Les métadonnées de ``CompositionLignes`` sont reportées.
    """
    if not lignes:
        return lignes
    prix = prix_transport_ht(ville) if ville else None
    if prix is None:
        return lignes
    prix = quantize_mad(Decimal(prix))
    roles = list(getattr(lignes, 'roles', ()) or ())
    nouvelles = []
    for index, ligne in enumerate(lignes):
        role = roles[index] if index < len(roles) else None
        if _est_transport(role, getattr(ligne, 'designation', '')):
            ligne = ligne._replace(prix_unitaire=prix)
        nouvelles.append(ligne)
    rendu = type(lignes)(nouvelles)
    meta = getattr(lignes, '__dict__', None)
    if meta:
        rendu.__dict__.update(meta)
    return rendu
