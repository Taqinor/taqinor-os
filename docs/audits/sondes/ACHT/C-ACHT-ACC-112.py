# flake8: noqa  (sonde d'acceptation ACHT112, rejouable par scripts/sonde.py — AMET93) (D-ENF22)
"""Preuve en direct ACHT112 (P4) : rapport énergie d'un chantier d'une société à logo téléversé → logo détouré
en en-tête (module image pur quote_engine.logo via ventes.selectors.logo_entete_html), jamais l'URI brute.
Le téléchargement MinIO du logo est remplacé par un PNG à larges marges blanches (une écriture MinIO ne serait
pas annulée) ; le reste est la vraie route GET /installations/chantiers/<id>/rapport-energie/. Transaction annulée.
"""
SONDE = {
    'constat': 'C-ACHT-ACC-112',
    'sha': '673ec3f92',
    'attendu': "rapport-energie 200 application/pdf ; en-tête = <img data:image/png détouré> (hdr-logo), pas l'URI du profil",
}


def sonde(ctx):
    import io
    from PIL import Image
    from rest_framework.test import APIClient
    from authentication.models import CustomUser
    from apps.installations.models import Installation
    from apps.parametres.models import CompanyProfile
    import apps.ventes.utils.pdf as pdfmod
    import apps.installations.energy_report as er
    u = CustomUser.objects.get(username='demo_admin')
    inst = Installation.objects.filter(company=u.company).order_by('-id').first()
    prof, _ = CompanyProfile.objects.get_or_create(company=u.company)
    prof.logo_key = 'sonde/acht112-logo.png'
    prof.save()
    im = Image.new('RGB', (600, 300), 'white')
    for x in range(200, 400):
        for y in range(100, 200):
            im.putpixel((x, y), (2, 47, 83))
    buf = io.BytesIO(); im.save(buf, 'PNG'); png = buf.getvalue()
    orig_dl, orig_pdf = pdfmod._download, pdfmod._html_to_pdf
    capt = {}
    pdfmod._download = lambda bucket, key: png if key == prof.logo_key else orig_dl(bucket, key)

    def _capture(html, *a, **k):
        capt['html'] = html
        return orig_pdf(html, *a, **k)
    pdfmod._html_to_pdf = _capture
    try:
        c = APIClient(); c.force_authenticate(user=u)
        r = c.get(f'/api/django/installations/chantiers/{inst.pk}/rapport-energie/')
    finally:
        pdfmod._download, pdfmod._html_to_pdf = orig_dl, orig_pdf
    html = capt.get('html') or ''
    i = html.find('<div class="hdr-logo">')
    entete = html[i:i + 160] if i >= 0 else ''
    obs = {'installation': inst.pk, 'status': r.status_code, 'content_type': r.get('Content-Type'),
           'pdf': bytes(getattr(r, 'content', b'')[:5]) == b'%PDF-', 'entete': entete,
           'logo_data_png': 'data:image/png;base64' in entete,
           'uri_brute_absente': prof.logo_key not in html}
    obs['repro'] = r.status_code == 200 and obs['pdf'] and obs['logo_data_png'] and obs['uri_brute_absente']
    return obs
