"""ENF15 — le code de parrainage devient unique PAR SOCIÉTÉ.

``Client.code_parrainage`` portait ``unique=True`` (unicité sur toutes les
sociétés) : le validateur d'unicité de DRF répondait « déjà utilisé » (409) à un
PATCH portant le code d'un client d'une AUTRE société — un oracle d'existence
entre locataires. L'unicité est désormais bornée à la société.

Sûre sur une table peuplée : les codes existants sont uniques sur toute la table
(dérivés du pk, « TQ-<pk> »), donc a fortiori uniques par société — l'ajout de la
contrainte ne peut pas échouer. Réversible (``migrate crm 0146``) : l'unicité
globale est rétablie ; le retour n'échouerait que si deux sociétés avaient
entre-temps reçu le même code saisi à la main.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0146_regle_attribution_choix_multiples'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='code_parrainage',
            field=models.CharField(
                blank=True, max_length=20, null=True,
                verbose_name='Code de parrainage',
                help_text="Code stable partagé par ce client pour parrainer un "
                          "prospect (lien /devis/mon-toit?utm_source=parrainage&"
                          "utm_campaign=<code>)."),
        ),
        migrations.AddConstraint(
            model_name='client',
            constraint=models.UniqueConstraint(
                fields=('company', 'code_parrainage'),
                name='crm_client_code_parrainage_societe'),
        ),
    ]
