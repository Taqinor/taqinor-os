# ZMKT15 - billets d'evenement (types, prix MAD, quotas, fenetre de vente).
# Additif : billet nullable sur InscriptionEvenement (comportement actuel =
# inscription sans billet).
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0100_zmkt14_type_evenement_pipeline"),
    ]

    operations = [
        migrations.CreateModel(
            name="BilletEvenement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(
                    max_length=200, verbose_name="Libellé")),
                ("prix_ttc_mad", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=10,
                    verbose_name="Prix TTC (MAD)")),
                ("date_debut_vente", models.DateTimeField(
                    blank=True, null=True, verbose_name="Début de vente")),
                ("date_fin_vente", models.DateTimeField(
                    blank=True, null=True, verbose_name="Fin de vente")),
                ("quota", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="Quota de places")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="billets_evenement",
                    to="authentication.company", verbose_name="Société")),
                ("evenement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="billets", to="compta.evenementmarketing",
                    verbose_name="Événement")),
            ],
            options={
                "verbose_name": "Billet d'événement",
                "verbose_name_plural": "Billets d'événement",
                "ordering": ["libelle"],
            },
        ),
        migrations.AddField(
            model_name="inscriptionevenement",
            name="billet",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inscriptions", to="compta.billetevenement",
                verbose_name="Billet"),
        ),
    ]
