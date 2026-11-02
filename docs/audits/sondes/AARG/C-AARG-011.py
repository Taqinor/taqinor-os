# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K11 : sur `generer-facture` et `facturer-complet`, la vue appelle `verifier_credit_hold(override=True)` — qui
JOURNALISE « débloqué par … » (SettingsAuditLog + chatter) — puis émet SANS transmettre l'override :
`apps/ventes/utils/echeancier.py::creer_facture_tranche` → `_emettre(facture, user)` et
`apps/ventes/domain/facturation_ops.py::facturer_devis_complet` → `facturer_vente(..., emettre=True)` sans
`override_credit` → `emettre_facture(verifier_credit=True)` relève `CreditHoldError` → 403. Directeur canonique (palier
admin, porte `encaisser`), blocage crédit actif, client au-delà du plafond. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-AARG-011", "sha": "56d5b623a",
         "attendu": "Directeur : generer-facture et facturer-complet avec override_credit → 403 credit_hold, une ligne "
                    "d'audit « débloqué » chacune, aucune facture émise ; témoin /facturer emettre+override 201",
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
    co = Company.objects.create(nom='Sonde AARG 011', slug='sonde-aarg-011')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    dirc = User.objects.create_user(username='sonde-aarg011-dir', password='x', company=co, role=r_dir)
    prof = CompanyProfile.get(company=co)
    prof.credit_hold_actif = True
    prof.save(update_fields=['credit_hold_actif'])
    cl = Client.objects.create(company=co, nom='Hold', prenom='K11', email='sonde-aarg-011@example.invalid',
                               plafond_credit=Decimal('100'))
    p = Produit.objects.create(company=co, nom='Kit K11', sku='SONDE-AARG-011', prix_vente=Decimal('1000'),
                               quantite_stock=50)
    f0 = Facture.objects.create(company=co, reference='FAC-SONDE-AARG11-ENCOURS', client=cl,
                                statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by=dirc)
    LigneFacture.objects.create(facture=f0, produit=p, designation='Encours', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))

    def devis(ref):
        d = Devis.objects.create(company=co, client=cl, reference=ref, statut=Devis.Statut.ENVOYE,
                                 taux_tva=Decimal('20.00'), created_by=dirc)
        LigneDevis.objects.create(devis=d, produit=p, designation='Centrale', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('10000'))
        Devis.objects.filter(pk=d.pk).update(statut=Devis.Statut.ACCEPTE)
        d.refresh_from_db()
        return d
    api = APIClient()
    api.force_authenticate(dirc)

    def logs():
        return SettingsAuditLog.objects.filter(company=co, section='credit_hold').count()

    def court(r):
        d = getattr(r, 'data', None)
        return {k: str(v)[:90] for k, v in d.items() if k in ('code', 'detail', 'credit_hold', 'statut')} \
            if isinstance(d, dict) else None
    out = {}
    for nom, url, corps in (
            ('generer_facture', 'generer-facture', {'override_credit': True}),
            ('facturer_complet', 'facturer-complet', {'override_credit': True}),
            ('temoin_facturer', 'facturer', {'nature': 'acompte', 'montant_ttc': '3000.00', 'emettre': True,
                                              'override_credit': True})):
        d = devis(f'DEV-SONDE-AARG11-{nom}')
        avant = logs()
        r = api.post(f'/api/django/ventes/devis/{d.id}/{url}/', corps, format='json', **H)
        nouveaux = list(SettingsAuditLog.objects.filter(company=co, section='credit_hold')
                        .order_by('-id')[:max(logs() - avant, 0)].values_list('new_value', flat=True))
        out[nom] = [r.status_code, court(r), nouveaux,
                    list(Facture.objects.filter(devis=d).values_list('reference', 'statut'))]
    print(out)
    contradiction = [k for k in ('generer_facture', 'facturer_complet')
                     if out[k][0] == 403 and out[k][2] and not any(s == Facture.Statut.EMISE for _r, s in out[k][3])]
    return {'repro': bool(contradiction), 'portes_contradictoires': contradiction, 'detail': out}
