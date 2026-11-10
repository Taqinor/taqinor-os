# NTPLT17 — verrou optimiste OPT-IN : ``lock_version`` (0 à la création, +1 à
# chaque ``save()``, cf. ``core.champs_plateforme.VerrouOptimisteMixin``).
# Colonne additive à défaut constant : sous PostgreSQL >= 11 l'ajout ne
# réécrit pas la table. Réversible (RemoveField implicite au retour arrière).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0135_aapv85_da_bcf_annule'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='lock_version',
            field=models.PositiveIntegerField(
                default=0, editable=False,
                help_text='Verrou optimiste (NTPLT17) : +1 à chaque enregistrement.'),
        ),
    ]
