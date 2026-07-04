# XPUR6 — Conditions de paiement fournisseur & échéancier multi-tranches.
# Additif : Fournisseur.delai_paiement_jours/fin_de_mois/escompte_pct/
# escompte_jours (défauts 0/False/0/0 = comportement historique inchangé) +
# EcheanceFactureFournisseur (tranches optionnelles).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0033_xpur5_fiche_fournisseur_enrichie"),
    ]

    operations = [
        migrations.AddField(
            model_name="fournisseur",
            name="delai_paiement_jours",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="fin_de_mois",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="escompte_pct",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="escompte_jours",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="EcheanceFactureFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("pourcentage", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    help_text='Pourcentage du TTC de cette tranche '
                              '(ex. 30.00).')),
                ("montant", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("date_echeance", models.DateField()),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="echeances_facture_fournisseur",
                    to="authentication.company")),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="echeances", to="stock.facturefournisseur")),
            ],
            options={
                "verbose_name": "Échéance de facture fournisseur",
                "verbose_name_plural": "Échéances de facture fournisseur",
                "ordering": ["date_echeance", "id"],
            },
        ),
    ]
