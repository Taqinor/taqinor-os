"""AUD188 — backstop DB des invariants de ``LigneEcriture``.

``creer_ecriture`` — la fabrique unique des écritures — créait ses lignes en
boucle sans jamais appeler ``full_clean()`` et ne revalidait QUE l'écriture
globale (l'équilibre) : les trois règles de ``LigneEcriture.clean()`` étaient du
code MORT sur le chemin de production. Comme le contrôle amont compare des
SOMMES, deux erreurs symétriques se compensaient, et une écriture dont chaque
ligne est simultanément débitée ET créditée de son propre montant était
acceptée — gonflant les colonnes MOUVEMENTS de la balance, le journal et le FEC
déposé à la DGI.

ADDITIF ET RÉVERSIBLE : deux ``CheckConstraint``, aucune donnée touchée,
``git revert`` suffit. Une base portant déjà des lignes violant l'invariant
fera ÉCHOUER la migration — c'est voulu : la corruption doit être vue et
corrigée à la main, jamais réécrite en silence par une migration.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0124_aud174_pointage_unique_par_ligne_gl'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='ligneecriture',
            constraint=models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name='ck_ligneecriture_montants_positifs'),
        ),
        migrations.AddConstraint(
            model_name='ligneecriture',
            constraint=models.CheckConstraint(
                condition=~(models.Q(debit__gt=0) & models.Q(credit__gt=0)),
                name='ck_ligneecriture_pas_debit_et_credit'),
        ),
    ]
