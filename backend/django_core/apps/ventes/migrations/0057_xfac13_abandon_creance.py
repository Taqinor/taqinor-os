# XFAC13 — Abandon de créance (write-off) avec motifs + tolérance petits
# écarts. Additif : tous les nouveaux champs sont nullable/blank par défaut →
# comportement historique inchangé tant qu'aucun abandon n'est enregistré.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0056_alter_affectationpaiement_id_alter_facturesource_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="abandon_motif",
            field=models.CharField(
                blank=True, default="", max_length=20,
                choices=[
                    ("irrecouvrable", "Irrécouvrable"),
                    ("geste_commercial", "Geste commercial"),
                    ("ecart_reglement", "Écart de règlement"),
                    ("liquidation", "Liquidation"),
                ]),
        ),
        migrations.AddField(
            model_name="facture",
            name="abandon_montant",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text="Résiduel soldé par abandon (MAD)."),
        ),
        migrations.AddField(
            model_name="facture",
            name="abandon_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="facture",
            name="abandon_auto",
            field=models.BooleanField(
                default=False,
                help_text="Abandon proposé automatiquement sous la "
                          "tolérance d'écart de règlement société (par "
                          "opposition à un abandon manuel motivé)."),
        ),
        migrations.AddField(
            model_name="facture",
            name="abandon_par",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="factures_abandonnees",
                to=settings.AUTH_USER_MODEL),
        ),
    ]
