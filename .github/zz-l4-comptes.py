# TEMPORAIRE (zz-scratch-l4-assistant) — un compte par role systeme + jetons + prix d'achat du catalogue.
import json
from django.contrib.auth import get_user_model
from apps.roles.models import Role
from apps.stock.models import Produit
from authentication.serializers import CustomTokenObtainPairSerializer as S

U = get_user_model()
admin = U.objects.get(username='demo_admin')
jetons = {}
for cle, nom in (('commercial', 'Commercial'), ('commercial_resp', 'Commercial responsable'),
                 ('directeur', 'Directeur')):
    role = Role.objects.get(company=admin.company, nom=nom)
    u, _ = U.objects.get_or_create(username='l4_' + cle, defaults={'company': admin.company,
                                                                  'first_name': nom.split()[0]})
    u.company, u.role, u.is_active = admin.company, role, True
    u.save()
    jetons[cle] = str(S.get_token(u).access_token)
    print(cle, nom, 'prix_achat_voir' in (role.permissions or []))
json.dump(jetons, open('/tmp/l4-jetons.json', 'w'))
prix = sorted({str(p.prix_achat) for p in Produit.objects.filter(company=admin.company)
               if p.prix_achat and p.prix_achat > 0} | {str(p.prix_achat) for p in Produit.objects.filter(
                   company__isnull=True) if p.prix_achat and p.prix_achat > 0})
json.dump(prix, open('/tmp/l4-prix.json', 'w'))
print('prix d achat suivis :', len(prix))
