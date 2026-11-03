# flake8: noqa  (constat C-ACVI-033 : copie rejouable de la sonde groupée C-ACVI-025, sa clé dans `observe`)
"""B-6 + B-14 — import fichier mode `maj` par le service réel (`apps.dataimport.services.commit`, CSV en mémoire),
société démo. B-6 : lead SANS téléphone rapproché par e-mail, la ligne apporte un téléphone → la colonne
`phone_normalise` est-elle persistée (dédup) ? B-14 : lead dont l'e-mail a été VIDÉ par un PATCH humain
(`'email' ∈ saisies_humaines`), rapproché par téléphone, la ligne apporte un e-mail → réécrit ? chatter old→new ?
Transaction annulée."""
SONDE = {"constat": "C-ACVI-025+033", "sha": "352ae5455",
         "attendu": "défaut : telephone écrit mais phone_normalise vide en base et find_duplicates_by_contact aveugle ; "
                    "e-mail vidé par l'humain réécrit par l'import, 0 LeadActivity",
         "modeles": ["crm.Lead", "crm.LeadActivity", "dataimport.ImportJob", "dataimport.ImportJobRow"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.leads_doublons import find_duplicates_by_contact
    from apps.dataimport import services as di
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    obs = {}
    # B-6
    l6 = Lead.objects.create(company=c, nom='Import', prenom='ACVI025', email='acvi025-6@example.invalid', owner=ua)
    csv6 = 'email,telephone\nacvi025-6@example.invalid,0612340256\n'.encode('utf-8')
    r6 = di.commit(csv6, 'maj6.csv', 'leads', c, ua, mode='maj')
    l6.refresh_from_db()
    en_base = Lead.objects.filter(pk=l6.pk).values('telephone', 'phone_normalise').first()
    dup = [x.pk for x in find_duplicates_by_contact(c, phone='0612340256')]
    obs['B6'] = {'retour_commit': {k: r6.get(k) for k in ('updated', 'created', 'skipped', 'errors') if isinstance(r6, dict)},
                 'en_base': en_base, 'dedup_trouve_le_lead': l6.pk in dup, 'dedup_ids': dup[:5]}
    # B-14
    api = APIClient()
    api.force_authenticate(ua)
    l14 = Lead.objects.create(company=c, nom='Vide', prenom='ACVI025', telephone='0612340257',
                              email='acvi025-14-ancien@example.invalid', owner=ua)
    with transaction.atomic():
        r = api.patch('%s%d/' % (reverse('lead-list'), l14.id), {'email': ''}, format='json', HTTP_HOST='localhost')
    l14.refresh_from_db()
    apres_patch = {'http': r.status_code, 'email': l14.email, 'saisies_humaines': l14.saisies_humaines}
    n_act = LeadActivity.objects.filter(lead=l14).count()
    csv14 = 'telephone,email\n0612340257,acvi025-14-import@example.invalid\n'.encode('utf-8')
    r14 = di.commit(csv14, 'maj14.csv', 'leads', c, ua, mode='maj')
    l14.refresh_from_db()
    obs['B14'] = {'apres_patch': apres_patch,
                  'retour_commit': {k: r14.get(k) for k in ('updated', 'created', 'skipped', 'errors') if isinstance(r14, dict)},
                  'email_apres_import': l14.email,
                  'lignes_chatter_ajoutees': LeadActivity.objects.filter(lead=l14).count() - n_act}
    obs['defauts'] = {
        'B6_phone_normalise_non_persiste': bool(en_base and en_base['telephone']) and not en_base['phone_normalise'],
        'B6_dedup_aveugle': l6.pk not in dup,
        'B14_valeur_videe_refaite': l14.email == 'acvi025-14-import@example.invalid' and 'email' in (apres_patch['saisies_humaines'] or []),
        'B14_sans_chatter': obs['B14']['lignes_chatter_ajoutees'] == 0,
    }
    return {'repro': any(obs['defauts'].values()), 'observe': obs}
