# XFAC10 — Facture pro-forma : trace/numérotation PF- indépendante des
# vraies factures. Additif : nouveau modèle uniquement.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0052_xfac8_canal_relance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProformaDocument",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=50)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="proforma_documents", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="proformas_creees", to=settings.AUTH_USER_MODEL)),
                ("devis", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="proformas", to="ventes.devis")),
            ],
            options={
                "verbose_name": "Facture pro-forma",
                "verbose_name_plural": "Factures pro-forma",
                "ordering": ["-date_creation"],
                "unique_together": {("company", "reference")},
            },
        ),
    ]
