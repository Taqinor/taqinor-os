import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("stock", "0080_odx19_achats_split_repoint"),
    ]

    operations = [
        migrations.CreateModel(
            name="OptionProduit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_options_produit",
                        to="authentication.company"),
                ),
                (
                    "produit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_options",
                        to="stock.produit"),
                ),
                ("groupe_option", models.CharField(
                    help_text="Groupe de l'option (ex. « Onduleur », « Batterie »).",
                    max_length=100)),
                ("obligatoire", models.BooleanField(
                    default=False,
                    help_text="Le groupe doit être renseigné dans la configuration.")),
            ],
            options={
                "verbose_name": "Option produit",
                "verbose_name_plural": "Options produit",
                "ordering": ["groupe_option", "id"],
            },
        ),
        migrations.CreateModel(
            name="ContrainteCompatibilite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_contraintes_compatibilite",
                        to="authentication.company"),
                ),
                (
                    "produit_a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_contraintes_a",
                        to="stock.produit"),
                ),
                (
                    "produit_b",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_contraintes_b",
                        to="stock.produit"),
                ),
                ("type", models.CharField(
                    choices=[
                        ("INCOMPATIBLE", "Incompatible"),
                        ("REQUIERT", "Requiert"),
                        ("RECOMMANDE", "Recommandé"),
                    ],
                    max_length=20)),
                ("message_utilisateur", models.CharField(
                    blank=True, default="",
                    help_text="Message affiché à l'utilisateur quand la contrainte joue.",
                    max_length=255)),
            ],
            options={
                "verbose_name": "Contrainte de compatibilité",
                "verbose_name_plural": "Contraintes de compatibilité",
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="optionproduit",
            index=models.Index(
                fields=["company", "groupe_option"], name="cpq_optprod_co_grp"),
        ),
        migrations.AddIndex(
            model_name="contraintecompatibilite",
            index=models.Index(
                fields=["company", "type"], name="cpq_contr_co_type"),
        ),
        migrations.AddIndex(
            model_name="contraintecompatibilite",
            index=models.Index(
                fields=["company", "produit_a"], name="cpq_contr_co_pa"),
        ),
    ]
