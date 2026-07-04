# XFSM15 — Suivi des récidives (callbacks / retour sur panne). Champs
# additifs : flag + lien origine (loose FK entier vers
# installations.Intervention, résolu via installations.selectors) + motif +
# non_facturable (défaut False = comportement inchangé).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0030_xfsm1_facturation_hors_garantie'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='est_recidive',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='intervention_origine_id',
            field=models.IntegerField(
                blank=True, null=True,
                help_text="ID de l'installations.Intervention d'origine "
                          'suspectée (récidive), résolu via '
                          'installations.selectors.'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='motif_recidive',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='ticket',
            name='non_facturable',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='savslasettings',
            name='recidive_fenetre_jours',
            field=models.PositiveIntegerField(default=30),
        ),
    ]
