from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0064_xstk22_livraison_suivi_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='priorite',
            field=models.CharField(
                choices=[
                    ('urgente', 'Urgente'),
                    ('haute', 'Haute'),
                    ('normale', 'Normale'),
                ],
                default='normale', max_length=10),
        ),
    ]
