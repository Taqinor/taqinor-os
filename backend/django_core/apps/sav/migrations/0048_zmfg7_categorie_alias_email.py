# ZMFG7 - Alias e-mail par categorie d'equipement -> creation auto de
# demande. Additif : alias_email/equipe_responsable NULL par defaut ->
# aucune categorie existante ne change de comportement (FG373 generique
# reste inchange tant que l'alias n'est pas configure).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0047_zmfg6_worksheets_maintenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorieequipement",
            name="alias_email",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Adresse e-mail dédiée à cette catégorie — un message reçu "
                    "à cet alias crée un ticket correctif pré-catégorisé "
                    "(vide = pas de routage par alias)."
                ),
                max_length=254,
                null=True,
                verbose_name="Alias e-mail",
            ),
        ),
        migrations.AddField(
            model_name="categorieequipement",
            name="equipe_responsable",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Équipe de maintenance affectée automatiquement aux "
                    "tickets créés par alias e-mail pour cette catégorie."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="categories_equipement",
                to="sav.equipemaintenance",
                verbose_name="Équipe responsable",
            ),
        ),
        migrations.AddConstraint(
            model_name="categorieequipement",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("alias_email__isnull", False),
                )
                & ~models.Q(("alias_email", "")),
                fields=("company", "alias_email"),
                name="sav_categorieequipement_company_alias_uniq",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="categorie_equipement",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets",
                to="sav.categorieequipement",
            ),
        ),
    ]
