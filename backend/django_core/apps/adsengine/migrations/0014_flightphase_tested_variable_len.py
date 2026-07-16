from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSENG testfix — Élargit ``FlightPhase.tested_variable`` de 12 à 32
    caractères. La séquence canonique ``flightplan.PHASE_SEQUENCE`` inclut
    'consolidation' (13 car.), que ``max_length=12`` tronquait à la
    matérialisation (StringDataRightTruncation). Additif, réversible."""

    dependencies = [
        ("adsengine", "0013_adseng5_creative_flight"),
    ]

    operations = [
        migrations.AlterField(
            model_name="flightphase",
            name="tested_variable",
            field=models.CharField(
                blank=True, default="", max_length=32,
                verbose_name="Variable testée"),
        ),
    ]
