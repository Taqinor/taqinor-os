from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0047_xqhs18_exercice_urgence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incident',
            name='type_incident',
            field=models.CharField(
                choices=[
                    ('accident', 'Accident'),
                    ('presqu_accident', 'Presqu’accident'),
                    ('incident', 'Incident'),
                    ('environnement', 'Environnement'),
                ],
                default='incident', max_length=20,
                verbose_name="Type d'événement"),
        ),
        migrations.AddField(
            model_name='incident',
            name='substance',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Substance'),
        ),
        migrations.AddField(
            model_name='incident',
            name='quantite_estimee',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Quantité estimée'),
        ),
        migrations.AddField(
            model_name='incident',
            name='quantite_unite',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Unité'),
        ),
        migrations.AddField(
            model_name='incident',
            name='milieu_touche',
            field=models.CharField(blank=True, choices=[('sol', 'Sol'), ('eau', 'Eau'), ('air', 'Air')], default='', max_length=10, verbose_name='Milieu touché'),
        ),
        migrations.AddField(
            model_name='incident',
            name='notification_requise',
            field=models.BooleanField(default=False, verbose_name='Notification à autorité requise'),
        ),
        migrations.AddField(
            model_name='incident',
            name='autorite_notifiee',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Autorité notifiée'),
        ),
        migrations.AddField(
            model_name='incident',
            name='date_notification',
            field=models.DateField(blank=True, null=True, verbose_name='Date de notification'),
        ),
        migrations.AddField(
            model_name='incident',
            name='date_limite_notification',
            field=models.DateField(blank=True, null=True, verbose_name='Date limite de notification'),
        ),
    ]
