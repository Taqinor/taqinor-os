SONDE = {"constat": 'C-APDF-ACC-PV', "sha": '5908d43bb',
         "attendu": 'PV de réception du chantier 17 (mise en service, société 4) (documents/pv-reception) en fr et ar : profil SOLAIRE EXEMPLE avec ICE/IF/RC/patente (D-APDF-2), prestations exclues (D-APDF-4), aucun username (APDF34), aucun prix_achat, statut inchangé (langue arabe hors critère : noté)'}

import re
import unicodedata

H = {'HTTP_HOST': 'localhost'}
PA = '987654.32'       # prix_achat planté sur chaque produit de la société (oracle 7)
MG = '876543.21'       # marge_snapshot plantée sur le devis
MARQUES_CHIFFRES = ('987654', '876543')
PROFIL = {
    'nom': 'SOLAIRE EXEMPLE SARL', 'ice': '001122334455667', 'identifiant_fiscal': '44556677',
    'rc': 'RC778899', 'patente': 'PAT112233', 'capital_social': '250 000,00 MAD', 'forme_juridique': 'SARL',
    'site_web': 'solaire-exemple.ma', 'email': 'contact@solaire-exemple.ma', 'telephone': '+212 522 000 111',
    'adresse': '12 rue Exemple, Casablanca', 'rib': '011 780 0000999888777666 55', 'banque': 'Banque Exemple',
}
LEGAL = {'ice': PROFIL['ice'], 'if': PROFIL['identifiant_fiscal'], 'rc': PROFIL['rc'],
         'patente': PROFIL['patente'], 'capital': PROFIL['capital_social'], 'forme': 'SARL'}
INTERDITS = ('saham', '691213', '003799642000067', 'taqinor', 'prix_achat', 'prix d\'achat', 'revendeur')
AR = re.compile('[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')
REPLI_FR = 'Document disponible en français uniquement'
REPLI_AR = 'هذه الوثيقة متوفرة باللغة الفرنسية فقط'


def preparer(company, **profil_extra):
    from django.apps import apps
    CP = apps.get_model('parametres', 'CompanyProfile')
    p, _ = CP.objects.get_or_create(company=company)
    for k, v in dict(PROFIL, **profil_extra).items():
        setattr(p, k, v)
    p.save()
    Produit = apps.get_model('stock', 'Produit')
    Produit.objects.filter(company=company).update(prix_achat=PA)
    return p


def directeur(company):
    from django.contrib.auth import get_user_model
    U = get_user_model()
    u = U.objects.filter(company=company, is_active=True, role__nom='Directeur').order_by('id').first()
    if u is None:
        from apps.roles.models import Role
        from apps.roles import permissions_registre as reg
        role = (Role.objects.filter(company=company, nom='Directeur').first()
                or Role.objects.create(company=company, nom='Directeur',
                                       permissions=list(reg.DIRECTEUR_PERMISSIONS), est_systeme=True))
        u = U.objects.create_user(username='sonde-apdf-dir-%s' % company.id, password='Sonde-apdf-123',
                                  email='dir%s@sonde.invalid' % company.id, company=company, role=role,
                                  first_name='Directeur', last_name='Sonde')
    return u


def api_pour(user):
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user)
    return c


def poser_langue(client, lang, entreprise=False):
    client.langue_document = lang
    champs = ['langue_document']
    if entreprise:
        client.type_client = 'entreprise'
        client.ice, client.if_fiscal, client.rc = 'ICECLI000777', 'IFCLI0555', 'RCCLI0333'
        champs += ['type_client', 'ice', 'if_fiscal', 'rc']
    client.save(update_fields=champs)


def usernames(company):
    from django.contrib.auth import get_user_model
    return [u for u in get_user_model().objects.filter(company=company).values_list('username', flat=True)
            if u and len(u) >= 5]


def _norm(t):
    return unicodedata.normalize('NFKC', t or '')


def _compact(t):
    return re.sub(r'[\s   ]', '', t)


def contient_ar(texte, phrase):
    tn = _compact(_norm(texte))
    return all((w in tn) or (w[::-1] in tn) for w in _norm(phrase).split())


def lire(resp):
    import fitz
    corps = b''.join(resp.streaming_content) if getattr(resp, 'streaming', False) else resp.content
    if resp.status_code != 200 or not corps.startswith(b'%PDF'):
        return None, 'HTTP %s %s %r' % (resp.status_code, resp.get('Content-Type', ''), corps[:200])
    doc = fitz.open(stream=corps, filetype='pdf')
    textes = [pg.get_text() for pg in doc]
    images = sum(len(pg.get_images(full=True)) for pg in doc)
    polices = sorted({f[3] for pg in doc for f in pg.get_fonts()})
    pix = doc[0].get_pixmap(dpi=40)   # rastérisation de la page 1
    s = pix.samples
    encre = sum(1 for i in range(0, len(s), pix.n * 5) if s[i] < 160)
    n = len(doc)
    doc.close()
    return {'pages': n, 'texte': '\n'.join(textes), 'images': images, 'polices': polices, 'encre': encre}, None


def _ctx(t, i, n=30):
    return t[max(0, i - n):i + n].replace('\n', ' ')


def verifier(nom, lang, resp, *, pages=None, identite=True, legal=(), ar_mode=None, fr_labels=(),
             fr_labels_bloquants=False, presents=(), absents=(), images_min=None, users=(), paginer=False,
             lignes_absentes=()):
    pdf, err = lire(resp)
    e = {'doc': nom, 'lang': lang, 'defauts': [], 'notes': []}
    if pdf is None:
        e['defauts'].append('rendu KO : ' + err)
        return e
    t = pdf['texte']
    tl = t.lower()
    tc = _compact(t)
    e.update(pages=pdf['pages'], ar=len(AR.findall(t)), encre=pdf['encre'], images=pdf['images'])
    if pages is not None and pdf['pages'] not in (pages if isinstance(pages, (tuple, list, set)) else (pages,)):
        e['defauts'].append('pages %s, attendu %s' % (pdf['pages'], pages))
    if identite and 'SOLAIRE EXEMPLE' not in t.upper():
        e['defauts'].append('identité « SOLAIRE EXEMPLE » absente')
    for cle in legal:
        if _compact(LEGAL[cle]) not in tc:
            e['defauts'].append('mention légale %s (%s) absente' % (cle, LEGAL[cle]))
    for mot in INTERDITS:
        i = tl.find(mot)
        if i >= 0:
            e['defauts'].append('interdit %r : …%s…' % (mot, _ctx(t, i)))
    m = re.search(r'\bmarges?\b', tl)
    if m:
        e['defauts'].append('interdit « marge » : …%s…' % _ctx(t, m.start()))
    chiffres = re.sub(r'\D', '', t)
    for mk in MARQUES_CHIFFRES:
        if mk in chiffres:
            e['defauts'].append('marqueur prix_achat/marge %s imprimé' % mk)
    for u in users:
        if re.search(r'(?<![\w.@-])' + re.escape(u.lower()) + r'(?![\w@-])', tl):
            e['defauts'].append('username %r imprimé' % u)
    for p in presents:
        if _compact(p) not in tc:
            e['defauts'].append('attendu absent : %r' % p)
    for a in absents:
        if _compact(a) in tc:
            e['defauts'].append('présent à tort : %r' % a)
    # en RTL l'extraction rend « N / 1 صفحة » : les deux ordres sont acceptés
    if paginer and not (re.search(r'(?<!\d)1\s*/\s*%d(?!\d)' % pdf['pages'], t)
                        or (lang == 'ar' and re.search(r'(?<!\d)%d\s*/\s*1(?!\d)' % pdf['pages'], t))):
        e['defauts'].append('pagination « 1 / %s » absente' % pdf['pages'])
    lignes = {ln.strip() for ln in t.splitlines()}
    for la in lignes_absentes:
        if la in lignes:
            e['defauts'].append('prestation listée comme composant : %r' % la)
    if images_min is not None and pdf['images'] < images_min:
        e['defauts'].append('images %s < %s' % (pdf['images'], images_min))
    restes = [lb for lb in fr_labels if lb in t]
    if lang in ('ar', 'en') and restes:
        (e['defauts'] if fr_labels_bloquants else e['notes']).append('libellés FR restés : %s' % restes)
    if lang == 'ar':
        if pdf['encre'] < 50:
            e['defauts'].append('page 1 rastérisée quasi vide (encre %s)' % pdf['encre'])
        if ar_mode == 'traduit' and e['ar'] < 50:
            e['defauts'].append('arabe %s caractères < 50 (document non traduit)' % e['ar'])
        elif ar_mode == 'repli' and not (REPLI_FR in t and contient_ar(t, REPLI_AR)):
            e['defauts'].append('mention de repli FR+AR absente (D-APDF-3 a)')
        elif ar_mode is None:
            e['notes'].append('langue ar hors critère (arabe %s car.)' % e['ar'])
        if any('noto' in p.lower() and 'arabic' in p.lower() for p in pdf['polices']):
            e['notes'].append('police Noto Sans Arabic embarquée : %s' % [p for p in pdf['polices'] if 'rabic' in p])
    return e


def bilan(entrees, **extra):
    ok = all(not x['defauts'] for x in entrees) and all(v is True for k, v in extra.items()
                                                        if k.startswith('ok_'))
    lignes = []
    for x in entrees:
        lignes.append('%s|%s|p=%s|ar=%s|img=%s|%s%s' % (
            x['doc'], x['lang'], x.get('pages'), x.get('ar'), x.get('images'),
            'PASS' if not x['defauts'] else 'FAIL ' + ' ; '.join(d[:220] for d in x['defauts']),
            (' [note: ' + ' ; '.join(n[:160] for n in x['notes']) + ']') if x['notes'] else ''))
    return dict({'repro': ok, 'rendus': lignes}, **extra)

def preparer_chantier(pk):
    from django.apps import apps
    I = apps.get_model('installations', 'Installation')
    inst = I.objects.select_related('client', 'company').get(pk=pk)
    preparer(inst.company)
    bom = inst.bom if isinstance(inst.bom, list) else []
    services = []
    for it in bom:
        if isinstance(it, dict):
            it['prix_achat'] = PA
            des = (it.get('designation') or it.get('nom') or '').strip()
            # D-APDF-4 : prestations = nature « service » gelée, et les lignes Installation / Transport
            if it.get('nature') == 'service' or des in ('Installation', 'Transport'):
                services.append(des)
    I.objects.filter(pk=pk).update(bom=bom)
    inst.refresh_from_db()
    return inst, [s for s in services if s]


def sonde(ctx):
    inst, services = preparer_chantier(17)
    avant = inst.statut
    api = api_pour(directeur(inst.company))
    users = usernames(inst.company)
    res = []
    for lang in ('fr', 'ar'):
        poser_langue(inst.client, lang)
        r = api.get('/api/django/documents/chantiers/17/pv-reception/', **H)
        res.append(verifier('pv_reception', lang, r, legal=('ice', 'if', 'rc', 'patente'), lignes_absentes=services,
                            users=users))
    inst.refresh_from_db()
    return bilan(res, ok_statut_inchange=(inst.statut == avant), prestations=services)
