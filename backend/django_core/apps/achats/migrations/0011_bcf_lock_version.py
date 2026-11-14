# ACNC21 — verrou optimiste du BCF : ``lock_version`` (0 à la création, +1 à
# chaque ``save()``, cf. ``core.champs_plateforme.VerrouOptimisteMixin``).
# Colonne additive à défaut constant (PostgreSQL >= 11 : pas de réécriture).
# Réversible (RemoveField implicite au retour arrière).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0010_aapv20_ligne_retour_lot_series'),
    ]

    operations = [
        migrations.AddField(
            model_name='boncommandefournisseur',
            name='lock_version',
            field=models.PositiveIntegerField(
                default=0, editable=False,
                help_text='Verrou optimiste (NTPLT17) : +1 à chaque enregistrement.'),
        ),
    ]
