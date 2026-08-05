# NTADM7 — seed des 3 paliers de licence TAQINOR (starter/pro/enterprise) au
# catalogue global. Idempotent (get_or_create par code). Réversible (no-op au
# retour — supprimer les paliers d'exemple n'est jamais destructif pour un
# tenant : tant qu'aucune société n'a de plan assigné, has_feature() renvoie
# toujours True — voir apps.parametres.feature_flags).
from django.db import migrations

# Représentatif, pas exhaustif : le founder complète/ajuste la liste de
# modules de chaque palier via l'admin Django (apps.adminops.admin) — cette
# seed donne un point de départ raisonnable, jamais une source figée.
PLANS = [
    {
        'code': 'starter',
        'nom': 'Starter',
        'modules_inclus': ['crm', 'ventes', 'stock'],
    },
    {
        'code': 'pro',
        'nom': 'Pro',
        'modules_inclus': [
            'crm', 'ventes', 'stock', 'installations', 'sav', 'compta',
            'reporting', 'contrats',
        ],
    },
    {
        'code': 'enterprise',
        'nom': 'Enterprise',
        'modules_inclus': [
            'crm', 'ventes', 'stock', 'installations', 'sav', 'compta',
            'reporting', 'contrats', 'rh', 'paie', 'achats', 'qhse',
            'gestion_projet', 'flotte', 'ged', 'kb', 'litiges', 'adminops',
            'publicapi', 'parametres',
        ],
    },
]


def seed(apps, schema_editor):
    PlanLicence = apps.get_model('adminops', 'PlanLicence')
    for plan in PLANS:
        PlanLicence.objects.get_or_create(
            code=plan['code'],
            defaults={
                'nom': plan['nom'],
                'modules_inclus': plan['modules_inclus'],
            })


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('adminops', '0002_ntadm7_planlicence'),
    ]

    operations = [migrations.RunPython(seed, noop)]
