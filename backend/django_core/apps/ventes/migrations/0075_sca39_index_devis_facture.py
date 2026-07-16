# SCA39 / YOPSB6 — pose les index chemin-de-l'argent Devis + Facture
# (sous-ensemble de NTPLT20) CONCURREMMENT : ventes_devis et ventes_facture
# sont les deux tables les plus chaudes, un AddIndex nu les verrouillerait en
# écriture pendant toute la construction en production. Même mécanisme que
# crm/0049 (AddIndexConcurrently + lock_timeout) — jamais d'AddIndex nommé nu.
# Les noms d'index sont EXPLICITES et identiques à ceux déclarés dans
# Meta.indexes des modèles (aucune divergence de nom hachée possible).

from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY est interdit dans une transaction.
    atomic = False

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('crm', '0049_qw10_lead_dedup_indexes_concurrent'),
        ('ventes', '0074_alter_facture_abandon_motif'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Échoue vite (3s) plutôt que de geler la base si un autre verrou long
        # est déjà tenu sur une des deux tables cibles.
        migrations.RunSQL(
            sql="SET lock_timeout = '3s';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name='devis',
            index=models.Index(
                fields=['company', 'statut'],
                name='ventes_devis_co_statut_idx'),
        ),
        AddIndexConcurrently(
            model_name='devis',
            index=models.Index(
                fields=['company', 'date_creation'],
                name='ventes_devis_co_datecrea_idx'),
        ),
        AddIndexConcurrently(
            model_name='facture',
            index=models.Index(
                fields=['company', 'statut'],
                name='ventes_fact_co_statut_idx'),
        ),
        AddIndexConcurrently(
            model_name='facture',
            index=models.Index(
                fields=['company', 'date_emission'],
                name='ventes_fact_co_dateemis_idx'),
        ),
    ]
