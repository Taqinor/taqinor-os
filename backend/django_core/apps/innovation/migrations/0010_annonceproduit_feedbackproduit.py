import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
        ('innovation', '0009_campagneinnovation_tag_auto'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnonceProduit',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('lien', models.URLField(
                    blank=True, default='', verbose_name='Lien')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_annonces',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Annonce produit',
                'verbose_name_plural': 'Annonces produit',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='FeedbackProduit',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                (
                    'theme',
                    models.CharField(
                        choices=[
                            ('ux', 'UX'),
                            ('performance', 'Performance'),
                            ('feature', 'Fonctionnalité'),
                            ('bug', 'Bug'),
                            ('autre', 'Autre'),
                        ],
                        default='autre', max_length=12, verbose_name='Thème'),
                ),
                (
                    'statut',
                    models.CharField(
                        choices=[
                            ('envoye', 'Envoyé'),
                            ('lu', 'Lu'),
                            ('adresse', 'Adressé'),
                        ],
                        default='envoye', max_length=10, verbose_name='Statut'),
                ),
                ('message_fermeture', models.TextField(
                    blank=True, default='', verbose_name='Message de fermeture')),
                (
                    'annonce',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='feedbacks_fermes',
                        to='innovation.annonceproduit',
                        verbose_name='Fermé via annonce'),
                ),
                (
                    'auteur',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='feedbacks_produit',
                        to=settings.AUTH_USER_MODEL, verbose_name='Auteur'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_feedbacks',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Feedback produit',
                'verbose_name_plural': 'Feedbacks produit',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='feedbackproduit',
            index=models.Index(
                fields=['company', 'theme'], name='innovation_fb_co_theme'),
        ),
        migrations.AddIndex(
            model_name='feedbackproduit',
            index=models.Index(
                fields=['company', 'statut'], name='innovation_fb_co_statut'),
        ),
    ]
