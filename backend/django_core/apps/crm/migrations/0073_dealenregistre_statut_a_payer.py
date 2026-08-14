# NTCRM22 — Ajoute le statut À_PAYER à DealEnregistre.statut (metadata de
# choix uniquement — CharField déjà max_length=10, aucune migration de
# données nécessaire).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0072_apporteur_token_acces'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dealenregistre',
            name='statut',
            field=models.CharField(choices=[
                ('en_attente', 'En attente'), ('approuve', 'Approuvé'),
                ('rejete', 'Rejeté'), ('expire', 'Expiré'),
                ('a_payer', 'À payer')], default='en_attente', max_length=10),
        ),
    ]
