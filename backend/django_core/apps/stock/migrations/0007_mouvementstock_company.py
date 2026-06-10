from django.db import migrations, models


def backfill_company_from_produit(apps, schema_editor):
    Mouvement = apps.get_model('stock', 'MouvementStock')
    for mv in Mouvement.objects.select_related('produit').iterator(chunk_size=500):
        if mv.company_id is None and mv.produit_id and mv.produit.company_id:
            mv.company_id = mv.produit.company_id
            mv.save(update_fields=['company'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0006_add_produit_tva'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mouvementstock',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='mouvements_stock',
                to='authentication.company',
            ),
        ),
        migrations.RunPython(
            backfill_company_from_produit,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
