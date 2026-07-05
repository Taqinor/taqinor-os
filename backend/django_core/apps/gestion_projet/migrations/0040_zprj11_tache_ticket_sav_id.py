from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0039_zprj10_politique_facturation'),
    ]

    operations = [
        migrations.AddField(
            model_name='tache',
            name='ticket_sav_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID du ticket SAV (conversion)'),
        ),
    ]
