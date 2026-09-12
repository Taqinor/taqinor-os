"""NTMIG13 — kit Excel/CSV générique : pas de mapping prédéfini.

Contrairement aux kits Odoo/Sage (NTMIG8/12), la source ``csv_generique`` n'a
AUCUN format d'export connu à l'avance : ce kit déclare volontairement des
:class:`~apps.migration.kits.Kit` VIDES (aucun ``mapping``, aucune
``colonnes_montant``) pour chaque entité — leur seul rôle est de faire
résoudre proprement :func:`apps.migration.kits.cle_kit` pour cette source
(pas d'``ImportError``/``KeyError`` silencieux) tout en documentant
explicitement l'absence de mapping prédéfini.

Le VRAI mécanisme réutilisé (déjà livré, XPLT2) est
``dataimport.ImportMapping`` : l'analyse (``services.analyser_lot``) propose
déjà le mapping AUTOMATIQUE du moteur par en-tête ; l'intégrateur l'ajuste côté
écran puis le sauve via ``POST /api/django/imports/mapping/`` (``nom``,
``target``, ``mapping``) ; tout appel suivant à ``analyser_lot``/
``charger_lot`` avec ce même ``mapping_name`` réutilise le mapping sauvegardé
au lieu du mapping automatique — rejouable sur autant de fichiers identiques
que nécessaire, sans repasser par ce kit ni par aucun code nouveau.
"""
from . import Kit, cle_kit

#: Entités pour lesquelles un import générique (sans kit prédéfini) a du sens
#: — les mêmes cibles que le moteur ``dataimport`` sait déjà charger.
_ENTITES_GENERIQUES = (
    'clients', 'leads', 'products', 'fournisseurs', 'vehicules',
    'equipements', 'devis', 'factures',
)

#: Les DEUX sources génériques de ``ProjetMigration.Source`` (``excel`` et
#: ``csv_generique``) partagent le même traitement : aucun format d'export
#: connu, donc aucun mapping prédéfini pour l'une ni pour l'autre.
_SOURCES_GENERIQUES = ('excel', 'csv_generique')

KIT_REGISTRY = {
    cle_kit(source, entite): Kit()
    for source in _SOURCES_GENERIQUES
    for entite in _ENTITES_GENERIQUES
}
