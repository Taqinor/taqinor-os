from django.db import migrations, models


class Migration(migrations.Migration):
    """NTADM22 — habilitation « staff support éditeur » sur ``CustomUser``.

    Purement additif (défaut False) : aucun compte existant ne devient support.
    Le drapeau est SÉPARÉ des rôles métier et de ``is_staff`` — il n'ouvre
    aucun accès par lui-même, il autorise seulement à DEMANDER une session
    d'impersonation, qui reste sans effet tant que l'Administrateur du tenant
    cible n'a pas donné son consentement explicite.

    ``apps.adminops.permissions.IsTaqinorSupportOuAdministrateur`` lisait déjà
    ce champ en ``getattr(user, 'is_taqinor_support', False)`` (repli False) :
    la migration le matérialise sans changer le comportement observé.
    """

    dependencies = [
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_taqinor_support',
            field=models.BooleanField(
                default=False, verbose_name='Staff support éditeur'),
        ),
    ]
