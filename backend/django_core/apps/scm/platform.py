"""ARC28 — Manifeste plateforme d'``apps.scm`` (planification supply chain).

Déclare UNE fois ce que le module expose aux surfaces transverses, collecté
GÉNÉRIQUEMENT par ``core.platform`` (aucun import de ``apps.scm`` depuis
``core``). Seule la surface ``import_specs`` est renseignée pour l'instant
(NTSCM40 — import CSV/XLSX des événements de demande, cible
``scm_evenement_demande``, mode ``creer`` uniquement). Le MAPPING colonne →
champ reste dans ``apps.dataimport.services.FIELD_MAPS`` (local à
``dataimport``, voir sa docstring ARC32) ; ce manifeste ne fait que déclarer
l'EXISTENCE de la cible."""

PLATFORM = {
    'import_specs': ['scm_evenement_demande'],
}
