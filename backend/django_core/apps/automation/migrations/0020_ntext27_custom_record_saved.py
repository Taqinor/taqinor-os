# NTEXT27 — ajoute le choix CUSTOM_RECORD_SAVED à TriggerType. Additif :
# AlterField ne touche que les `choices` déclarés en Python, la colonne
# reste un CharField(max_length=40) — aucune donnée existante affectée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0019_ntext8_server_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrule',
            name='trigger_type',
            field=models.CharField(choices=[
                ('lead_stage_change', "Changement d'étape d'un lead"),
                ('devis_accepted', 'Devis accepté'),
                ('chantier_status', 'Chantier atteint un statut'),
                ('facture_overdue', 'Facture en retard'),
                ('warranty_expiring', 'Garantie proche expiration'),
                ('maintenance_due', 'Visite de maintenance due'),
                ('stock_below_threshold', 'Stock sous le seuil'),
                ('date_echeance_champ', 'Échéance de champ (± N jours)'),
                ('webhook_inbound', 'Webhook entrant'),
                ('projet_status_change', 'Changement de statut de projet'),
                ('projet_phase_change', 'Changement de phase de projet'),
                ('record_state_change',
                 "Changement d'état d'un enregistrement"),
                ('custom_record_saved',
                 "Enregistrement d'objet personnalisé créé/modifié"),
            ], max_length=40),
        ),
    ]
