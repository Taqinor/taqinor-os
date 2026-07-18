import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP55 — Instagram : ``MetaConnection.ig_user_id`` + miroirs média /
    commentaire IG + journal de publication (flux container). Chaîne linéaire :
    dépend de 0029."""

    dependencies = [
        ('adsengine', '0029_adsdeep53_comment_inbox'),
    ]

    operations = [
        migrations.AddField(
            model_name='metaconnection',
            name='ig_user_id',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='ID compte Instagram Business'),
        ),
        migrations.CreateModel(
            name='InstagramMediaMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meta_id', models.CharField(
                    max_length=64, verbose_name='ID média IG')),
                ('caption', models.TextField(
                    blank=True, default='',
                    verbose_name='Légende (LECTURE SEULE — immuable après publication)')),
                ('media_type', models.CharField(
                    blank=True, default='', max_length=16,
                    verbose_name='Type de média')),
                ('media_url', models.TextField(
                    blank=True, default='', verbose_name='URL du média')),
                ('permalink', models.TextField(
                    blank=True, default='', verbose_name='Permalien')),
                ('like_count', models.PositiveIntegerField(
                    default=0, verbose_name='J’aime')),
                ('comments_count', models.PositiveIntegerField(
                    default=0, verbose_name='Commentaires')),
                ('view_count', models.PositiveIntegerField(
                    default=0, verbose_name='Vues')),
                ('comment_enabled', models.BooleanField(
                    default=True, verbose_name='Commentaires ouverts')),
                ('timestamp', models.DateTimeField(
                    blank=True, null=True, verbose_name='Publié le')),
                ('fetched_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Récupéré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Miroir de média Instagram',
                'verbose_name_plural': 'Miroirs de média Instagram',
                'ordering': ['-timestamp', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InstagramCommentMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meta_id', models.CharField(
                    max_length=64, verbose_name='ID commentaire IG')),
                ('media_meta_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID média commenté')),
                ('parent_meta_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID commentaire parent')),
                ('message', models.TextField(
                    blank=True, default='', verbose_name='Message')),
                ('from_username', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Auteur')),
                ('like_count', models.PositiveIntegerField(
                    default=0, verbose_name='J’aime')),
                ('hidden', models.BooleanField(
                    default=False, verbose_name='Masqué')),
                ('answered', models.BooleanField(
                    default=False, verbose_name='Répondu')),
                ('timestamp', models.DateTimeField(
                    blank=True, null=True, verbose_name='Créé le (IG)')),
                ('fetched_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Récupéré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Miroir de commentaire Instagram',
                'verbose_name_plural': 'Miroirs de commentaire Instagram',
                'ordering': ['-timestamp', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InstagramPublishJob',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('media_type', models.CharField(
                    blank=True, default='', max_length=16,
                    verbose_name='Type de média')),
                ('image_url', models.TextField(
                    blank=True, default='', verbose_name='URL image (JPEG)')),
                ('video_url', models.TextField(
                    blank=True, default='', verbose_name='URL vidéo (Reel)')),
                ('caption', models.TextField(
                    blank=True, default='',
                    verbose_name='Légende (posée à la création)')),
                ('creation_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID container (creation_id)')),
                ('published_media_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID média publié')),
                ('status', models.CharField(
                    choices=[('pending', 'En attente'), ('created', 'Container créé'),
                             ('finished', 'Container prêt'), ('published', 'Publié'),
                             ('error', 'Erreur')],
                    default='pending', max_length=12, verbose_name='État')),
                ('status_code', models.CharField(
                    blank=True, default='', max_length=32,
                    verbose_name='Code de statut Meta (container)')),
                ('quota_used', models.IntegerField(
                    blank=True, null=True, verbose_name='Quota utilisé (24 h)')),
                ('quota_total', models.IntegerField(
                    blank=True, null=True, verbose_name='Quota total (24 h)')),
                ('scheduled_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Programmé pour')),
                ('error', models.TextField(
                    blank=True, default='', verbose_name='Erreur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Publication Instagram',
                'verbose_name_plural': 'Publications Instagram',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='instagrammediamirror',
            constraint=models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adseng_ig_media_meta'),
        ),
        migrations.AddConstraint(
            model_name='instagramcommentmirror',
            constraint=models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adseng_ig_comment_meta'),
        ),
    ]
