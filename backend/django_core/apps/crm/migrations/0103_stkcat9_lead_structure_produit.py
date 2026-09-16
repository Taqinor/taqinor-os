# STKCAT9 (fondateur 16/09/2026, audit L3 stock ↔ CRM ↔ devis) —
# Lead.structure_produit : LE PRODUIT de structure choisi pour ce lead
# (string-FK additive, nullable). Le rail « catégorie typée » (STKCAT2) rend
# enfin sélectionnable une structure que son NOM ne trahit pas — une pergola,
# un carport, un bac lesté — là où `structure_pref` ne savait dire que
# « acier » ou « aluminium ».
#
# ADDITIVE ET RÉVERSIBLE : aucune colonne existante n'est touchée.
# `structure_pref` est CONSERVÉ tel quel (aucun AlterField) — il reste
# l'expression du besoin quand aucun produit précis n'est arrêté, et tout lead
# enregistré hier garde exactement la valeur et le type qu'il portait.
#
# Référence de modèle EN CHAÎNE (`to='stock.produit'`) : `apps.crm` n'importe
# jamais les modèles d'`apps.stock` (règle de modularité du dépôt). La
# dépendance pointe la migration qui CRÉE `stock.Produit`, pas la dernière en
# date : cette migration reste ainsi indépendante de l'avancement de la chaîne
# de `stock`.
#
# `related_name='+'` : aucun accesseur inverse sur `Produit` — un catalogue
# n'a pas à porter la liste des leads qui le citent.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_initial'),
        ('crm', '0102_cadx_une_seule_cadence_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='structure_produit',
            field=models.ForeignKey(
                blank=True,
                help_text='Produit de structure retenu pour ce lead (une '
                          'fiche du catalogue dont la catégorie est typée '
                          '« Structure »). Vide = c\'est « Préférence de '
                          'structure » (acier / aluminium) qui décide, '
                          'exactement comme avant.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='stock.produit',
                verbose_name='Structure choisie (catalogue)',
            ),
        ),
    ]
