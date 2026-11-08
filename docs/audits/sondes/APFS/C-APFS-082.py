# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K81 — prix d'ACHAT du routeur `installations` servis sans `prix_achat_voir`, et écriture d'achats sans
`achats_commander`. Société A : fournisseur, produit, contrat de prix (+ ligne `prix_convenu`), commande cadre
(+ ligne `prix_negocie`, appel), dossier d'import (+ frais `montant`, ligne landed cost `valeur_fob`), chantier +
livraison (`cout_transport`). Rejeu par la VRAIE route (cookie JWT réel) en Commercial, Viewer, Technicien (rôles
système SANS `prix_achat_voir`), contrôle positif Administrateur. Témoin ASTK14 : le même rôle sur
`achats/bons-commande-fournisseur/<id>/` (prix masqués). Écriture : Technicien responsable (`installation_gerer`,
sans `achats_commander`) POST contrat de prix / ligne / commande cadre. Transaction annulée."""
SONDE = {"constat": "C-APFS-082", "sha": "57d3fd371d",
         "attendu": "repro si Commercial/Viewer/Technicien lisent prix_convenu / prix_negocie / montant / valeur_fob / "
                    "cout_transport sur les routes installations alors que le BCF témoin leur masque ses prix ; "
                    "et Technicien responsable crée un contrat de prix (201) sans achats_commander",
         "modeles": ["authentication.Company", "authentication.CustomUser", "roles.Role", "stock.Fournisseur",
                     "stock.Produit", "installations.ContratPrixFournisseur", "installations.ContratPrixLigne",
                     "installations.CommandeCadre", "installations.CommandeCadreLigne", "installations.AppelCommande",
                     "installations.DossierImport", "installations.FraisImport", "installations.LandedCostLigne",
                     "installations.Installation", "installations.Livraison", "stock.BonCommandeFournisseur"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Fournisseur, Produit, BonCommandeFournisseur, LigneBonCommandeFournisseur
    from apps.installations.models_contrat_prix import ContratPrixFournisseur, ContratPrixLigne
    from apps.installations.models_commande_cadre import CommandeCadre, CommandeCadreLigne, AppelCommande
    from apps.installations.models_dossier_import import DossierImport
    from apps.installations.models_landed_cost import FraisImport, LandedCostLigne
    from apps.installations.models_livraison import Livraison
    from apps.installations.models import Installation
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(reg.CANONICAL_SYSTEM_ROLES)
    today = timezone.now().date()
    co = Company.objects.create(nom='Sonde APFS 082 A', slug='sonde-apfs-082-a')

    def compte(nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom, defaults={'permissions': perms, 'est_systeme': True})
        return U.objects.create_user(username='apfs082-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms))

    adm = compte('Administrateur', 'adm')
    roles = {'Commercial': compte('Commercial', 'com'), 'Viewer': compte('Viewer', 'vie'),
             'Technicien': compte('Technicien', 'tec')}
    tresp = compte('Technicien responsable', 'tresp')
    erreurs = {}

    def creer(cle, fn):
        try:
            with transaction.atomic():
                return fn()
        except Exception as exc:  # noqa
            erreurs[cle] = repr(exc)[:160]
            return None

    f = Fournisseur.objects.create(company=co, nom='Fournisseur 082')
    p = Produit.objects.create(company=co, nom='Onduleur 082', sku='APFS082-P', prix_vente=Decimal('5000'))
    cpf = creer('cpf', lambda: ContratPrixFournisseur.objects.create(company=co, reference='CPF-082', intitule='Contrat 082',
                                                                   fournisseur=f, created_by=adm))
    cpl = creer('cpl', lambda: ContratPrixLigne.objects.create(contrat=cpf, produit=p, prix_convenu=Decimal('777.77'),
                                                             remise_pct=Decimal('5')))
    cc = creer('cc', lambda: CommandeCadre.objects.create(company=co, reference='CC-082', intitule='Cadre 082',
                                                        fournisseur=f, created_by=adm))
    ccl = creer('ccl', lambda: CommandeCadreLigne.objects.create(commande_cadre=cc, produit=p,
                                                               prix_negocie=Decimal('666.66'), volume_engage=Decimal('100')))
    ap = creer('appel', lambda: AppelCommande.objects.create(company=co, ligne=ccl, quantite=Decimal('3'), created_by=adm))
    di = creer('dossier', lambda: DossierImport.objects.create(company=co, reference='DI-082', designation='Import 082',
                                                             fournisseur=f, created_by=adm))
    fi = creer('frais', lambda: FraisImport.objects.create(company=co, dossier=di, montant=Decimal('5555.55'),
                                                         created_by=adm))
    lcl = creer('landed', lambda: LandedCostLigne.objects.create(company=co, dossier=di, produit=p, quantite=Decimal('10'),
                                                               valeur_fob=Decimal('4444.40')))
    inst = creer('chantier', lambda: Installation.objects.create(company=co, reference='CH-APFS082'))
    liv = creer('livraison', lambda: Livraison.objects.create(company=co, reference='LIV-082', installation=inst,
                                                            cout_transport=Decimal('333.33')))
    bcf = BonCommandeFournisseur.objects.create(company=co, reference='BCF-APFS082', fournisseur=f)
    LigneBonCommandeFournisseur.objects.create(bon_commande=bcf, produit=p, quantite=2, prix_achat_unitaire=Decimal('70'))

    CIBLES = {
        'contrats-prix-fournisseur': cpf, 'contrats-prix-lignes': cpl, 'commandes-cadre': cc,
        'commandes-cadre-lignes': ccl, 'appels-commande': ap, 'dossiers-import': di, 'frais-import': fi,
        'landed-cost-lignes': lcl, 'livraisons': liv,
    }
    EXACTES = {'prix_achat', 'prix_unitaire_ht', 'prix_convenu', 'montant_achete', 'frais_annexes', 'montant',
               'total_valeur', 'valeur', 'prix_negocie', 'valeur_fob', 'remise_pct', 'prix_achat_unitaire'}
    PREFIXES = ('prix_achat_', 'total_achat', 'montant_', 'cout_', 'budget_')

    def cles_prix(d, acc, pre=''):
        if isinstance(d, dict):
            for k, v in d.items():
                if (k in EXACTES or k.startswith(PREFIXES)) and v not in (None, '', [], {}):
                    acc.add(pre + k)
                cles_prix(v, acc, pre + k + '.' if isinstance(v, (dict, list)) else pre)
        elif isinstance(d, list):
            for x in d:
                cles_prix(x, acc, pre)
        return acc

    def client(u):
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    def j(r):
        try:
            return r.json()
        except Exception:  # noqa
            return None

    def lire(u):
        c = client(u)
        out = {}
        for route, obj in CIBLES.items():
            if obj is None:
                out[route] = 'non créé'
                continue
            r = c.get(f'/api/django/installations/{route}/{obj.pk}/', **H)
            rl = c.get(f'/api/django/installations/{route}/', **H)
            out[route] = f"get={r.status_code} list={rl.status_code} prix={sorted(cles_prix(j(r), set()))}"
        r = c.get(f'/api/django/installations/contrats-prix-fournisseur/prix-convenu/?produit={p.pk}', **H)
        out['prix-convenu'] = f"{r.status_code} {str(j(r))[:90]}"
        r = c.get(f'/api/django/achats/bons-commande-fournisseur/{bcf.pk}/', **H)
        out['TEMOIN_bcf'] = f"get={r.status_code} prix={sorted(cles_prix(j(r), set()))}"
        return out

    obs = {'erreurs_creation': erreurs, 'prix_achat_voir': {k: 'prix_achat_voir' in R[k] for k in
                                                            ('Commercial', 'Viewer', 'Technicien', 'Administrateur')}}
    for k, u in roles.items():
        obs[k] = lire(u)
    obs['Administrateur (contrôle positif)'] = lire(adm)
    # Écriture : Technicien responsable sans achats_commander
    ct = client(tresp)
    w = {'achats_commander': 'achats_commander' in R['Technicien responsable'],
         'installation_gerer': 'installation_gerer' in R['Technicien responsable']}
    r = ct.post('/api/django/installations/contrats-prix-fournisseur/',
                {'intitule': 'Contrat posé par Tech resp', 'fournisseur': f.pk}, format='json', **H)
    w['POST contrat'] = r.status_code
    cid = (j(r) or {}).get('id') if isinstance(j(r), dict) else None
    if cid:
        r2 = ct.post('/api/django/installations/contrats-prix-lignes/',
                     {'contrat': cid, 'produit': p.pk, 'prix_convenu': '1.00'}, format='json', **H)
        w['POST ligne prix_convenu=1.00'] = r2.status_code
    r3 = ct.post('/api/django/installations/commandes-cadre/',
                 {'intitule': 'Cadre posé par Tech resp', 'fournisseur': f.pk}, format='json', **H)
    w['POST commande cadre'] = r3.status_code
    if r3.status_code >= 400:
        w['detail cadre'] = str(j(r3))[:120]
    r4 = ct.post('/api/django/achats/bons-commande-fournisseur/', {'fournisseur': f.pk}, format='json', **H)
    w['TEMOIN POST BCF (ACHT54)'] = r4.status_code
    obs['ecriture_Technicien_responsable'] = w

    lecteurs = [k for k in roles if any("prix=['" in v or 'prix=["' in v for kk, v in obs[k].items()
                                        if kk not in ('TEMOIN_bcf', 'prix-convenu'))]
    temoin_masque = all(obs[k]['TEMOIN_bcf'].endswith('prix=[]') or 'get=403' in obs[k]['TEMOIN_bcf']
                        or 'get=404' in obs[k]['TEMOIN_bcf'] for k in roles)
    obs['roles_lisant_prix_installations'] = lecteurs
    obs['temoin_bcf_masque_aux_3_roles'] = temoin_masque
    obs['repro'] = bool(lecteurs and temoin_masque)
    return obs
