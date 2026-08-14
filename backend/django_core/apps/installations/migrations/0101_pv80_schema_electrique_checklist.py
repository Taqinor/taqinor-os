# Generated for PV80 — « le chantier hérite du schéma ».
#
# Ajoute l'étape système « Schéma électrique validé » (cle
# `schema_electrique_valide`) au template « Défaut » (protégé) de CHAQUE
# société déjà amorcée (N74) — même patron que 0006
# (`attach_orphans_to_default_template`) : purement additif, idempotent,
# jamais destructif. Les sociétés dont le template « Défaut » n'existe pas
# encore n'ont rien à migrer ici : `ensure_default_template` (services.py,
# `DEFAULT_CHECKLIST_ETAPES` mis à jour PV80) l'amorcera avec l'étape déjà en
# place au premier usage — les deux chemins convergent vers le MÊME jeu
# d'étapes, l'étape ajoutée EN FIN de liste dans les deux cas (aucun `ordre`
# existant n'est renuméroté).

from django.db import migrations


NOUVELLE_ETAPE_CLE = 'schema_electrique_valide'
NOUVELLE_ETAPE_LIBELLE = 'Schéma électrique validé'


def seed_schema_electrique_step(apps, schema_editor):
    ChecklistTemplate = apps.get_model('installations', 'ChecklistTemplate')
    ChecklistEtapeModele = apps.get_model(
        'installations', 'ChecklistEtapeModele')
    for template in ChecklistTemplate.objects.filter(protege=True):
        if ChecklistEtapeModele.objects.filter(
                template=template, cle=NOUVELLE_ETAPE_CLE).exists():
            continue
        max_ordre = ChecklistEtapeModele.objects.filter(
            template=template).order_by('-ordre').values_list(
            'ordre', flat=True).first()
        ChecklistEtapeModele.objects.create(
            company_id=template.company_id, template=template,
            cle=NOUVELLE_ETAPE_CLE, libelle=NOUVELLE_ETAPE_LIBELLE,
            ordre=(max_ordre + 1) if max_ordre is not None else 0,
            capture_serie=False, photo_obligatoire=False,
            actif=True, protege=True)


def noop_reverse(apps, schema_editor):
    # Réversible sans perte : cette migration n'AJOUTE que des lignes ; les
    # retirer romprait un chantier qui aurait déjà coché l'étape. On ne
    # supprime rien à la descente (comme 0006).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0100_photochecklistmeta_tenantmodel_timestamps'),
    ]

    operations = [
        migrations.RunPython(seed_schema_electrique_step, noop_reverse),
    ]
