"""AUD188 — backstop DB des invariants d'argent du devis.

``bulk_create``/``bulk_update``/``QuerySet.update``/SQL brut contournent tout
garde Python : une remise hors [0, 100] ou un prix unitaire négatif posé par
l'un de ces chemins n'était détecté par rien.

XSAL14 a rendu ``LigneDevis.quantite``/``prix_unitaire`` nullables (lignes de
section/note) : en SQL une colonne NULL satisfait un ``CHECK`` (le prédicat vaut
UNKNOWN, jamais FALSE), ces lignes restent donc valides — comportement
inchangé.

ADDITIF ET RÉVERSIBLE : que des ``AddConstraint``, aucune donnée touchée,
``git revert`` suffit. Une base portant déjà une valeur hors bornes fera
ÉCHOUER la migration — c'est voulu : la corruption doit être vue et corrigée à
la main, jamais réécrite en silence.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0109_qjr212_prix_par_kwc_option_effective'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='devis',
            constraint=models.CheckConstraint(
                condition=models.Q(remise_globale__gte=0)
                & models.Q(remise_globale__lte=100),
                name='ck_devis_remise_globale_0_100'),
        ),
        migrations.AddConstraint(
            model_name='devis',
            constraint=models.CheckConstraint(
                condition=models.Q(acompte_montant__gte=0),
                name='ck_devis_acompte_montant_positif'),
        ),
        migrations.AddConstraint(
            model_name='lignedevis',
            constraint=models.CheckConstraint(
                condition=models.Q(quantite__gte=0)
                & models.Q(prix_unitaire__gte=0),
                name='ck_lignedevis_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='lignedevis',
            constraint=models.CheckConstraint(
                condition=models.Q(remise__gte=0) & models.Q(remise__lte=100),
                name='ck_lignedevis_remise_0_100'),
        ),
    ]
