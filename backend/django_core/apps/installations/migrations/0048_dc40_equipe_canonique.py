# DC40 — Modèle d'ÉQUIPE terrain CANONIQUE (décision fondateur).
#
# Additif & RÉVERSIBLE (jamais destructif) :
#   1. on CRÉE la table ``Equipe`` (+ son M2M ``membres`` et ses FK
#      ``chef``/``created_by``/``company``) ;
#   2. on AJOUTE la FK NULLABLE ``Intervention.equipe_ref`` → ``Equipe``
#      (l'ancien M2M ``Intervention.equipe`` reste intact — rien ne casse) ;
#   3. une migration de DONNÉES rétro-remplit UNE ``Equipe`` canonique par
#      ensemble DISTINCT de membres trouvé sur les interventions existantes
#      (dédup par (société, frozenset(membre_ids))) et repointe ``equipe_ref``.
#
# La migration de données est RÉVERSIBLE : le reverse vide ``equipe_ref`` et
# SUPPRIME uniquement les équipes rétro-remplies (marquées par le sentinelle
# ``_DC40_TAG`` dans ``description``) — l'état d'origine (le M2M ad-hoc) est
# intégralement restauré.
#
# Noms d'index ≤ 30 caractères (contrainte Django/Postgres) ; le nom d'index
# est écrit une seule fois, identique au Meta du modèle (pas de divergence).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Sentinelle posée dans ``Equipe.description`` pour reconnaître, au reverse, les
# équipes créées par CE rétro-remplissage (et elles seules).
_DC40_TAG = '[DC40-backfill]'


def _member_ids(intervention, through_model):
    """Ids des membres du M2M ad-hoc ``Intervention.equipe`` (via la table de
    liaison brute — les modèles historiques n'exposent pas ``.equipe.all()``
    de façon fiable en migration). Trié pour un nom déterministe."""
    return sorted(
        through_model.objects
        .filter(intervention_id=intervention.id)
        .values_list('customuser_id', flat=True)
    )


def backfill_equipes(apps, schema_editor):
    """Rétro-remplit une ``Equipe`` canonique par ensemble distinct de membres
    et repointe ``Intervention.equipe_ref``. Idempotent et scopé société."""
    Intervention = apps.get_model('installations', 'Intervention')
    Equipe = apps.get_model('installations', 'Equipe')
    # Table de liaison auto-générée du M2M ``Intervention.equipe``.
    Through = Intervention.equipe.through

    # Cache {(company_id, frozenset(member_ids)): equipe_id} pour dédupliquer.
    cache = {}
    db_alias = schema_editor.connection.alias

    for interv in Intervention.objects.using(db_alias).all().iterator():
        member_ids = _member_ids(interv, Through)
        if not member_ids:
            continue  # aucune équipe ad-hoc → rien à canoniser.
        key = (interv.company_id, frozenset(member_ids))
        equipe_id = cache.get(key)
        if equipe_id is None:
            # Nom déterministe & unique par société (respecte unique_together).
            suffixe = '-'.join(str(m) for m in member_ids)
            nom = f'Équipe {suffixe}'[:120]
            equipe = Equipe.objects.using(db_alias).create(
                company_id=interv.company_id,
                nom=nom,
                actif=True,
                description=_DC40_TAG,
            )
            equipe.membres.set(member_ids)
            equipe_id = equipe.id
            cache[key] = equipe_id
        # Repointe l'intervention sur l'équipe canonique (sans toucher le M2M
        # ad-hoc, qui reste le filet de sécurité / la source du reverse).
        interv.equipe_ref_id = equipe_id
        interv.save(update_fields=['equipe_ref'])


def unbackfill_equipes(apps, schema_editor):
    """Reverse RÉEL : vide ``equipe_ref`` sur les interventions qui pointent une
    équipe rétro-remplie, puis SUPPRIME ces équipes (marquées ``_DC40_TAG``).
    L'état d'origine (le M2M ad-hoc, intact) est intégralement restauré."""
    Intervention = apps.get_model('installations', 'Intervention')
    Equipe = apps.get_model('installations', 'Equipe')
    db_alias = schema_editor.connection.alias

    backfilled = Equipe.objects.using(db_alias).filter(description=_DC40_TAG)
    backfilled_ids = list(backfilled.values_list('id', flat=True))
    if backfilled_ids:
        (Intervention.objects.using(db_alias)
         .filter(equipe_ref_id__in=backfilled_ids)
         .update(equipe_ref=None))
        backfilled.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('installations', '0047_livraison_mode_acheminement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Equipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('actif', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_equipes', to='authentication.company')),
                ('chef', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_equipes_chef', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_equipes_creees', to=settings.AUTH_USER_MODEL)),
                ('membres', models.ManyToManyField(blank=True, related_name='installations_equipes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Équipe terrain',
                'verbose_name_plural': 'Équipes terrain',
                'ordering': ['nom'],
                'unique_together': {('company', 'nom')},
            },
        ),
        migrations.AddIndex(
            model_name='equipe',
            index=models.Index(fields=['company', 'actif'], name='idx_equipe_co_actif'),
        ),
        migrations.AddField(
            model_name='intervention',
            name='equipe_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='interventions', to='installations.equipe'),
        ),
        migrations.RunPython(backfill_equipes, unbackfill_equipes),
    ]
