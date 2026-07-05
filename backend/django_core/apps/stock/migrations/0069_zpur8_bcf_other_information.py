# ZPUR8 - onglet "Other Information" Odoo au niveau du document BCF :
# acheteur, reference fournisseur, note de bas de page + report editable des
# defauts fournisseur (incoterm/conditions de paiement). Additif :
# nullable/vide = comportement historique inchange (BCF existants intacts).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stock", "0068_zpur7_relance_bcf"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="acheteur",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bons_commande_fournisseur_acheteur",
                to=settings.AUTH_USER_MODEL,
                help_text="Acheteur responsable du BCF (defaut = created_by).",
            ),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="ref_fournisseur",
            field=models.CharField(
                blank=True, max_length=100, null=True,
                help_text=(
                    "Reference de la commande cote fournisseur "
                    "(texte libre)."),
            ),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="note_bas_page",
            field=models.TextField(
                blank=True, null=True,
                help_text="Mentions imprimees en bas de page du PDF BCF.",
            ),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="incoterm",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="conditions_paiement",
            field=models.CharField(
                blank=True, max_length=200, null=True,
                help_text=(
                    "Conditions de paiement reportees du fournisseur "
                    "(editables au document), derivees de "
                    "delai_paiement_jours."),
            ),
        ),
    ]
