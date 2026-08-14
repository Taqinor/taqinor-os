"""ARC28 — Manifeste plateforme d'``apps.scm`` (planification supply chain).

Déclare UNE fois ce que le module expose aux surfaces transverses, collecté
GÉNÉRIQUEMENT par ``core.platform`` (aucun import de ``apps.scm`` depuis
``core``). Seule la surface ``import_specs`` est renseignée pour l'instant
(NTSCM40 — import CSV/XLSX des événements de demande, cible
``scm_evenement_demande``, mode ``creer`` uniquement). Le MAPPING colonne →
champ reste dans ``apps.dataimport.services.FIELD_MAPS`` (local à
``dataimport``, voir sa docstring ARC32) ; ce manifeste ne fait que déclarer
l'EXISTENCE de la cible.

NOTE NTSCM44 — ``CyclePlanificationSOP``/``PolitiqueStock`` portent un fil
d'activité (chatter générique ``records.Activity`` via ``log_field_change``/
``chatter_qs``, actions ``historique`` DÉDIÉES sur leurs viewsets — pas le
mixin générique ``ChatterViewSetMixin``) : cela ne nécessite AUCUNE entrée
``record_targets`` ici (ce registre sert le mixin générique + le croisement
``core.platform_coverage`` avec ``searchable_models``, hors périmètre de
cette lane — l'ajouter sans ``searchable_models`` créerait une incohérence
NEUVE que le test de dérive ARC41 refuserait)."""

PLATFORM = {
    'import_specs': ['scm_evenement_demande'],
}
