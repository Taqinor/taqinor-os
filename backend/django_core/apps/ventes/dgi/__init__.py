"""N105 — Capacité DGI LOCALE (export UBL 2.1 conforme + validateur).

Package de groundwork pour la conformité DGI marocaine, atteignable UNIQUEMENT
à la demande / par programme (commande de gestion ou endpoint gardé), et armé
par le seul interrupteur maître ``CompanyProfile.dgi_export_actif`` (défaut
OFF). Tant que l'interrupteur est OFF, RIEN de cette capacité n'est exposé et
le comportement de l'application reste byte-identique.

Surface publique :
  * ``build_ubl_xml(facture, profile=None) -> str`` — XML UBL 2.1 conforme
    portant l'ICE du destinataire (B2B) et de l'émetteur, les identifiants
    société, les lignes avec TVA par ligne, et la ventilation HT/TVA/TTC.
  * ``validate_dgi_conformity(facture, profile=None) -> list[str]`` — liste de
    messages de problème en français (vide = conforme).
  * ``is_dgi_enabled(company) -> bool`` — état de l'interrupteur maître.

HORS PÉRIMÈTRE (gatés ailleurs) : transmission au portail Simpl-TVA, signature
électronique certifiée. Aucun appel externe, aucun sceau d'archivage, aucune
piste d'audit, aucun champ de statut sur la facture.
"""
from .dgi_export import build_ubl_xml
from .dgi_validator import validate_dgi_conformity
from .toggle import is_dgi_enabled

__all__ = [
    'build_ubl_xml',
    'validate_dgi_conformity',
    'is_dgi_enabled',
]
