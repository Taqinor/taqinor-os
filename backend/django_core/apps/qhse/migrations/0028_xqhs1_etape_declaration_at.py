# Generated for XQHS1 — Workflow complet déclaration AT/MP (loi 18-12).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0027_indicateuresg"),
    ]

    operations = [
        migrations.AddField(
            model_name="declarationcnss",
            name="jours_itt",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Jours d'incapacité temporaire de travail (ITT)"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="date_certificat_initial",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date du certificat médical initial"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="date_consolidation",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date de consolidation / guérison"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="conciliation_statut",
            field=models.CharField(
                choices=[
                    ("non_requise", "Non requise"),
                    ("a_faire", "À faire"),
                    ("en_cours", "En cours"),
                    ("faite", "Faite"),
                ],
                default="non_requise", max_length=15,
                verbose_name="Statut de la conciliation préalable"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="est_maladie_professionnelle",
            field=models.BooleanField(
                default=False, verbose_name="Maladie professionnelle"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="type_maladie_professionnelle",
            field=models.CharField(
                blank=True, default="", max_length=120,
                verbose_name="Type MP (tableau marocain)"),
        ),
        migrations.AddField(
            model_name="declarationcnss",
            name="exposition_mp",
            field=models.TextField(
                blank=True, default="",
                verbose_name="Exposition (agent, durée, poste)"),
        ),
        migrations.CreateModel(
            name="EtapeDeclarationAt",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_etape", models.CharField(
                    choices=[
                        ("avis_employeur",
                         "Avis à l'employeur/assureur (48 h)"),
                        ("dossier_assureur",
                         "Dossier de déclaration à l'assureur AT (5 j)"),
                        ("information_inspection",
                         "Information de l'inspection du travail (5 j)"),
                        ("certificat_medical",
                         "Certificat médical initial (3 exemplaires)"),
                        ("suivi_itt", "Suivi des jours d'ITT"),
                        ("certificat_guerison",
                         "Certificat de guérison / consolidation"),
                        ("conciliation",
                         "Conciliation préalable obligatoire"),
                    ],
                    max_length=25, verbose_name="Type d'étape")),
                ("echeance", models.DateTimeField(
                    blank=True, null=True, verbose_name="Échéance")),
                ("fait_le", models.DateTimeField(
                    blank=True, null=True, verbose_name="Fait le")),
                ("statut", models.CharField(
                    choices=[
                        ("a_faire", "À faire"),
                        ("fait", "Fait"),
                        ("hors_delai", "Hors délai"),
                    ],
                    default="a_faire", max_length=12,
                    verbose_name="Statut")),
                ("notes", models.TextField(
                    blank=True, default="", verbose_name="Notes")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_etapes_declaration_at",
                    to="authentication.company", verbose_name="Société")),
                ("declaration", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="etapes", to="qhse.declarationcnss",
                    verbose_name="Déclaration CNSS")),
            ],
            options={
                "verbose_name": "Étape de déclaration AT/MP",
                "verbose_name_plural": "Étapes de déclaration AT/MP",
                "ordering": ["declaration", "echeance", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="etapedeclarationat",
            index=models.Index(
                fields=["company", "statut"], name="qhse_etapeat_co_statut"),
        ),
        migrations.AddIndex(
            model_name="etapedeclarationat",
            index=models.Index(
                fields=["company", "echeance"],
                name="qhse_etapeat_co_echeance"),
        ),
        migrations.AddConstraint(
            model_name="etapedeclarationat",
            constraint=models.UniqueConstraint(
                fields=("declaration", "type_etape"),
                name="qhse_etapeat_decl_type_uniq"),
        ),
    ]
