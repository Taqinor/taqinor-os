from django.db import migrations, models


class Migration(migrations.Migration):
    """AUD107 — ``NoteDebit.remise_globale`` (miroir de Facture/Avoir).

    La note de débit n'avait AUCUN champ de remise globale : son chemin de
    repli « facture entière » recopiait les lignes 1:1 (produit, quantité,
    P.U., remise DE LIGNE, taux TVA) sans jamais la remise GLOBALE du
    document, et sa propriété ``total_ht`` sommait ces lignes. Une pénalité
    de retard adossée à une facture remisée à 15 % majorait donc le client
    sur le montant NON remisé.

    Additif et réversible : colonne décimale à 0 par défaut. Toutes les notes
    existantes la portent à 0 → totaux strictement inchangés pour elles.
    """

    dependencies = [
        ('ventes', '0109_qjr212_prix_par_kwc_option_effective'),
    ]

    operations = [
        migrations.AddField(
            model_name='notedebit',
            name='remise_globale',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Remise globale (%) reprise de la facture "
                          "d'origine.",
                max_digits=5,
            ),
        ),
    ]
