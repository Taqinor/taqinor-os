# XFAC5 — Promesse de paiement (promise-to-pay) + pause de relance à
# expiration. Additif : nouveau modèle + un champ nullable sur Facture.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0049_xfac4_retenue_subie"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="exclu_relances_jusquau",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="PromessePaiement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name="ID")),
                ("montant_promis", models.DecimalField(decimal_places=2, max_digits=12)),
                ("date_promise", models.DateField()),
                ("note", models.TextField(blank=True, default="")),
                ("statut", models.CharField(
                    choices=[("en_cours", "En cours"), ("tenue", "Tenue"),
                             ("rompue", "Rompue")],
                    default="en_cours", max_length=10)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="promesses_paiement", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="promesses_paiement_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="promesses_paiement", to="ventes.facture")),
            ],
            options={
                "verbose_name": "Promesse de paiement",
                "verbose_name_plural": "Promesses de paiement",
                "ordering": ["-date_creation"],
            },
        ),
    ]
