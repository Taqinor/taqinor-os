"""Initialise « Responsable par défaut des nouveaux leads » sur Meryem.

Additif et sûr : pour chaque profil entreprise sans responsable par défaut,
on cherche un utilisateur ACTIF de la même société dont l'identifiant, le
prénom, le nom ou l'email contient « meryem » (insensible à la casse) et on
l'assigne. Si aucun compte Meryem n'existe, le champ reste vide et le founder
le choisit dans Paramètres. Réversible : ne casse jamais le déploiement.
"""
from django.db import migrations
from django.db.models import Q


def set_meryem_default(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    User = apps.get_model('authentication', 'CustomUser')

    for profile in CompanyProfile.objects.filter(
        responsable_defaut_leads__isnull=True
    ):
        candidates = User.objects.filter(is_active=True).filter(
            Q(username__icontains='meryem')
            | Q(first_name__icontains='meryem')
            | Q(last_name__icontains='meryem')
            | Q(email__icontains='meryem')
        )
        if profile.company_id:
            candidates = candidates.filter(company_id=profile.company_id)
        meryem = candidates.order_by('id').first()
        if meryem is not None:
            profile.responsable_defaut_leads = meryem
            profile.save(update_fields=['responsable_defaut_leads'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0004_companyprofile_responsable_defaut_leads'),
    ]

    operations = [
        migrations.RunPython(set_meryem_default, noop),
    ]
