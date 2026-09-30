"""COCKPIT-CONTRÔLE (30/09/2026) — les deux traces d'une étape de relance.

ADDITIVE, en deux moitiés (aucune contrainte, aucune colonne retirée) :

  1. ``RelanceEtape.due_initial_at`` (échéance d'ORIGINE, NULL permis) et
     ``RelanceEtape.nb_reports`` (reports HUMAINS, défaut 0) ;
  2. une REPRISE des lignes existantes : ``due_initial_at = due_at``. Le
     passé des reports n'est connu nulle part — ``nb_reports`` part de 0, et
     l'origine d'une étape déjà repoussée avant cette migration est sa date
     ACTUELLE. C'est la seule valeur vraie disponible, jamais une date
     inventée. Une ligne sans heure (d'avant MRY5) garde NULL.

PAR LOTS de clés primaires (même patron que ``0097_ckp1``) : un ``UPDATE``
global verrouillerait la table le temps de tout réécrire.

RÉVERSIBLE en no-op : le retour arrière de la moitié 1 supprime les deux
colonnes, la reprise n'a donc rien à défaire.
"""
from django.db import migrations, models
from django.db.models import F

#: Taille des lots d'écriture (voir ``0097_ckp1_relanceetape_annulee``).
LOT = 1000


def reprendre_due_initial(apps, schema_editor):
    """``due_initial_at = due_at`` sur chaque ligne qui a une heure et pas
    encore d'origine, par tranches de pk."""
    RelanceEtape = apps.get_model('crm', 'RelanceEtape')
    pks = list(RelanceEtape.objects
               .filter(due_initial_at__isnull=True, due_at__isnull=False)
               .order_by('pk')
               .values_list('pk', flat=True).iterator(chunk_size=LOT))
    for debut in range(0, len(pks), LOT):
        RelanceEtape.objects.filter(pk__in=pks[debut:debut + LOT]).update(
            due_initial_at=F('due_at'))
    return len(pks)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0115_cad178_geste_relance_appareil'),
    ]

    operations = [
        migrations.AddField(
            model_name='relanceetape',
            name='due_initial_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Échéance d'origine"),
        ),
        migrations.AddField(
            model_name='relanceetape',
            name='nb_reports',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Reports humains'),
        ),
        migrations.RunPython(reprendre_due_initial, migrations.RunPython.noop),
    ]
