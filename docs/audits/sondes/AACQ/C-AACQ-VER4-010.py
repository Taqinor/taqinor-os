# flake8: noqa  (sonde de contre-visite AACQ 04/11, rejouable par scripts/sonde.py — AMET93)
"""AACQ38 (contre-visite) : `veille_decouverte.py::legende_vers_domaine` ne garde le sous-domaine que pour
les hébergeurs listés dans `data/veille_lexiques/places_de_marche.json::hebergeurs_boutiques` (15 entrées).
Un hébergeur absent (e-monsite.com, webnode.fr, jimdofree.com…) rend le domaine NU de l'hébergeur :
deux boutiques distinctes `a.e-monsite.com` / `b.e-monsite.com` partagent la clé ('domaine', 'e-monsite.com')
de `veille_regles.py::detecter_doublons` → l'une est classée « doublon ». Témoin : la même paire en
myshopify.com (hébergeur listé) n'est pas doublon. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AACQ-VER4-010", "sha": "8fb8ba32b",
         "attendu": "témoin myshopify : aucun doublon ; e-monsite.com / webnode.fr : domaine = hébergeur nu, une des deux Pages classée 'doublon' (attendu sain : aucune)",
         "modeles": ["authentication.Company", "adsengine.VeilleAnnonceur", "adsengine.VeilleVerdict"]}


def sonde(ctx):
    from django.test import override_settings
    from django.utils import timezone
    from authentication.models import Company
    from apps.adsengine import veille_decouverte as vd
    from apps.adsengine import veille_regles as vr
    from apps.adsengine.models import VeilleAnnonceur

    def classer(slug, legendes):
        co = Company.objects.create(nom=slug, slug=slug)
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[co.id]):
            dec = vd.creer_decouverte(co, None, {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                'plafond_appels': 5, 'plafond_pages_par_requete': 5})
        pubs = [
            {'id': f'{slug}-{i}', 'page_id': f'{slug}-P{i}',
             'page_name': f'Boutique {i}',
             'ad_creative_bodies': [f'Texte propre numéro {i} de la page'],
             'ad_creative_link_captions': [leg]}
            for i, leg in enumerate(legendes)]
        vd.ingerer_page(dec.requetes.get(), {'pubs': pubs, 'a_suivant': False}, 1)
        compte = vr.appliquer_regles(dec, maintenant=timezone.now())
        classes = sorted(VeilleAnnonceur.objects.filter(company=co).values_list('classe', flat=True))
        return {'compte': dict(compte) if hasattr(compte, 'items') else compte, 'classes': classes}

    obs = {
        'domaines': {leg: vd.legende_vers_domaine(leg) for leg in (
            'boutique-a.myshopify.com', 'a.e-monsite.com', 'b.e-monsite.com', 'a.webnode.fr', 'a.jimdofree.com')},
        'temoin_myshopify': classer('sonde-aacq-v4-010-shop', ['boutique-a.myshopify.com', 'chic-b.myshopify.com']),
        'e_monsite': classer('sonde-aacq-v4-010-emon', ['boutique-a.e-monsite.com', 'chic-b.e-monsite.com']),
        'webnode': classer('sonde-aacq-v4-010-wbn', ['boutique-a.webnode.fr', 'chic-b.webnode.fr']),
    }
    code_aacq38 = obs['domaines']['boutique-a.myshopify.com'] == 'boutique-a.myshopify.com'
    temoin_ok = 'doublon' not in obs['temoin_myshopify']['classes']
    ecart = ('doublon' in obs['e_monsite']['classes']) or ('doublon' in obs['webnode']['classes'])
    obs['code_aacq38_present'] = code_aacq38
    obs['repro'] = bool(code_aacq38 and temoin_ok and ecart)
    return obs
