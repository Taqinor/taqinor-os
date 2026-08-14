# NTEXT6 — ajoute le choix FOR_EACH à ActionType (règle ET étape). Additif :
# AlterField ne touche que les `choices` déclarés en Python, la colonne reste
# un CharField(max_length=40) — aucune donnée existante affectée.

from django.db import migrations, models

CHOICES = [
    ('send_whatsapp', 'Envoyer un WhatsApp'),
    ('send_email', 'Envoyer un email'),
    ('send_sms', 'Envoyer un SMS'),
    ('create_activity', 'Créer une activité / tâche'),
    ('assign_record', 'Assigner un enregistrement'),
    ('set_field', 'Mettre à jour un champ'),
    ('create_sav_ticket', 'Créer un ticket SAV'),
    ('create_custom_record', 'Créer un enregistrement personnalisé'),
    ('for_each', "Pour chaque élément d'une liste"),
]


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0014_ntext26_alter_automationstep_action_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrule',
            name='action_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='automationstep',
            name='action_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
    ]
