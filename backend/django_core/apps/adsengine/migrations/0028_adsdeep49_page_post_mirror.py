import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP49 — Miroir local d'un post organique de Page (created_by_app /
    ad_linked). Chaîne linéaire : dépend de 0027."""

    dependencies = [
        ('adsengine', '0027_adsdeep46_naming_convention_tags'),
    ]

    operations = [
        migrations.CreateModel(
            name='PagePostMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meta_id', models.CharField(
                    max_length=64, verbose_name='ID post Meta')),
                ('message', models.TextField(
                    blank=True, default='', verbose_name='Texte')),
                ('permalink', models.TextField(
                    blank=True, default='', verbose_name='Permalien')),
                ('created_time', models.DateTimeField(
                    blank=True, null=True, verbose_name='Créé le (Meta)')),
                ('is_published', models.BooleanField(
                    default=True, verbose_name='Publié')),
                ('scheduled_publish_time', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Publication programmée')),
                ('created_by_app', models.BooleanField(
                    default=False, verbose_name="Créé par l'app (éditable)")),
                ('ad_linked', models.BooleanField(
                    default=False,
                    verbose_name='Adossé à une pub (édition à risque)')),
                ('fetched_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Récupéré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Miroir de post de Page',
                'verbose_name_plural': 'Miroirs de post de Page',
                'ordering': ['-created_time', '-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='pagepostmirror',
            constraint=models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adseng_page_post_meta'),
        ),
    ]
