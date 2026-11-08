# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K05 — « Retirer des modèles » sans contrôle D-ACAL-12 : C1 (ouvert sur L) marqué modèle n'est plus « l'ouvert »
de L (ACAL187), donc `depuis-lead` crée C2 ; `POST demarquer-modele/` sur C1 répond 200 et L porte alors DEUX
calepinages ouverts. Jumeau protégé : la restauration corbeille (`_refuser_si_le_lead_a_deja_un_ouvert`).
Témoin : avant le démarquage, un seul ouvert (C2)."""
SONDE = {"constat": "C-ACON-005", "sha": "33cba7f5d",
         "attendu": "repro si marquer C1 (200) -> depuis-lead L = 201 (C2) -> demarquer C1 = 200 et "
                    "calepinages_ouverts_du_lead(L) = 2 ; témoin : avant démarquage = [C2]",
         "modeles": ["calepinage.Calepinage", "records.TaggedItem"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.calepinage.selectors import calepinages_ouverts_du_lead
    from apps.calepinage.services.creation import ouvrir_ou_creer_pour_lead
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 005', slug='sonde-acon-005')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = get_user_model().objects.create_user(username='sonde_acon_005', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    L = Lead.objects.create(company=co, nom='Toiture', prenom='K05')
    c1, _ = ouvrir_ou_creer_pour_lead(L.pk, co, user=u, titre='C1')
    base = '/api/django/calepinage/calepinages/'
    m = api.post(f'{base}{c1.pk}/marquer-modele/', {}, format='json', **H)
    dl = api.post(f'{base}depuis-lead/', {'lead': L.pk}, format='json', **H)
    avant = [c.pk for c in calepinages_ouverts_du_lead(co, L.pk)]
    d = api.post(f'{base}{c1.pk}/demarquer-modele/', {}, format='json', **H)
    apres = [c.pk for c in calepinages_ouverts_du_lead(co, L.pk)]
    c2 = (dl.data or {}).get('calepinage')
    obs = {'c1': c1.pk, 'marquer_http': m.status_code, 'depuis_lead_http': dl.status_code, 'c2': c2,
           'ouverts_avant_demarquage': avant, 'demarquer_http': d.status_code,
           'demarquer_corps': str(d.data)[:120], 'ouverts_apres': apres}
    temoin_ok = m.status_code == 200 and dl.status_code == 201 and avant == [c2]
    defaut = d.status_code == 200 and sorted(apres) == sorted([c1.pk, c2])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    print(obs)
    return obs
