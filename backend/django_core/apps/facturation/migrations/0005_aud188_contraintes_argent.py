"""AUD188 — backstop DB des invariants d'argent de la facturation.

``Avoir`` et ``LigneAvoir`` n'avaient AUCUNE ``CheckConstraint`` — et ``Avoir``
n'a même ni ``clean()`` ni ``save()`` — tandis que le registre censé cataloguer
ces trous (``docs/db-invariants-gap.md``) avait un angle mort sur son propre
périmètre : une écriture directe en base (queryset ou SQL brut) posait un
``montant_ttc`` négatif — une note de crédit négative — qu'aucune contrainte ni
aucun outil d'audit ne détectait.

Cette migration ne contient QUE des ``AddConstraint`` : aucun ``RunPython``,
aucune écriture de masse.

ADDITIF ET RÉVERSIBLE : que des ``AddConstraint``, aucune donnée touchée,
``git revert`` suffit. Une base portant déjà des montants négatifs ou une
remise hors [0, 100] fera ÉCHOUER la migration — c'est voulu : la corruption
doit être vue et corrigée à la main, jamais réécrite en silence.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0004_pvfresh_facture_pdf_render_meta'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='facture',
            constraint=models.CheckConstraint(
                condition=models.Q(remise_globale__gte=0)
                & models.Q(remise_globale__lte=100),
                name='ck_facture_remise_globale_0_100'),
        ),
        migrations.AddConstraint(
            model_name='facture',
            constraint=models.CheckConstraint(
                condition=models.Q(montant_ht__gte=0)
                & models.Q(montant_tva__gte=0)
                & models.Q(montant_ttc__gte=0),
                name='ck_facture_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='lignefacture',
            constraint=models.CheckConstraint(
                condition=models.Q(quantite__gte=0)
                & models.Q(prix_unitaire__gte=0),
                name='ck_lignefacture_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='lignefacture',
            constraint=models.CheckConstraint(
                condition=models.Q(remise__gte=0) & models.Q(remise__lte=100),
                name='ck_lignefacture_remise_0_100'),
        ),
        migrations.AddConstraint(
            model_name='paiement',
            constraint=models.CheckConstraint(
                condition=models.Q(montant__gte=0),
                name='ck_paiement_montant_positif'),
        ),
        migrations.AddConstraint(
            model_name='avoir',
            constraint=models.CheckConstraint(
                condition=models.Q(remise_globale__gte=0)
                & models.Q(remise_globale__lte=100),
                name='ck_avoir_remise_globale_0_100'),
        ),
        migrations.AddConstraint(
            model_name='avoir',
            constraint=models.CheckConstraint(
                condition=models.Q(montant_ht__gte=0)
                & models.Q(montant_tva__gte=0)
                & models.Q(montant_ttc__gte=0),
                name='ck_avoir_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='ligneavoir',
            constraint=models.CheckConstraint(
                condition=models.Q(quantite__gte=0)
                & models.Q(prix_unitaire__gte=0),
                name='ck_ligneavoir_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='ligneavoir',
            constraint=models.CheckConstraint(
                condition=models.Q(remise__gte=0) & models.Q(remise__lte=100),
                name='ck_ligneavoir_remise_0_100'),
        ),
    ]
