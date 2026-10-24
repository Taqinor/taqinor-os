# VNT103 — retrait des champs morts ``Devis.acompte_pct`` / ``acompte_montant``.

from django.db import migrations


class Migration(migrations.Migration):
    """VNT103 : ``Devis.acompte_pct`` et ``Devis.acompte_montant`` n'ont plus aucun lecteur
    (écran, moteur PDF, empreinte du devis) ; l'acompte se lit sur l'échéancier de la vente
    (VNT28). La contrainte ``ck_devis_acompte_montant_positif`` est retirée, puis les deux
    champs quittent l'état des modèles. Les COLONNES restent en base (nullables, plus
    aucune écriture ne les remplit) : retrait en deux temps (YOPSB4), zéro perte de
    donnée, réversible (le retour arrière rend les champs à l'état et recrée la
    contrainte). Prod (lecture seule, 14/10/2026) : 375 devis, 0 valeur non nulle."""

    dependencies = [
        ('ventes', '0140_signature_figures_scellees'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='devis',
            name='ck_devis_acompte_montant_positif',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='devis',
                    name='acompte_pct',
                ),
                migrations.RemoveField(
                    model_name='devis',
                    name='acompte_montant',
                ),
            ],
            database_operations=[],
        ),
    ]
