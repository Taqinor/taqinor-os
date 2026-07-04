# Generated manually — XPAI3 mutuelle / prévoyance / assurance groupe.
#
# Additif : deux nouveaux modèles (RegimeMutuelle catalogue company-scoped,
# AdhesionMutuelle OneToOne vers ProfilPaie). Aucun champ existant modifié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI3 — Mutuelle / prévoyance / assurance groupe."""

    dependencies = [
        ("paie", "0022_xpai1_stc"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegimeMutuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("libelle", models.CharField(max_length=120, verbose_name="Libellé")),
                ("mode", models.CharField(choices=[("pourcentage", "Pourcentage"), ("fixe", "Montant fixe")], default="pourcentage", max_length=12, verbose_name="Mode de calcul")),
                ("palier", models.CharField(choices=[("celibataire", "Célibataire"), ("famille", "Famille")], default="celibataire", max_length=12, verbose_name="Palier")),
                ("part_salariale", models.DecimalField(decimal_places=4, default=0, max_digits=14, verbose_name="Part salariale (% ou montant)")),
                ("part_patronale", models.DecimalField(decimal_places=4, default=0, max_digits=14, verbose_name="Part patronale (% ou montant)")),
                ("deductible_net_imposable", models.BooleanField(default=True, verbose_name="Déductible du net imposable (part salariale)")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="paie_regimes_mutuelle", to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Régime de mutuelle",
                "verbose_name_plural": "Régimes de mutuelle",
                "ordering": ["libelle"],
            },
        ),
        migrations.CreateModel(
            name="AdhesionMutuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date_debut", models.DateField(verbose_name="Date d'adhésion")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="paie_adhesions_mutuelle", to="authentication.company", verbose_name="Société")),
                ("profil", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="adhesion_mutuelle", to="paie.profilpaie", verbose_name="Profil de paie")),
                ("regime", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="adhesions", to="paie.regimemutuelle", verbose_name="Régime")),
            ],
            options={
                "verbose_name": "Adhésion mutuelle",
                "verbose_name_plural": "Adhésions mutuelle",
                "ordering": ["-date_creation"],
            },
        ),
    ]
