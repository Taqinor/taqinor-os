import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('identity', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsumedAssertion',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('assertion_id', models.CharField(
                    db_index=True, max_length=255)),
                ('consumed_at', models.DateTimeField(auto_now_add=True)),
                ('expire_le', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='consumed_assertions',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Assertion SAML consommée',
                'verbose_name_plural': 'Assertions SAML consommées',
            },
        ),
        migrations.AddConstraint(
            model_name='consumedassertion',
            constraint=models.UniqueConstraint(
                fields=('company', 'assertion_id'),
                name='identity_unique_assertion_per_company'),
        ),
    ]
