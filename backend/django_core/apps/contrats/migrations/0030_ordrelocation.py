# XCTR17 — Location de matériel SORTANTE (aux clients) : nouveau modèle
# `OrdreLocation` (fondation). Additif, aucune donnée existante touchée.

import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0041_xctr17_produit_location"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("contrats", "0029_contrat_responsable"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrdreLocation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("client_id", models.PositiveIntegerField(
                    verbose_name="ID du client")),
                ("numero_serie", models.CharField(
                    blank=True, default="", max_length=100,
                    verbose_name="N° de série / unité")),
                ("date_reservation", models.DateField(
                    verbose_name="Date de réservation")),
                ("date_enlevement_prevue", models.DateField(
                    verbose_name="Date d'enlèvement prévue")),
                ("date_retour_prevue", models.DateField(
                    verbose_name="Date de retour prévue")),
                ("date_enlevement_reelle", models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'enlèvement réelle")),
                ("date_retour_reelle", models.DateField(
                    blank=True, null=True,
                    verbose_name="Date de retour réelle")),
                ("statut", models.CharField(
                    choices=[
                        ("reservee", "Réservée"),
                        ("enlevee", "Enlevée"),
                        ("retournee", "Retournée"),
                        ("cloturee", "Clôturée"),
                        ("annulee", "Annulée"),
                    ],
                    default="reservee", max_length=20,
                    verbose_name="Statut")),
                ("tarif_jour", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    verbose_name="Tarif journalier appliqué")),
                ("montant_estime", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name="Montant estimé")),
                ("note", models.TextField(
                    blank=True, default="", verbose_name="Note")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ordres_location",
                    to="authentication.company", verbose_name="Société")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ordres_location_crees",
                    to=django.conf.settings.AUTH_USER_MODEL,
                    verbose_name="Créé par")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ordres_location",
                    to="stock.produit", verbose_name="Produit loué")),
            ],
            options={
                "verbose_name": "Ordre de location",
                "verbose_name_plural": "Ordres de location",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="ordrelocation",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_ordloc_co_st"),
        ),
        migrations.AddIndex(
            model_name="ordrelocation",
            index=models.Index(
                fields=["produit", "numero_serie"],
                name="contrats_ordloc_prod_serie"),
        ),
    ]
