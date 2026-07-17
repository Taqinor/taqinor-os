"""NTEXT13 — seed d'un package d'exemple au catalogue global.

Idempotent (get_or_create par code). Réversible (no-op au
retour — supprimer le package d'exemple n'est pas destructif pour un tenant
puisque le catalogue ne fait que documenter un manifest, jamais matérialisé
tant qu'aucune installation (NTEXT14) n'existe)."""
from django.db import migrations

MANIFEST = {
    'custom_object_defs': [
        {
            'code': 'intervention_sav',
            'libelle': 'Intervention SAV avancée',
            'icone': '🛠️',
            'champs': [
                {'code': 'gravite', 'libelle': 'Gravité', 'type': 'choice',
                 'options': ['faible', 'moyenne', 'critique']},
                {'code': 'temps_resolution_h',
                 'libelle': 'Temps de résolution (h)', 'type': 'number'},
            ],
        },
    ],
    'automation_rules': [
        {
            'nom': 'Alerte intervention critique',
            'description': 'Notifie le responsable SAV à la création '
                            "d'une intervention de gravité critique.",
        },
    ],
    'rapport_definitions': [
        {'titre': 'SAV — temps de résolution moyen',
         'dataset': 'sav.ticket'},
    ],
    'branded_templates': [],
}


def seed(apps, schema_editor):
    ExtensionPackage = apps.get_model('extensions', 'ExtensionPackage')
    ExtensionPackage.objects.get_or_create(
        code='sav_avance',
        defaults={
            'nom': 'Suivi SAV avancé',
            'version': '1.0.0',
            'categorie': 'SAV',
            'description': "Objets, champs et automatisations pour un suivi "
                           "SAV enrichi (gravité, temps de résolution, "
                           "rapport dédié).",
            'manifest': MANIFEST,
        })


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0001_initial'),
    ]

    operations = [migrations.RunPython(seed, noop)]
