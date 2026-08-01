# NTSAN24 — Traçabilité instrument -> patient : M2M léger ActeRealise <->
# InstrumentSterilise (recherche "quels patients ont reçu un instrument du
# cycle X" en cas de rappel sanitaire).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sante', '0019_ntsan23_sterilisation'),
    ]

    operations = [
        migrations.AddField(
            model_name='acterealise',
            name='instruments_utilises',
            field=models.ManyToManyField(blank=True, related_name='actes_realises', to='sante.instrumentsterilise', verbose_name='Instruments stérilisés utilisés'),
        ),
    ]
