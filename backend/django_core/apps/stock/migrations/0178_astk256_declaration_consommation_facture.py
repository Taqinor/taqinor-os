"""ASTK256 — lien persistant ``DeclarationConsommation.facture`` (FK chaîne vers
``facturation.Facture``) : le n° COURANT de la facture (« FAC-… » après
émission) est servi, jamais « BROUILLON-<id> » figé.

ADDITIF + rattrapage : chaque déclaration ``facturee`` est reliée à la facture
non annulée de sa société dont ``note`` porte ``[origine:CONSIGNATION-DECL-<id>]``
(sans lien, ``document_reference`` reste le repli). RÉVERSIBLE : ``RemoveField``
(le rattrapage n'a pas de retour : la colonne disparaît avec lui).
"""
import django.db.models.deletion
from django.db import migrations, models


def relier_declarations(apps, schema_editor):
    Declaration = apps.get_model('stock', 'DeclarationConsommation')
    Facture = apps.get_model('facturation', 'Facture')
    for decl in Declaration.objects.filter(statut='facturee',
                                           facture__isnull=True):
        facture = (Facture.objects
                   .filter(company_id=decl.company_id,
                           note__contains=f'[origine:CONSIGNATION-DECL-{decl.pk}]')
                   .exclude(statut='annulee').order_by('id').first())
        if facture is not None:
            decl.facture_id = facture.pk
            decl.save(update_fields=['facture'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0177_r3_fiche_comptage_calibre_log_type'),
        ('facturation', '0023_vnt15_tranche_vivante_instantanes'),
    ]

    operations = [
        migrations.AddField(
            model_name='declarationconsommation',
            name='facture',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='facturation.facture'),
        ),
        migrations.RunPython(relier_declarations, migrations.RunPython.noop),
    ]
