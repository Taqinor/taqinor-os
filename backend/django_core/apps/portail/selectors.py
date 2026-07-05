"""Selectors du module Portail client (``apps.portail``).

Point d'entrée des LECTURES cross-app du domaine portail (CLAUDE.md : les autres
apps lisent ``portail`` via ``apps.portail.selectors`` ou par string-FK, jamais
via ``apps.portail.models``).

À la sortie de compta (ODX12), les lecteurs internes de ``ComptePortailClient``
(les vues publiques tokenisées ``portail_mon_releve`` / ``portail_contester_
facture`` de compta, et le sélecteur lecture de ``apps.contrats``) continuent de
passer par le shim compta. Ce module est le point d'accès stable pour toute
future lecture fine — jamais un import direct de ``apps.portail.models`` depuis
l'extérieur.
"""
