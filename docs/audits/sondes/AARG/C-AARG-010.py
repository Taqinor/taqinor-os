# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K10 : `override_credit` d'un COMMERCIAL est honoré sur les portes de facturation alors que `peut_passer_outre`
(ADEV14 : palier admin/responsable) n'est appliqué qu'à l'acceptation (`apps/ventes/domain/cycle_vie.py::
_garde_blocages_acceptation`). `apps/ventes/views/devis_facturation.py::DevisFacturationActionsMixin.facturer` transmet
`override_credit` du corps à `apps/ventes/domain/facturation_vente.py::_emettre` (→ `verifier_credit_hold(override=True)`
+ `emettre_facture(verifier_credit=False)`) ; `generer_facture` / `facturer_complet` passent `bool(corps['override_credit'])`
à `verifier_credit_hold` sans regarder le palier. Blocage crédit actif, client au-delà du plafond, Commercial canonique
(palier normal, porte `encaisser`). Vraies routes, transaction annulée."""
SONDE = {"constat": "C-AARG-010", "sha": "56d5b623a",
         "attendu": "Commercial : /facturer emettre sans override 403 credit_hold (témoin) ; accepter avec "
                    "override_credit 403 (témoin ADEV14) ; /facturer emettre + override_credit 201, facture émise "
                    "numérotée ; ligne d'audit « débloqué par <commercial> »",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Devis", "LigneDevis", "Facture",
                     "LigneFacture", "SettingsAuditLog"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.parametres.models_audit import SettingsAuditLog
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 010', slug='sonde-aarg-010')
    r_com = Role.objects.create(company=co, nom='Commercial', permissions=list(reg.COMMERCIAL_PERMISSIONS),
                                est_systeme=True)
    com = User.objects.create_user(username='sonde-aarg010-com', password='x', company=co, role=r_com)
    from apps.ventes.domain.cycle_vie import peut_passer_outre
    tier = com.menu_tier
    autorise = peut_passer_outre(com)
    prof = CompanyProfile.get(company=co)
    prof.credit_hold_actif = True
    prof.save(update_fields=['credit_hold_actif'])
    cl = Client.objects.create(company=co, nom='Hold', prenom='K10', email='sonde-aarg-010@example.invalid',
                               plafond_credit=Decimal('100'))
    p = Produit.objects.create(company=co, nom='Kit K10', sku='SONDE-AARG-010', prix_vente=Decimal('1000'),
                               quantite_stock=50)
    f0 = Facture.objects.create(company=co, reference='FAC-SONDE-AARG10-ENCOURS', client=cl,
                                statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by=com)
    LigneFacture.objects.create(facture=f0, produit=p, designation='Encours', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    def devis(ref, accepte=True):
        d = Devis.objects.create(company=co, client=cl, reference=ref, statut=Devis.Statut.ENVOYE,
                                 taux_tva=Decimal('20.00'), created_by=com)
        LigneDevis.objects.create(devis=d, produit=p, designation='Centrale', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('10000'))
        if accepte:
            Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE)
            d.refresh_from_db()
        return d
    api = APIClient()
    api.force_authenticate(com)

    def court(r):
        d = getattr(r, 'data', None)
        if not isinstance(d, dict):
            return None
        return {k: (str(v)[:90]) for k, v in d.items() if k in ('code', 'detail', 'credit_hold', 'statut', 'facture')}
    logs0 = SettingsAuditLog.objects.filter(company=co, section='credit_hold').count()
    out = {'menu_tier': tier, 'peut_passer_outre': autorise}
    # témoin ADEV14 : l'acceptation ignore le drapeau d'un Commercial
    dacc = devis('DEV-SONDE-AARG10-ACC', accepte=False)
    r = api.post(f'/api/django/ventes/devis/{dacc.id}/accepter/', {'nom': 'Client', 'override_credit': True},
                 format='json', **H)
    dacc.refresh_from_db()
    out['temoin_accepter_override'] = [r.status_code, court(r), dacc.statut]
    # témoin : /facturer émission sans override
    d1 = devis('DEV-SONDE-AARG10-F1')
    r = api.post(f'/api/django/ventes/devis/{d1.id}/facturer/',
                 {'nature': 'acompte', 'montant_ttc': '3000.00', 'emettre': True}, format='json', **H)
    out['temoin_facturer_sans_override'] = [r.status_code, court(r)]
    # porte : /facturer émission + override_credit du Commercial
    d2 = devis('DEV-SONDE-AARG10-F2')
    r = api.post(f'/api/django/ventes/devis/{d2.id}/facturer/',
                 {'nature': 'acompte', 'montant_ttc': '3000.00', 'emettre': True, 'override_credit': True},
                 format='json', **H)
    fs = list(Facture.objects.filter(devis=d2).values_list('reference', 'statut'))
    out['facturer_override'] = [r.status_code, court(r), fs]
    # porte : generer-facture avec override_credit (passe verifier_credit_hold de la vue)
    d3 = devis('DEV-SONDE-AARG10-G')
    r = api.post(f'/api/django/ventes/devis/{d3.id}/generer-facture/', {'override_credit': True}, format='json', **H)
    out['generer_facture_override'] = [r.status_code, court(r),
                                       list(Facture.objects.filter(devis=d3).values_list('reference', 'statut'))]
    logs = list(SettingsAuditLog.objects.filter(company=co, section='credit_hold').values_list('new_value', flat=True)) \
        if hasattr(SettingsAuditLog, 'new_value') else \
        [str(x) for x in SettingsAuditLog.objects.filter(company=co, section='credit_hold')]
    out['audit_credit_hold'] = [len(logs) - logs0, [str(v)[:90] for v in logs]]
    print(out)
    emise = any(s == Facture.Statut.EMISE for _ref, s in fs)
    return {'repro': out['temoin_facturer_sans_override'][0] == 403 and out['facturer_override'][0] == 201 and emise,
            **out}
