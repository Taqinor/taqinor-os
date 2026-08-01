from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0016_feedbackproduit_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='idee',
            name='client_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID client (opaque, boîte à idées publique)'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='idees_clients_actif',
            field=models.BooleanField(
                default=False,
                verbose_name="Permettre aux clients d'envoyer des idées"),
        ),
    ]
