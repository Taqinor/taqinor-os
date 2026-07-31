"""YDATA2 — le devis d'un dossier réglementaire / de subvention devient PROTECT.

Revue `check_on_delete.py --financial` : `RegulatoryDossier.devis` et
`SubventionDossier.devis` étaient en CASCADE. Or `DELETE /ventes/devis/<id>/`
est un endpoint LIVE (rôle admin) : supprimer un devis effaçait donc en
silence le dossier ONEE/ANRE (et, en cascade, ses pièces `DossierChecklistItem`
et sa navette `DossierExchange`) ainsi que le dossier de subvention, y compris
`montant_demande`/`montant_accorde` et un statut `verse` — de la preuve
comptable et réglementaire détruite sans trace.

PROTECT refuse désormais la suppression tant qu'un dossier existe (même patron
que `FactureSource.devis`, déjà PROTECT). `reset_demo_company._delete_cascading`
gère génériquement les `ProtectedError`, donc la purge des tenants de démo reste
fonctionnelle.

Changement d'`on_delete` uniquement : opération d'ÉTAT, aucun SQL émis, aucune
donnée touchée — réversible à l'identique (retour à CASCADE).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0089_alter_rooflayout_devis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='regulatorydossier',
            name='devis',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='dossiers_reglementaires', to='ventes.devis', verbose_name='Devis'),
        ),
        migrations.AlterField(
            model_name='subventiondossier',
            name='devis',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subvention_dossiers', to='ventes.devis', verbose_name='Devis'),
        ),
    ]
