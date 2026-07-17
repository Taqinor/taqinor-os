# Hand-authored (NTPRO5) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("immobilier", "0004_revisionloyer"),
    ]

    operations = [
        migrations.AddField(
            model_name="bail",
            name="depot_garantie_recu",
            field=models.BooleanField(default=False, verbose_name="Dépôt reçu"),
        ),
        migrations.AddField(
            model_name="bail",
            name="date_reception_depot",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date de réception du dépôt",
            ),
        ),
        migrations.AddField(
            model_name="bail",
            name="depot_garantie_restitue",
            field=models.BooleanField(
                default=False, verbose_name="Dépôt restitué"
            ),
        ),
        migrations.AddField(
            model_name="bail",
            name="date_restitution",
            field=models.DateField(
                blank=True, null=True, verbose_name="Date de restitution"
            ),
        ),
        migrations.AddField(
            model_name="bail",
            name="montant_retenu",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name="Montant retenu (retenues justifiées)",
            ),
        ),
        migrations.AddField(
            model_name="bail",
            name="motif_retenue",
            field=models.TextField(
                blank=True, default="", verbose_name="Motif de la retenue"
            ),
        ),
    ]
