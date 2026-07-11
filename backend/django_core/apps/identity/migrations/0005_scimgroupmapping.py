import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('roles', '0001_initial'),
        ('identity', '0004_scimtoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScimGroupMapping',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('scim_group_name', models.CharField(max_length=255)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scim_group_mappings',
                    to='authentication.company')),
                ('role', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+', to='roles.role')),
            ],
            options={
                'verbose_name': 'Mapping groupe SCIM → rôle',
                'verbose_name_plural': 'Mappings groupe SCIM → rôle',
            },
        ),
        migrations.AddConstraint(
            model_name='scimgroupmapping',
            constraint=models.UniqueConstraint(
                fields=('company', 'scim_group_name'),
                name='identity_unique_scim_group_per_company'),
        ),
    ]
