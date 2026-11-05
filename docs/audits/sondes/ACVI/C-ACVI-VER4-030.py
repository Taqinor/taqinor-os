# flake8: noqa  (sonde de contre-visite ACVI, rejouable par scripts/sonde.py — AMET93)
"""ACVI62 (contre-visite de clôture 04/11) — le Given exact que le test nommé contourne : la correction
humaine arrive par l'API (`PATCH /api/django/crm/leads/<id>/`, marque posée par `LeadSerializer.update`,
pas un `.update()` de queryset) et la revalidation porte sur la MÊME visite (renvoyer → terminée →
valider), pas sur une seconde visite. Attendu : 1er feu vert 36 kVA `mesure_visite`, marque levée ;
PATCH 30 → marqué ; revalidation → 30 gardé, une note « non recopiée ». Témoin : sans PATCH, la
revalidation d'une mesure corrigée (40) remplace (36 → 40). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-030", "sha": "64c9c7317",
         "attendu": "code_post_acvi62 ; apres 1er feu vert 36/mesure_visite non marque ; PATCH 30 marque ; revalidation meme visite -> 30 garde, 1 note non recopiee ; temoin sans PATCH 36 -> 40",
         "modeles": ["authentication.Company", "crm.Lead", "crm.LeadActivity", "visites.VisiteTerrain",
                     "records.Activity"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import visites_retour_lead
    from apps.crm.models import Lead, LeadActivity
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain

    code_post = hasattr(visites_retour_lead, '_feu_vert_anterieur')
    co = Company.objects.create(nom='Sonde ACVI-VER4-030', slug='sonde-acvi-ver4-030')
    u = get_user_model().objects.create_user(username='sonde-acvi-ver4-030', password='x',
                                             role_legacy='admin', company=co)
    zone = {'id': 'z1', 'libelle': 'A', 'longueur_m': 40, 'largeur_m': 18, 'pente_deg': 8,
            'orientation': 'sud', 'couverture': 'bac_acier', 'structure': 'portique',
            'surface_utile_m2': None}

    def mesures(kva):
        return {'comptage': {'type_compteur': 'triphasé', 'niveau_tension_constate': 'mt',
                             'puissance_souscrite_kva_constatee': kva},
                'toiture_ci': {'zones_toiture': [zone]}}

    def lead_ci(nom):
        return Lead.objects.create(company=co, nom=nom, type_installation='industriel', owner=u,
                                   compteur_puissance_kva=Decimal('80'),
                                   puissance_souscrite_source='declare')

    def revalider(visite, kva):
        vs.renvoyer_visite(visite, u, motif='reprendre le compteur')
        VisiteTerrain.objects.filter(pk=visite.pk).update(
            statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures(kva))
        visite.refresh_from_db()
        vs.valider_visite(visite, u)

    api = APIClient()
    api.force_authenticate(u)
    # Chemin observé
    lead = lead_ci('Usine')
    v = VisiteTerrain.objects.create(company=co, lead=lead, gabarit='ci',
                                     statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures(36))
    vs.valider_visite(v, u)
    lead.refresh_from_db()
    apres1 = (str(lead.compteur_puissance_kva), lead.puissance_souscrite_source,
              'compteur_puissance_kva' in (lead.saisies_humaines or []))
    r = api.patch(f'/api/django/crm/leads/{lead.pk}/', {'compteur_puissance_kva': '30'}, format='json')
    lead.refresh_from_db()
    apres_patch = (r.status_code, str(lead.compteur_puissance_kva), lead.puissance_souscrite_source,
                   'compteur_puissance_kva' in (lead.saisies_humaines or []))
    revalider(v, 36)
    lead.refresh_from_db()
    notes = LeadActivity.objects.filter(lead=lead, kind=LeadActivity.Kind.NOTE,
                                        body__startswith='Mesure de visite non recopiée').count()
    final = (str(lead.compteur_puissance_kva), lead.puissance_souscrite_source, notes)
    # Témoin : pas de correction humaine, mesure corrigée à la revalidation
    t = lead_ci('Temoin')
    vt = VisiteTerrain.objects.create(company=co, lead=t, gabarit='ci',
                                      statut=VisiteTerrain.Statut.TERMINEE, mesures=mesures(36))
    vs.valider_visite(vt, u)
    revalider(vt, 40)
    t.refresh_from_db()
    temoin = str(t.compteur_puissance_kva)
    obs = {'code_post_acvi62': code_post, 'apres_1er_feu_vert': apres1, 'apres_patch': apres_patch,
           'apres_revalidation': final, 'temoin_sans_patch': temoin}
    print(obs)
    repro = (code_post and apres1 == ('36.00', 'mesure_visite', False)
             and apres_patch[3] is True and final[0] == '30.00' and final[2] == 1
             and temoin == '40.00')
    return {'repro': repro, **obs}
