# XPUR1 — Documents de conformité fournisseur + gate d'achat/paiement.
# Additif : AchatsParametres (1 par société, interrupteurs achats fins) et
# DocumentConformiteFournisseur (ARF/CNSS/RC/assurance, date d'expiration).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0028_dc34_fournisseur_type_soustraitantprofile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AchatsParametres",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("bloquer_paiement_conformite_expiree",
                 models.BooleanField(default=False)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="achats_parametres",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Paramètres achats",
                "verbose_name_plural": "Paramètres achats",
            },
        ),
        migrations.CreateModel(
            name="DocumentConformiteFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_document", models.CharField(
                    choices=[
                        ("arf", "Attestation de régularité fiscale (ARF)"),
                        ("cnss", "Attestation CNSS"),
                        ("rc", "Registre du commerce (RC)"),
                        ("assurance", "Assurance"),
                        ("autre", "Autre pièce"),
                    ],
                    default="autre", max_length=20)),
                ("reference", models.CharField(
                    blank=True, max_length=120, null=True)),
                ("date_emission", models.DateField(blank=True, null=True)),
                ("date_expiration", models.DateField(blank=True, null=True)),
                ("obligatoire", models.BooleanField(default=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="documents_conformite_fournisseur",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="documents_conformite_fournisseur_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("fournisseur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="documents_conformite",
                    to="stock.fournisseur")),
            ],
            options={
                "verbose_name": "Document de conformité fournisseur",
                "verbose_name_plural": "Documents de conformité fournisseur",
                "ordering": ["fournisseur_id", "type_document"],
            },
        ),
        migrations.AddIndex(
            model_name="documentconformitefournisseur",
            index=models.Index(
                fields=["company", "fournisseur"], name="idx_docf_co_fourn"),
        ),
        migrations.AddIndex(
            model_name="documentconformitefournisseur",
            index=models.Index(
                fields=["company", "date_expiration"],
                name="idx_docf_co_expir"),
        ),
    ]
