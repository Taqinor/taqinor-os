import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('mlops', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeatureVector',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.CharField(max_length=60)),
                ('object_id', models.PositiveBigIntegerField()),
                ('features_json', models.JSONField(blank=True, default=dict)),
                ('calcule_le', models.DateTimeField(auto_now=True)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mlops_featurevector_set',
                        to='authentication.company',
                        verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Vecteur de features',
                'verbose_name_plural': 'Vecteurs de features',
                'ordering': ['content_type', 'object_id'],
            },
        ),
        migrations.AddIndex(
            model_name='featurevector',
            index=models.Index(
                fields=['company', 'content_type'],
                name='mlops_featvec_co_ct_idx'),
        ),
        migrations.AddConstraint(
            model_name='featurevector',
            constraint=models.UniqueConstraint(
                fields=('company', 'content_type', 'object_id'),
                name='uniq_mlops_featvec_co_ct_obj'),
        ),
    ]
