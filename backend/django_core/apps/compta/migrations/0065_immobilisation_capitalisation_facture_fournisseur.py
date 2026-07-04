"""XACC33 — "Immobiliser" une ligne de facture fournisseur (capitalisation).

Additif : ``Immobilisation.piece_origine_facture_fournisseur_id`` /
``piece_origine_ligne_facture_fournisseur_id`` (string-refs vers apps.stock,
jamais un import cross-app). La ligne est unique (une ligne → une seule
immobilisation) — NULL autorisé plusieurs fois (Postgres), seuls les
doublons non-nuls sont refusés par la contrainte d'unicité.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0064_immobilisation_date_mise_en_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='immobilisation',
            name='piece_origine_facture_fournisseur_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Facture fournisseur d'origine (id stock, string-ref)"),
        ),
        migrations.AddField(
            model_name='immobilisation',
            name='piece_origine_ligne_facture_fournisseur_id',
            field=models.PositiveIntegerField(blank=True, null=True, unique=True, verbose_name='Ligne de facture fournisseur d\'origine (id stock, string-ref)'),
        ),
    ]
