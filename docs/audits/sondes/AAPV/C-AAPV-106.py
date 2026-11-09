# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K51 + K52 — lectures et écritures de montants d'achat sous `IsResponsableOrAdmin` (franchi par un code
quelconque du module) au lieu de `prix_achat_voir` / `achats_payer` (D-ASTK-2 / D-ASTK-3).
K51 : `installations/receptions-non-facturees/` (GR/IR) — GET (montant_provision), POST lettrer sans facture,
DELETE, POST création — par Technicien / Technicien responsable / Commercial / Admin Ventes (rôles système).
K52 : `stock/factures-fournisseur/releve-deductions-tva/` et `stock/paiements-fournisseur/ras-tva/export/`.
Témoins : `stock/factures-fournisseur/comptes-a-payer/` (PeutVoirPrixAchat) et `stock/paiements-fournisseur/`
(PeutLirePaiementsFournisseur) refusent ces rôles ; l'Administrateur passe partout."""
SONDE = {"constat": "C-AAPV-106", "sha": "c6bd9b5d52",
         "attendu": "repro si un rôle sans prix_achat_voir lit la provision / le relevé / l'export (200) alors que les témoins lui répondent 403",
         "modeles": ["installations.ReceptionNonFacturee", "stock.FactureFournisseur", "stock.PaiementFournisseur",
                     "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.apps import apps as dj
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.installations.models import ReceptionNonFacturee
    from apps.stock.models import Fournisseur
    FF = dj.get_model('achats', 'FactureFournisseur')
    LFF = dj.get_model('achats', 'LigneFactureFournisseur')
    PF = dj.get_model('achats', 'PaiementFournisseur')
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 106', slug='sonde-aapv-106')
    today = timezone.now().date()

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s106-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    roles = ['Administrateur', 'Technicien', 'Technicien responsable', 'Commercial', 'Admin Ventes']
    comptes = {n: compte(n) for n in roles}
    adm = comptes['Administrateur'][0]
    four = Fournisseur.objects.create(company=co, nom='F-S106')
    fac = FF.objects.create(company=co, reference='FF-S106', fournisseur=four, date_facture=today,
                            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))
    LFF.objects.create(facture=fac, designation='Panneaux', quantite=Decimal('10'),
                       prix_unitaire_ht=Decimal('1000'), taux_tva=Decimal('20'))
    PF.objects.create(company=fac.company, facture=fac, montant=Decimal('12000'), date_paiement=today,
                      montant_ras_tva=Decimal('1500'), taux_ras=Decimal('75'), created_by=adm)
    obs = {'perms': {n: {'prix_achat_voir': 'prix_achat_voir' in R[n], 'achats_payer': 'achats_payer' in R[n]}
                     for n in roles}}
    for n in roles:
        u, c = comptes[n]
        p1 = ReceptionNonFacturee.objects.create(company=co, libelle=f'prov {n} 1', montant_provision=Decimal('12345'),
                                                 created_by=adm)
        p2 = ReceptionNonFacturee.objects.create(company=co, libelle=f'prov {n} 2', montant_provision=Decimal('6789'),
                                                 created_by=adm)
        g = c.get('/api/django/installations/receptions-non-facturees/', **H)
        montants = []
        if g.status_code == 200:
            rows = g.data.get('results', g.data) if isinstance(g.data, dict) else g.data
            montants = sorted({str(r.get('montant_provision')) for r in rows})[:3]
        lt = c.post(f'/api/django/installations/receptions-non-facturees/{p1.id}/lettrer/', {}, format='json', **H)
        p1.refresh_from_db()
        de = c.delete(f'/api/django/installations/receptions-non-facturees/{p2.id}/', **H)
        cr = c.post('/api/django/installations/receptions-non-facturees/',
                    {'libelle': 'provision inventée', 'montant_provision': '1.00'}, format='json', **H)
        rel = c.get('/api/django/stock/factures-fournisseur/releve-deductions-tva/', **H)
        ras = c.get('/api/django/stock/paiements-fournisseur/ras-tva/export/', **H)
        t1 = c.get('/api/django/stock/factures-fournisseur/comptes-a-payer/', **H)
        t2 = c.get('/api/django/stock/paiements-fournisseur/', **H)
        obs[n] = {'grir_get': g.status_code, 'grir_montants_vus': montants,
                  'grir_lettrer': lt.status_code, 'provision_lettree': p1.lettre,
                  'grir_delete': de.status_code,
                  'grir_delete_effectif': not ReceptionNonFacturee.objects.filter(pk=p2.pk).exists(),
                  'grir_create': cr.status_code,
                  'releve_tva': rel.status_code,
                  'releve_extrait': (str(rel.data)[:110] if rel.status_code == 200 else None),
                  'ras_export': ras.status_code, 'ras_type': ras.get('Content-Type', '')[:40],
                  'ras_octets': len(ras.content) if ras.status_code == 200 else 0,
                  'temoin_comptes_a_payer': t1.status_code, 'temoin_paiements_list': t2.status_code}
    print(obs)
    sans_prix = [n for n in roles if not obs['perms'][n]['prix_achat_voir']]
    temoin_ok = obs['Administrateur']['releve_tva'] == 200 and all(
        obs[n]['temoin_comptes_a_payer'] == 403 for n in sans_prix)
    k51 = obs['Technicien']['grir_get'] == 200 and obs['Technicien']['grir_lettrer'] == 200 \
        and obs['Technicien']['grir_delete_effectif']
    k52 = any(obs[n]['releve_tva'] == 200 or obs[n]['ras_export'] == 200 for n in sans_prix)
    obs['k51_repro'] = bool(k51)
    obs['k52_repro'] = bool(k52)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and k51 and k52)
    return obs
