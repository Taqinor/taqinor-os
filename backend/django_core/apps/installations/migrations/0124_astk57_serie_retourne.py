# ASTK57 — statut « retourné » d'une série entrepôt (réception annulée).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0123_ciq634_garanties_pose'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serieentrepot',
            name='statut',
            field=models.CharField(choices=[('en_stock', 'En stock'), ('reserve', 'Réservé'), ('sorti', 'Sorti'), ('retourne', 'Retourné (réception annulée)')], default='en_stock', max_length=20),
        ),
    ]
