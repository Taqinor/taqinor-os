import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSDEEP53 — Boîte de réception des commentaires : miroir des commentaires
    (posts organiques + dark/ad posts) + règles de masquage par mot-clé. Chaîne
    linéaire : dépend de 0028."""

    dependencies = [
        ('adsengine', '0028_adsdeep49_page_post_mirror'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentMirror',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meta_id', models.CharField(
                    max_length=64, verbose_name='ID commentaire Meta')),
                ('object_meta_id', models.CharField(
                    blank=True, default='', max_length=128,
                    verbose_name='ID objet commenté (post / dark post)')),
                ('source', models.CharField(
                    choices=[('post', 'Post organique'),
                             ('ad', 'Post publicitaire (dark)')],
                    default='post', max_length=8, verbose_name='Origine')),
                ('parent_meta_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID commentaire parent (réponse)')),
                ('message', models.TextField(
                    blank=True, default='', verbose_name='Message')),
                ('from_name', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Auteur')),
                ('from_id', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='ID auteur')),
                ('created_time', models.DateTimeField(
                    blank=True, null=True, verbose_name='Créé le (Meta)')),
                ('like_count', models.PositiveIntegerField(
                    default=0, verbose_name='J’aime')),
                ('reply_count', models.PositiveIntegerField(
                    default=0, verbose_name='Réponses')),
                ('is_hidden', models.BooleanField(
                    default=False, verbose_name='Masqué (dernier état connu)')),
                ('hidden_verified', models.BooleanField(
                    default=False,
                    verbose_name='Masquage re-vérifié (read-back)')),
                ('can_hide', models.BooleanField(
                    default=True, verbose_name='Masquable')),
                ('can_remove', models.BooleanField(
                    default=True, verbose_name='Supprimable')),
                ('answered', models.BooleanField(
                    default=False, verbose_name='Répondu (par la Page)')),
                ('permalink', models.TextField(
                    blank=True, default='', verbose_name='Permalien')),
                ('private_reply_sent_at', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Réponse privée envoyée le')),
                ('fetched_at', models.DateTimeField(
                    blank=True, null=True, verbose_name='Récupéré le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Miroir de commentaire',
                'verbose_name_plural': 'Miroirs de commentaire',
                'ordering': ['-created_time', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CommentKeywordRule',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('keyword', models.CharField(
                    max_length=128, verbose_name='Mot-clé')),
                ('enabled', models.BooleanField(
                    default=True, verbose_name='Active')),
                ('auto', models.BooleanField(
                    default=False,
                    verbose_name='Masquage automatique (sinon : proposition seule)')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Règle de masquage par mot-clé',
                'verbose_name_plural': 'Règles de masquage par mot-clé',
                'ordering': ['keyword'],
            },
        ),
        migrations.AddConstraint(
            model_name='commentmirror',
            constraint=models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adseng_comment_meta'),
        ),
        migrations.AddConstraint(
            model_name='commentkeywordrule',
            constraint=models.UniqueConstraint(
                fields=['company', 'keyword'],
                name='uniq_adseng_comment_kw'),
        ),
    ]
