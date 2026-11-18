# Recopie de l'étape « Migrate + seed throwaway demo data » de .github/workflows/ci.yml (lane e2e 2) :
# `demo_admin` reçoit un rôle « Administrateur » portant toutes les permissions (dont `taches_voir`), comme en CI,
# pour jouer ici les specs frontend/e2e/taches-*.spec.js. À lancer par :
#   /opt/taches-cloud/acc-f3.sh manage shell < /opt/taches-cloud/e2e-demo-admin.py
from authentication.models import CustomUser
from apps.roles.models import Role
from apps.roles.permissions_registre import ALL_PERMISSIONS, SCOPE_TEAM, SCOPE_SUBTREE, SCOPE_SELF
u = CustomUser.objects.get(username='demo_admin')
perms = [p for p in ALL_PERMISSIONS if p not in (SCOPE_TEAM, SCOPE_SUBTREE, SCOPE_SELF)]
if 'taches_voir' not in perms:
    perms.append('taches_voir')
role, _ = Role.objects.get_or_create(company=u.company, nom='Administrateur')
role.permissions = perms
role.save(update_fields=['permissions'])
u.is_superuser = True
u.role = role
u.save(update_fields=['is_superuser', 'role'])
print('demo_admin role', role.pk, 'taches_voir' in role.permissions)
