import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTADM18 — référentiel PLATEFORME des annonces produit + accusés de lecture.

    Purement additif. Les deux tables sont GLOBALES par conception (aucune FK
    ``company`` — exemptées du garde YDATA4 dans
    ``scripts/tenant_exempt_models.txt``) : une nouveauté de l'ERP est publiée
    une fois par l'éditeur et concerne toutes les sociétés.
    """

    dependencies = [
        ('adminops', '0004_ntadm22_session_impersonation'),
        ('roles', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnonceProduit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=200, verbose_name='Titre')),
                ('corps', models.TextField(blank=True, default='', verbose_name='Corps (markdown court)')),
                ('date_publication', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Date de publication')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='annonces_produit_publiees', to=settings.AUTH_USER_MODEL, verbose_name='Publiée par')),
                ('cible_roles', models.ManyToManyField(blank=True, related_name='annonces_produit_plateforme', to='roles.role', verbose_name='Rôles ciblés')),
            ],
            options={
                'verbose_name': 'Annonce produit',
                'verbose_name_plural': 'Annonces produit',
                'ordering': ['-date_publication', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LectureAnnonce',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lu_le', models.DateTimeField(auto_now_add=True, verbose_name='Lu le')),
                ('annonce', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lectures', to='adminops.annonceproduit', verbose_name='Annonce')),
                ('utilisateur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lectures_annonces_produit', to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': "Lecture d'annonce produit",
                'verbose_name_plural': "Lectures d'annonces produit",
                'ordering': ['-lu_le', '-id'],
                'unique_together': {('utilisateur', 'annonce')},
            },
        ),
    ]
