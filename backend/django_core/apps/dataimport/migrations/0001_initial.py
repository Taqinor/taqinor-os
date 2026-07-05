import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('authentication', '0014_customuser_account_lockout'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalRef',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_system', models.CharField(max_length=50)),
                ('external_id', models.CharField(max_length=150)),
                ('object_id', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dataimport_external_refs', to='authentication.company')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
        ),
        migrations.AddIndex(
            model_name='externalref',
            index=models.Index(fields=['content_type', 'object_id'], name='dataimport__content_45a3e1_idx'),
        ),
        migrations.AddConstraint(
            model_name='externalref',
            constraint=models.UniqueConstraint(fields=('company', 'external_system', 'external_id'), name='uniq_dataimport_external_ref'),
        ),
    ]
