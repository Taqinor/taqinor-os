# XFAC1 — Avances client (paiement sans facture) + affectation multi-factures.
# ``Paiement.facture`` devient nullable (une avance/acompte à la commande
# n'a pas encore de facture) ; ``Paiement.client`` + ``statut_affectation``
# tracent l'avance jusqu'à sa ventilation. ``AffectationPaiement`` répartit un
# paiement non affecté sur une ou plusieurs factures ouvertes du même client.
# Additif et revertable : tout paiement existant reste ``facture`` posé et
# ``statut_affectation='affecte'`` (défaut du champ) → comportement inchangé.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0047_qs3_sharelink_bcf"),
        ("crm", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="paiement",
            name="facture",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="paiements",
                to="ventes.facture",
            ),
        ),
        migrations.AddField(
            model_name="paiement",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="avances",
                to="crm.client",
            ),
        ),
        migrations.AddField(
            model_name="paiement",
            name="statut_affectation",
            field=models.CharField(
                choices=[
                    ("affecte", "Affecté"),
                    ("partiellement_affecte", "Partiellement affecté"),
                    ("non_affecte", "Non affecté"),
                ],
                default="affecte",
                max_length=25,
            ),
        ),
        migrations.CreateModel(
            name="AffectationPaiement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name="ID")),
                ("montant", models.DecimalField(decimal_places=2, max_digits=12)),
                ("date_affectation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="affectations_paiement",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="affectations_effectuees",
                    to=settings.AUTH_USER_MODEL)),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="affectations_paiement", to="ventes.facture")),
                ("paiement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="affectations", to="ventes.paiement")),
            ],
            options={
                "verbose_name": "Affectation de paiement",
                "verbose_name_plural": "Affectations de paiement",
                "ordering": ["-date_affectation"],
            },
        ),
    ]
