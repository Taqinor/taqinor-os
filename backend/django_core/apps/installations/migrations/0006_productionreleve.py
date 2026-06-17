import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0007_mark_owner_protected"),
        ("installations", "0005_installation_art33_regularisation_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionReleve",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("periode_debut", models.DateField()),
                ("periode_fin", models.DateField()),
                ("kwh_produit", models.DecimalField(decimal_places=2, max_digits=12)),
                ("source", models.CharField(choices=[("manuel", "Saisie manuelle"), ("monitoring", "Monitoring")], default="manuel", max_length=12)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="releves_production", to="authentication.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="releves_production", to=settings.AUTH_USER_MODEL)),
                ("installation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="releves_production", to="installations.installation")),
            ],
            options={
                "verbose_name": "Relevé de production",
                "verbose_name_plural": "Relevés de production",
                "ordering": ["-periode_debut", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="productionreleve",
            index=models.Index(fields=["company", "installation"], name="installatio_company_3c77a7_idx"),
        ),
    ]
