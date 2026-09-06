"""MRY5 — `RelanceEtape` v2 + `Lead.ne_plus_contacter`.

Tout est ADDITIF et nullable ou pourvu d'un défaut : aucune ligne existante
n'est réécrite. En particulier `due_at` reste NULL sur les étapes créées avant
MRY5 — c'est la vérité, elles n'ont jamais porté d'heure ; `due_date` (NOT
NULL) continue de porter les filtres `scope`, dont le grain reste le JOUR.

`devis` est une FK EN CHAÎNE vers `ventes.Devis` (`SET_NULL`) : crm ne connaît
jamais les modèles de ventes (frontière M3, contrat import-linter).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0089_crx2_payload_source'),
        ('ventes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='ne_plus_contacter',
            field=models.BooleanField(
                default=False, verbose_name='Ne plus contacter'),
        ),
        migrations.AddField(
            model_name='relanceetape',
            name='cadence',
            field=models.CharField(
                default='contact', max_length=20, verbose_name='Cadence'),
        ),
        migrations.AddField(
            model_name='relanceetape',
            name='due_at',
            field=models.DateTimeField(
                blank=True, db_index=True, null=True,
                verbose_name='Échéance (heure)'),
        ),
        migrations.AddField(
            model_name='relanceetape',
            name='template_cle',
            field=models.CharField(
                blank=True, default='', max_length=40,
                verbose_name='Clé du gabarit de message'),
        ),
        migrations.AddField(
            model_name='relanceetape',
            name='devis',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='relance_etapes', to='ventes.devis',
                verbose_name='Devis suivi'),
        ),
        migrations.AddIndex(
            model_name='relanceetape',
            index=models.Index(
                fields=['company', 'lead', 'cadence', 'statut'],
                name='crm_relance_lead_cad_idx'),
        ),
    ]
