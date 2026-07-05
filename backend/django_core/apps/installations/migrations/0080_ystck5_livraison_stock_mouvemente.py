from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0079_ystck4_retour_materiel'),
    ]

    operations = [
        migrations.AddField(
            model_name='livraison',
            name='stock_mouvemente',
            field=models.BooleanField(default=False),
        ),
    ]
