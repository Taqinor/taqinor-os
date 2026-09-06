"""AUD509 — les PREUVES d'un contrat ne partent plus en cascade.

``SignatureContrat.contrat``, ``RetenueGarantie.contrat`` et
``Caution.contrat`` etaient en ``CASCADE`` : une suppression DURE du contrat
(admin Django, shell, script de reprise) effacait en silence les preuves de
signature (loi 53-05) et les garanties financieres avec lui. Le garde de statut
de ``ContratViewSet`` est la premiere barriere ; ce ``PROTECT`` est la defense
en profondeur, au niveau de la BASE, pour tous les chemins qui ne passent pas
par l'API.

Purement declaratif et revertable : aucune donnee n'est touchee, seule la
regle d'integrite change.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0045_aud818_contrat_soft_delete'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caution',
            name='contrat',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cautions', to='contrats.contrat', verbose_name='Contrat'),
        ),
        migrations.AlterField(
            model_name='retenuegarantie',
            name='contrat',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='retenues_garantie', to='contrats.contrat', verbose_name='Contrat'),
        ),
        migrations.AlterField(
            model_name='signaturecontrat',
            name='contrat',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='signatures', to='contrats.contrat', verbose_name='Contrat'),
        ),
    ]
