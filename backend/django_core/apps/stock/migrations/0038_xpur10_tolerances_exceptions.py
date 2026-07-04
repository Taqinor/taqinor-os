# XPUR10 — Tolérances par société & file d'exceptions sur le rapprochement
# 3 voies + blocage réel du paiement. Additif : AchatsParametres
# .tolerance_prix_pct/tolerance_prix_absolu_mad/tolerance_quantite_pct
# (défaut 0) + FactureFournisseur.statut_controle/motif_ecart/resolu_par/
# resolu_le (défaut 'normale' = comportement historique inchangé).
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0037_xpur9_avoir_fournisseur"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="tolerance_prix_pct",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="achatsparametres",
            name="tolerance_prix_absolu_mad",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="achatsparametres",
            name="tolerance_quantite_pct",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="statut_controle",
            field=models.CharField(
                choices=[
                    ("normale", "Normale"),
                    ("exception", "En exception"),
                    ("resolue", "Résolue"),
                ],
                default="normale", max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="motif_ecart",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="resolu_par",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="factures_fournisseur_resolues",
                to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="resolu_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
