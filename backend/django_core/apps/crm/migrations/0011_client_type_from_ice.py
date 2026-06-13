"""Initialise type_client sur les clients existants.

Règle demandée : un client qui porte déjà un ICE devient « Entreprise » ;
tous les autres restent « Particulier » (la valeur par défaut). Additif et
réversible (le retour ne fait que reposer la valeur par défaut).
"""
from django.db import migrations
from django.db.models import Q


def set_type_from_ice(apps, schema_editor):
    Client = apps.get_model('crm', 'Client')
    Client.objects.filter(~Q(ice__isnull=True) & ~Q(ice='')).update(
        type_client='entreprise')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0010_client_cin_client_if_fiscal_client_rc_and_more'),
    ]

    operations = [
        migrations.RunPython(set_type_from_ice, noop),
    ]
