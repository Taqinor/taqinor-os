# Generated for XQHS2 — Disposition des non-conformités + dérogation à durée
# limitée.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("stock", "0028_dc34_fournisseur_type_soustraitantprofile"),
        ("qhse", "0028_xqhs1_etape_declaration_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="nonconformite",
            name="disposition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("rebut", "Rebut"),
                    ("retouche", "Retouche"),
                    ("retour_fournisseur", "Retour fournisseur"),
                    ("accepte_en_etat", "Accepté en l'état"),
                    ("tri_recontrole", "Tri / recontrôle"),
                ],
                default="", max_length=20, verbose_name="Disposition"),
        ),
        migrations.AddField(
            model_name="nonconformite",
            name="disposition_par",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="qhse_ncr_dispositions",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Disposition posée par"),
        ),
        migrations.AddField(
            model_name="nonconformite",
            name="disposition_le",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Disposition posée le"),
        ),
        migrations.AddField(
            model_name="nonconformite",
            name="cout_disposition",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Coût de la disposition (interne)"),
        ),
        migrations.AddField(
            model_name="nonconformite",
            name="fournisseur",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="qhse_ncr_retours", to="stock.fournisseur",
                verbose_name="Fournisseur (retour)"),
        ),
        migrations.CreateModel(
            name="Derogation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("justification", models.TextField(
                    blank=True, default="", verbose_name="Justification")),
                ("evaluation_risque", models.TextField(
                    blank=True, default="",
                    verbose_name="Évaluation du risque")),
                ("quantite_max", models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Quantité maximale couverte")),
                ("date_debut", models.DateField(
                    blank=True, null=True, verbose_name="Date de début")),
                ("date_expiration", models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'expiration")),
                ("prealerte_jours", models.PositiveIntegerField(
                    default=15, verbose_name="Préalerte (jours)")),
                ("statut", models.CharField(
                    choices=[
                        ("active", "Active"),
                        ("expiree", "Expirée"),
                        ("cloturee", "Clôturée"),
                    ],
                    default="active", max_length=10, verbose_name="Statut")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("approbateur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="qhse_derogations_approuvees",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Approbateur")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_derogations",
                    to="authentication.company", verbose_name="Société")),
                ("non_conformite", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="derogations", to="qhse.nonconformite",
                    verbose_name="Non-conformité")),
            ],
            options={
                "verbose_name": "Dérogation",
                "verbose_name_plural": "Dérogations",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="derogation",
            index=models.Index(
                fields=["company", "statut"], name="qhse_derog_co_statut"),
        ),
        migrations.AddIndex(
            model_name="derogation",
            index=models.Index(
                fields=["company", "date_expiration"],
                name="qhse_derog_co_exp"),
        ),
    ]
