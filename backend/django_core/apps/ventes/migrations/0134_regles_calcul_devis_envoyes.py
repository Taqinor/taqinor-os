# Décision fondateur 08/10/2026 — « nouveaux rendus seulement » : les devis
# déjà envoyés gardent les règles de calcul d'origine (1) ; les autres (et
# tout devis créé ensuite) suivent les règles corrigées (2). AddField +
# RunPython réversible (le retour arrière supprime simplement la colonne).

from django.db import migrations, models


def figer_devis_envoyes(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    (Devis.objects
     .exclude(statut='brouillon', date_envoi__isnull=True)
     .update(regles_calcul=1))


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0133_adev33_remise_approuvee_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='regles_calcul',
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.RunPython(figer_devis_envoyes, migrations.RunPython.noop),
    ]
