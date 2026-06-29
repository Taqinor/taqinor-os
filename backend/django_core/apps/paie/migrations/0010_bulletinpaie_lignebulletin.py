# Generated manually — PAIE17 Bulletin de paie + lignes
# (snapshot immuable une fois validé).
#
# Additive et réversible :
# * ``BulletinPaie`` : snapshot figé du calcul (montants brut/cotisations
#   salariales & patronales/frais pro/net imposable/IR/net à payer), statut
#   brouillon→validé, unique (periode, profil).
# * ``LigneBulletin`` : détail figé du bulletin (code/libellé/type/montant/ordre).
#
# L'immuabilité une fois ``statut == 'valide'`` est appliquée au niveau modèle
# (gardes dans ``save``/``delete``) et dans ``services`` — pas de contrainte DB
# supplémentaire requise.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("paie", "0009_rubrique_plafond_exoneration"),
    ]

    operations = [
        migrations.CreateModel(
            name="BulletinPaie",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("statut", models.CharField(
                    choices=[("brouillon", "Brouillon"), ("valide", "Validé")],
                    default="brouillon", max_length=12, verbose_name="Statut")),
                ("personnes_a_charge", models.PositiveSmallIntegerField(
                    default=0, verbose_name="Personnes à charge")),
                ("brut", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Brut")),
                ("brut_imposable", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Brut imposable")),
                ("cnss_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="CNSS salariale")),
                ("cnss_patronale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="CNSS patronale")),
                ("amo_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="AMO salariale")),
                ("amo_patronale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="AMO patronale")),
                ("cimr_salariale", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="CIMR salariale")),
                ("frais_professionnels", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Frais professionnels")),
                ("net_imposable", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Net imposable")),
                ("ir", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="IR")),
                ("retenues", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Retenues")),
                ("prime_anciennete", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Prime d'ancienneté")),
                ("charges_patronales", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Charges patronales")),
                ("net_a_payer", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Net à payer")),
                ("date_validation", models.DateTimeField(
                    blank=True, null=True, verbose_name="Validé le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_bulletins",
                    to="authentication.company",
                    verbose_name="Société")),
                ("periode", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="bulletins",
                    to="paie.periodepaie",
                    verbose_name="Période")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="bulletins",
                    to="paie.profilpaie",
                    verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Bulletin de paie",
                "verbose_name_plural": "Bulletins de paie",
                "ordering": ["-date_creation"],
                "unique_together": {("periode", "profil")},
            },
        ),
        migrations.CreateModel(
            name="LigneBulletin",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                ("libelle", models.CharField(
                    max_length=120, verbose_name="Libellé")),
                ("type", models.CharField(
                    choices=[("gain", "Gain"), ("retenue", "Retenue"),
                             ("cotisation", "Cotisation")],
                    default="gain", max_length=12, verbose_name="Type")),
                ("montant", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant")),
                ("ordre", models.PositiveIntegerField(
                    default=0, verbose_name="Ordre")),
                ("bulletin", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes",
                    to="paie.bulletinpaie",
                    verbose_name="Bulletin")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_lignes_bulletin",
                    to="authentication.company",
                    verbose_name="Société")),
            ],
            options={
                "verbose_name": "Ligne de bulletin",
                "verbose_name_plural": "Lignes de bulletin",
                "ordering": ["bulletin", "ordre", "id"],
            },
        ),
    ]
