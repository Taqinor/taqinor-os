# NTEXT26 — ajoute le choix CREATE_CUSTOM_RECORD à ActionType (additif,
# aucune donnée existante affectée : AlterField ne touche que les `choices`
# déclarés en Python, la colonne reste un CharField(max_length=40)).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Renumérotée 0012 -> 0013 à l'intégration : une lane soeur (NTEXT4)
        # avait déjà pris 0012 sur cette app.
        ('automation', '0012_ntext4_automationstep'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrule',
            name='action_type',
            field=models.CharField(choices=[('send_whatsapp', 'Envoyer un WhatsApp'), ('send_email', 'Envoyer un email'), ('send_sms', 'Envoyer un SMS'), ('create_activity', 'Créer une activité / tâche'), ('assign_record', 'Assigner un enregistrement'), ('set_field', 'Mettre à jour un champ'), ('create_sav_ticket', 'Créer un ticket SAV'), ('create_custom_record', 'Créer un enregistrement personnalisé')], max_length=40),
        ),
    ]
