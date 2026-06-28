# Generated for N91/F21 — capture terrain hors-ligne tolérante (outbox +
# synchro idempotente). Additif : une seule table de journal d'idempotence,
# aucune colonne d'une table métier modifiée.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('installations', '0014_fg297_document_projet_revision'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldOp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_op_id', models.CharField(db_index=True, max_length=64)),
                ('op_type', models.CharField(max_length=60)),
                ('target_type', models.CharField(blank=True, default='', max_length=20)),
                ('target_id', models.PositiveIntegerField(blank=True, null=True)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('ok', models.BooleanField(default=True)),
                ('applied_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_field_ops', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Opération de capture terrain (idempotence)',
                'verbose_name_plural': 'Opérations de capture terrain (idempotence)',
                'ordering': ['-applied_le', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='fieldop',
            constraint=models.UniqueConstraint(fields=('company', 'client_op_id'), name='uniq_fieldop_company_opid'),
        ),
    ]
