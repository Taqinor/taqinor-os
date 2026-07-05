import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ged', '0035_zged4_typechampsignature'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='proprietaire',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_documents_possedes', to=settings.AUTH_USER_MODEL, verbose_name='propriétaire'),
        ),
        migrations.AddField(
            model_name='document',
            name='contact_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='contact assigné (crm.Client)'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['proprietaire'], name='ged_doc_proprio_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['company', 'contact_id'], name='ged_doc_co_contact_idx'),
        ),
    ]
