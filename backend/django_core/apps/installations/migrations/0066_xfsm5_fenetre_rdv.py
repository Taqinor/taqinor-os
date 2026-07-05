from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0065_xfsm4_intervention_priorite'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='fenetre_debut',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='intervention',
            name='fenetre_fin',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='intervention',
            name='arrivee_dans_fenetre',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
