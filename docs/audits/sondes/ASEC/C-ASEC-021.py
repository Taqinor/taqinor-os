SONDE = {"constat": "C-ASEC-021", "sha": "5908d43bb",
         "attendu": "STATIQUE : ni DEBUG ni la sous-chaîne « demo » du slug n'OUVRENT plus un geste démo ou un cookie "
                    "sans Secure (commandes démo gardées par Company.est_demo — DEBUG n'y reste qu'un refus "
                    "SUPPLÉMENTAIRE —, règle SEC_COMPTE_DEMO_ACTIF sans retour sous DEBUG, cookies Secure décidés par "
                    "requête avant le repli historique)"}


def sonde(ctx):
    # Constat de déploiement (geste opérateur) : lecture du code monté, aucune commande démo exécutée
    # (reset/seed touchent des données et du stockage). La garde comportementale est couverte par les
    # tests nommés ASEC16/ASEC25/ASEC52 (CI).
    import inspect
    import re
    from authentication.management.commands import reset_demo_company, seed_demo, seed_demo_company
    from apps.ventes.coherence import regles_securite
    from authentication import views
    obs = {}
    for mod in (reset_demo_company, seed_demo, seed_demo_company):
        src = inspect.getsource(mod)
        obs[mod.__name__.rsplit('.', 1)[-1]] = {
            'est_demo cité': 'est_demo' in src,
            "slug 'demo' comme marqueur": bool(re.search(r"""['"]demo['"]\s+in\s+\w*slug""", src)),
            # DEBUG comme OUVREUR (« if settings.DEBUG: <autoriser> ») vs refus supplémentaire (« if not DEBUG: raise »)
            'DEBUG ouvreur': bool(re.search(r'if\s+settings\.DEBUG\s*(or|:)', src)),
            'DEBUG refus supplémentaire': bool(re.search(r'if\s+not\s+settings\.DEBUG\b.*\n\s+raise', src))}
    src = inspect.getsource(regles_securite)
    obs['regle SEC_COMPTE_DEMO_ACTIF'] = {
        'retour sous DEBUG': bool(re.search(r'if\s+settings\.DEBUG\s*:\s*return', src)),
        'est_demo cité': 'est_demo' in src}
    src = inspect.getsource(views._cookie_secure)
    i_sec, i_dbg = src.find('request.is_secure()'), src.rfind('return not settings.DEBUG')
    obs['_cookie_secure'] = {'is_secure() par requête': i_sec >= 0,
                             'repli DEBUG après is_secure()': i_dbg == -1 or i_sec < i_dbg}
    ok = (all(v['est_demo cité'] and not v["slug 'demo' comme marqueur"] and not v['DEBUG ouvreur']
              for k, v in obs.items() if k.startswith(('reset', 'seed')))
          and not obs['regle SEC_COMPTE_DEMO_ACTIF']['retour sous DEBUG']
          and obs['regle SEC_COMPTE_DEMO_ACTIF']['est_demo cité']
          and all(obs['_cookie_secure'].values()))
    return 'STATIQUE — marqueurs d\'environnement relus dans le code monté ; tenu=%s ; %s' % (ok, obs)
