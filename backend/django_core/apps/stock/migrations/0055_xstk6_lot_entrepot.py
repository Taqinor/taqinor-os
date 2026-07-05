# XSTK6 — registre de lots en entrepôt + garde de sortie du stock périmé.
# Additif : nouveau modèle LotEntrepot (alimenté à la confirmation de
# réception, décrémenté à la sortie FEFO) + flag société
# `bloquer_stock_perime` (défaut ON — garde de sécurité, contournable avec
# motif tracé). Comportement historique inchangé pour toute société qui
# n'utilise pas encore le suivi par lot.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0054_xstk3_code_barres"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="bloquer_stock_perime",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="LotEntrepot",
            fields=[
                ("id", models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("numero_lot", models.CharField(max_length=100)),
                ("date_peremption", models.DateField(blank=True, null=True)),
                ("quantite_recue", models.IntegerField(default=0)),
                ("quantite_restante", models.IntegerField(default=0)),
                ("reference_reception", models.CharField(
                    blank=True, max_length=80, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lots_entrepot", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="lots_entrepot_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("emplacement", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="lots_entrepot", to="stock.emplacementstock")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lots_entrepot", to="stock.produit")),
            ],
            options={
                "verbose_name": "Lot en entrepôt",
                "verbose_name_plural": "Lots en entrepôt",
                "ordering": ["date_peremption", "-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="lotentrepot",
            index=models.Index(
                fields=["company", "produit"], name="idx_lotent_co_produit"),
        ),
        migrations.AddIndex(
            model_name="lotentrepot",
            index=models.Index(
                fields=["company", "date_peremption"],
                name="idx_lotent_co_peremption"),
        ),
    ]
