"""Parseurs de formats de relevés bancaires normalisés (NTTRE1-3).

Chaque parseur transforme le contenu brut d'un fichier de relevé bancaire en une
liste de dictionnaires ``{date_operation, libelle, montant, reference}`` — le
même contrat que ``services.ajouter_ligne_releve`` consomme ligne à ligne pour
matérialiser des ``LigneReleve`` existantes (aucun nouveau modèle de ligne).

Formats couverts :
  * CFONB120 (``cfonb.parser_cfonb120``) — lignes fixes 120 caractères (NTTRE1).
  * MT940 SWIFT (``mt940.parser_mt940``) — tags ``:61:``/``:86:`` (NTTRE2).
  * camt.053 ISO 20022 (``camt053.parser_camt053``) — ``<Ntry>`` XML (NTTRE3).

``montant`` est SIGNÉ tel que côté entreprise : positif = crédit/encaissement,
négatif = débit/décaissement (aligné sur la convention de ``LigneReleve``).
"""

from .camt053 import parser_camt053
from .cfonb import parser_cfonb120
from .mt940 import parser_mt940

__all__ = ['parser_cfonb120', 'parser_mt940', 'parser_camt053']
