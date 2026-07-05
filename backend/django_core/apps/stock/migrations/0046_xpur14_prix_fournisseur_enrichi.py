# XPUR14 — PrixFournisseur enrichi : code article fournisseur, paliers de
# quantité, validité, import xlsx. Additif : champs vides/paliers absents =
# comportement historique inchangé (tarif de base toujours proposé, PDF sans
# colonne « Réf. fournisseur »).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0045_xpur13_seuil_deviation_prix"),
    ]

    operations = [
        migrations.AddField(
            model_name="prixfournisseur",
            name="ref_produit_fournisseur",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="prixfournisseur",
            name="date_debut",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prixfournisseur",
            name="date_fin",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="PalierPrixFournisseur",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("qte_min", models.PositiveIntegerField()),
                ("prix", models.DecimalField(
                    decimal_places=2, max_digits=10)),
                ("prix_fournisseur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paliers", to="stock.prixfournisseur")),
            ],
            options={
                "verbose_name": "Palier de prix fournisseur",
                "verbose_name_plural": "Paliers de prix fournisseur",
                "ordering": ["qte_min"],
                "unique_together": {("prix_fournisseur", "qte_min")},
            },
        ),
    ]
