SONDE = {"constat": "C-ADEP-VER2-002", "sha": "1dfa7986c",
         "attendu": "si l'écart ADEP102 était réel côté Django : avec les réglages vivants du conteneur (NUM_PROXIES), la chaîne X-Forwarded-For que nginx transmet après Caddy(trusted_proxies)+realip ('V, nœudCF, V') ne rend PAS l'IP du visiteur V à la preuve de signature (_client_ip)",
         "modeles": ["ventes.DevisSignature"]}


def sonde(ctx):
    from django.conf import settings
    from django.test import RequestFactory
    from apps.ventes.public.noyau import _client_ip
    V = '41.250.10.20'
    rf = RequestFactory()
    cas = {
        # Worker -> CF (Caddy garde XFF du pair de confiance et ajoute le nœud) -> nginx realip -> append
        'worker_relaye': ('41.250.10.20, 162.158.1.2, 41.250.10.20', V),
        # CF ajoute en plus la sortie Worker 2a06:98c0:3600::103 (plage de confiance) : nginx la saute
        'worker_ipv6_sortie': ('41.250.10.20, 2a06:98c0:3600::103, 172.68.3.4, 41.250.10.20', V),
        # appelant direct d'Internet qui forge un XFF : Caddy remplace, nginx append l'appelant réel
        'direct_forge': ('203.0.113.66, 203.0.113.66', '203.0.113.66'),
    }
    obs = {}
    for nom, (xff, attendu) in cas.items():
        req = rf.post('/x', HTTP_X_FORWARDED_FOR=xff, REMOTE_ADDR='172.18.0.5')
        obs[nom] = {'ip': _client_ip(req), 'attendu': attendu}
    print('NUM_PROXIES', getattr(settings, 'NUM_PROXIES', None),
          'CF_CONNECTING_IP_TRUSTED', getattr(settings, 'CF_CONNECTING_IP_TRUSTED', None))
    print(obs)
    return {"repro": any(o['ip'] != o['attendu'] for o in obs.values()), "obs": obs,
            "num_proxies": getattr(settings, 'NUM_PROXIES', None)}
