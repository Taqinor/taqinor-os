"""WIR128 — PermisTravail.delivre_par / valide_par : CharField → FK utilisateur.

Un permis validé ne portait aucun lien auditable (texte libre). On aligne sur
les modèles voisins (ActionCorrectivePreventive.verifiee_par, ConsignationLoto)
en traçant le délivreur / valideur par FK ``authentication.User`` (SET_NULL).

Migration en quatre temps pour préserver un backfill best-effort du texte
existant : (1) ajout des FK temporaires, (2) appariement best-effort de l'ancien
texte à un utilisateur de la même société (username / nom complet), (3) retrait
des anciens CharField, (4) renommage des FK aux noms définitifs. Réversible :
l'inverse recrée les CharField vides (le texte d'origine n'est pas restauré —
best-effort assumé).
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _match_user(User, company_id, texte):
    """Meilleur appariement d'un texte libre à un utilisateur de la société."""
    texte = (texte or '').strip()
    if not texte:
        return None
    qs = User.objects.filter(company_id=company_id)
    # 1) username exact
    u = qs.filter(username__iexact=texte).first()
    if u is not None:
        return u
    # 2) nom complet « Prénom Nom »
    parts = texte.split()
    if len(parts) >= 2:
        u = qs.filter(
            first_name__iexact=parts[0],
            last_name__iexact=' '.join(parts[1:])).first()
        if u is not None:
            return u
    return None


def backfill_valideurs(apps, schema_editor):
    PermisTravail = apps.get_model('qhse', 'PermisTravail')
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0],
                          settings.AUTH_USER_MODEL.split('.')[1])
    for permis in PermisTravail.objects.all().iterator():
        delivre = _match_user(User, permis.company_id, permis.delivre_par)
        valide = _match_user(User, permis.company_id, permis.valide_par)
        changed = False
        if delivre is not None:
            permis.delivre_par_user = delivre
            changed = True
        if valide is not None:
            permis.valide_par_user = valide
            changed = True
        if changed:
            permis.save(update_fields=['delivre_par_user', 'valide_par_user'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('qhse', '0055_ncr_date_creation_editable'),
    ]

    operations = [
        migrations.AddField(
            model_name='permistravail',
            name='delivre_par_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='qhse_permis_delivres',
                to=settings.AUTH_USER_MODEL, verbose_name='Délivré par'),
        ),
        migrations.AddField(
            model_name='permistravail',
            name='valide_par_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='qhse_permis_valides',
                to=settings.AUTH_USER_MODEL, verbose_name='Validé par'),
        ),
        migrations.RunPython(backfill_valideurs, noop),
        migrations.RemoveField(model_name='permistravail', name='delivre_par'),
        migrations.RemoveField(model_name='permistravail', name='valide_par'),
        migrations.RenameField(
            model_name='permistravail',
            old_name='delivre_par_user', new_name='delivre_par'),
        migrations.RenameField(
            model_name='permistravail',
            old_name='valide_par_user', new_name='valide_par'),
    ]
