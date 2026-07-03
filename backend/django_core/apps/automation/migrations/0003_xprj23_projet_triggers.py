# XPRJ23 — nouveaux déclencheurs « projet_status_change » et
# « projet_phase_change » (étapes du projet, gestion_projet). Additif : seul
# le jeu de choices de la colonne trigger_type change (aucune donnée touchée).
from django.db import migrations, models


TRIGGER_CHOICES = [
    ('lead_stage_change', "Changement d'étape d'un lead"),
    ('devis_accepted', 'Devis accepté'),
    ('chantier_status', 'Chantier atteint un statut'),
    ('facture_overdue', 'Facture en retard'),
    ('warranty_expiring', 'Garantie proche expiration'),
    ('maintenance_due', 'Visite de maintenance due'),
    ('stock_below_threshold', 'Stock sous le seuil'),
    ('projet_status_change', 'Changement de statut de projet'),
    ('projet_phase_change', 'Changement de phase de projet'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0002_modelemessage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrule',
            name='trigger_type',
            field=models.CharField(choices=TRIGGER_CHOICES, max_length=40),
        ),
    ]
