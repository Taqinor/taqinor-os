SONDE = {"constat": "C-ACAL-VER2-51", "sha": "56d5b623a",
         "attendu": "ACAL42 parité : pour un calepinage lié à un devis BROUILLON agricole puis multi-villa, "
                    "design-context.modifiable == not est_verrouille(calepinage) ; repro=True si l'écran dit "
                    "« lecture seule » (modifiable False, raison agricole / multi-villa) alors que la porte "
                    "d'écriture laisse passer (est_verrouille False, verifier_ecriture_autorisee sans 409)"}


def sonde(ctx):
    # ACAL42 — services/verrou.est_verrouille lit SEULEMENT verdict(devis, CALEPINAGE) ;
    # views/calepinages.contexte_conception['modifiable'] lit ventes/selectors_calepinage
    # .contexte_conception_devis -> devis_concevables, qui exclut AUSSI agricole et multi-villa.
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.verrou import est_verrouille, verifier_ecriture_autorisee, VerrouilleRefuse
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACAL VER2-51', slug='sonde-acal-ver2-51')
    u = User.objects.create_user(username='sonde_acal_ver2_51', password='x', role_legacy='responsable', company=co)
    api = APIClient(); api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client sonde')
    out = {}
    for cas in ('agricole', 'multi_villa'):
        devis = Devis.objects.create(
            company=co, client=cl, reference=f'DEV-SONDE-51-{cas}', statut='brouillon',
            mode_installation=('agricole' if cas == 'agricole' else 'residentiel'))
        if cas == 'multi_villa':
            p = Produit.objects.create(company=co, nom='Panneau mono 550W', sku='V251-550',
                                       prix_vente=Decimal('2290'), prix_achat=Decimal('1'), quantite_stock=10)
            for g in (0, 1):
                LigneDevis.objects.create(devis=devis, produit=p, designation=p.nom, quantite=4,
                                          prix_unitaire=Decimal('2290'), groupe_index=g)
        cal = Calepinage.objects.create(company=co, devis=devis, client_id=cl.pk, titre=f'sonde {cas}')
        verrou = est_verrouille(cal)
        try:
            verifier_ecriture_autorisee(cal)
            porte = 'passe'
        except VerrouilleRefuse:
            porte = '409'
        r = api.get(f'/api/django/calepinage/calepinages/{cal.pk}/design-context/', HTTP_HOST='localhost')
        modifiable = (r.data or {}).get('modifiable') if r.status_code == 200 else None
        raison = (r.data or {}).get('raison_lecture_seule') if r.status_code == 200 else None
        print(f'{cas}: est_verrouille={verrou} porte={porte} design-context {r.status_code} '
              f'modifiable={modifiable} raison={str(raison)[:120]!r}')
        out[cas] = {'est_verrouille': verrou, 'porte': porte, 'modifiable': modifiable, 'statut_http': r.status_code}
    repro = any(v['statut_http'] == 200 and v['modifiable'] is not None
                and v['modifiable'] != (not v['est_verrouille']) for v in out.values())
    return {'repro': repro, **out}
