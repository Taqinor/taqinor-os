"""ASEC8 — caviarde les valeurs SECRÈTES déjà copiées dans ``AuditLog.changes``.

Avant ASEC8, le diff automatique recopiait en clair le secret TOTP, le hash du
mot de passe, les codes de secours et tout champ chiffré. Cette migration de
données remplace ces valeurs par ``***`` dans les lignes existantes (le fait
que le champ a changé reste tracé). ``changes`` ne participe pas au hash
d'inviolabilité (NTSEC17) : la chaîne reste vérifiable.

Par lots de 1 000 (curseur sur la clé primaire). Retour arrière : NO-OP
VOLONTAIRE — une valeur en clair n'est jamais restaurée.
"""
from django.db import migrations

LOT = 1000


def caviarder_lignes(apps, schema_editor):
    from apps.audit.redaction import CHAMPS_SECRETS, MASQUE, champs_secrets_du_modele

    AuditLog = apps.get_model('audit', 'AuditLog')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    secrets_par_ct = {}

    def secrets_de(ct_id):
        if ct_id not in secrets_par_ct:
            noms = set(CHAMPS_SECRETS)
            ct = ContentType.objects.filter(pk=ct_id).first() if ct_id else None
            if ct is not None:
                try:
                    noms |= champs_secrets_du_modele(
                        apps.get_model(ct.app_label, ct.model))
                except LookupError:
                    pass
            secrets_par_ct[ct_id] = noms
        return secrets_par_ct[ct_id]

    dernier = 0
    while True:
        lot = list(
            AuditLog.objects.filter(pk__gt=dernier, changes__isnull=False)
            .order_by('pk').only('pk', 'content_type_id', 'changes')[:LOT])
        if not lot:
            break
        for ligne in lot:
            dernier = ligne.pk
            changes = ligne.changes
            if not isinstance(changes, list):
                continue
            secrets = secrets_de(ligne.content_type_id)
            modifie = False
            nouveaux = []
            for change in changes:
                if isinstance(change, dict) and change.get('field') in secrets \
                        and (change.get('old') != MASQUE
                             or change.get('new') != MASQUE):
                    change = {**change, 'old': MASQUE, 'new': MASQUE}
                    modifie = True
                nouveaux.append(change)
            if modifie:
                AuditLog.objects.filter(pk=ligne.pk).update(changes=nouveaux)


def ne_rien_restaurer(apps, schema_editor):
    """No-op documenté : la valeur en clair n'est jamais restaurée."""


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0008_via_portail_idx_concurrent'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(caviarder_lignes, ne_rien_restaurer),
    ]
