#!/usr/bin/env python3
"""AMET98 (C-AMET-025) — rejeu d'une table de parcours sur UN enregistrement de la pile LOCALE.

    python scripts/rejouer_parcours.py PA4 --enregistrement <id> [--modele ventes.Devis] [--donnees f.json]
                                       [--couvre AMET98] [--timeout 2400]

Chaque étape jouable de `apps/<pilote>/parcours/<PA>.json` est jouée par l'API réelle (`APIClient`,
utilisateur de la société de l'enregistrement) dans UNE transaction annulée, via `scripts/sonde.py`
(AMET93 : mail en mémoire, Celery coupé, HTTP sortant bloqué, comptes avant / après). Ordre : la chaîne
`suite` depuis la 1re étape ; une étape hors chaîne (porte alternative) est une VARIANTE jouée avant son
ancre puis annulée (point de sauvegarde). Route : `Classe.methode` par le MRO des vues ; une fonction de
domaine par la vue qui porte son nom ou qui l'APPELLE ; une étape `beat` / `tache` appelle sa fonction si
elle n'a aucun argument requis. URL : `pk` = objet courant du modèle de la vue, `<x>_id` = objet courant
du modèle x ; un objet créé est rattaché au modèle de PERSISTANCE de l'étape (jamais à celui de la vue).

Verdicts : PASS / FAIL ; NON_JOUEE (objet courant absent, arguments ou corps manquants — 400 sans corps
fourni — : bloque la couverture de ses tâches) ; NON_JOUABLE_API (aucune vue n'expose ni n'appelle la
fonction d'entrée, ou `non_jouable` déclaré : rapportée, hors enregistrement) ; MANQUANTE (déclarée par la
table, jamais jouée).

Oracles par étape : qa-explorer 1-10 côté API (1 ≥ 500 ; 2 4xx sauf `attendu` déclaré ; 5 objet créé
relisible ; 6 et 7 PDF `/proposal` du devis courant ; 9 société étrangère dans une réponse ; 10
`audit_coherence` sur les objets touchés, NA pour une variante ; 3, 4, 8 = navigateur : NA) + 3 oracles
de parcours : `auto` (une étape automatique a changé son modèle de persistance), `checkpoint` (PATCH des
valeurs fournies, relues en base), `aval` (refus_409 : la même requête rejouée est refusée en 4xx — refus
CORRECT d'une action non répétable ; recalcul / ecrase / reference : le modèle a changé).

--donnees = {"<étape>": {"corps": {…}, "pk": …, "source": "f.py::V.m", "checkpoint": {…}, "repeter": false,
"attendu": 404, "motif": "…", "avant": "<étape>", "non_jouable": "<motif>"}, "_utilisateur": "<username>"} ;
dans un corps : `@Modele` (pk courant), `@Modele.chemin[cond].x`, `@aujourdhui`,
{"@liste": ref, "si": champ, "champs": {clé: champ}}. Exemple : docs/audits/parcours/PA4.donnees.json.

Écrit un enregistrement d'acceptation par groupe (format AMET88, validé par
`check_acceptation.lire_enregistrement`) avec `couvre:` = `taches[]` des étapes jouées (+ `--couvre`).
Jamais contre la prod : conteneur local seulement, et le moteur refuse des réglages `*prod*`.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import inspect
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_acceptation  # noqa: E402
import check_parcours  # noqa: E402
import sonde  # noqa: E402

ROOT = check_parcours.ROOT
MARQUE = '@@PARCOURS '
CODES = {'PASS': 'P', 'FAIL': 'F', 'NA': 'N'}
NOMS = {'P': 'PASS', 'F': 'FAIL', 'N': 'NA'}
AUTO = ('evenement', 'beat', 'signal', 'tache')


class _Moteur:
    """Exécuté DANS le conteneur : sa source est expédiée par `sonde.py` (jamais importé côté hôte)."""

    def __init__(self, etapes, enreg, modele, donnees):
        from django.apps import apps
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from django.urls import get_resolver
        from rest_framework.test import APIClient
        if 'prod' in os.environ.get('DJANGO_SETTINGS_MODULE', '') + str(getattr(settings, 'SETTINGS_MODULE', '')):
            raise RuntimeError('rejouer_parcours refusé : réglages de production')
        self.apps, self.etapes, self.donnees = apps, etapes, donnees
        self.routes, self.objets, self.sorties, self.instantane = [], {}, [], {}
        self._parcourir(get_resolver().url_patterns, '')
        racine = apps.get_model(modele) if modele else next(
            (self.modele_vue(r[2]) for e in etapes for r in [self.route_de(e.get('fonction_entree'))] if r), None)
        obj = racine._default_manager.get(pk=enreg)
        self.objets[racine._meta.label] = obj.pk
        utilisateurs = get_user_model().objects
        actifs = utilisateurs.filter(company_id=obj.company_id, is_active=True).order_by('-is_superuser', 'id')
        self.u = (utilisateurs.get(username=donnees['_utilisateur']) if donnees.get('_utilisateur') else actifs.first())
        self.client = APIClient(HTTP_HOST='localhost')
        self.client.force_authenticate(user=self.u)
        self.modeles = {self.modele_de((e.get('checkpoint') or {}).get('persistance')) for e in etapes} - {None}

    def _parcourir(self, motifs, pre):
        for m in motifs:
            if hasattr(m, 'url_patterns'):
                self._parcourir(m.url_patterns, pre + str(m.pattern))
            elif 'format' not in str(m.pattern):
                self.routes.append((pre + str(m.pattern), m.callback, getattr(m.callback, 'cls', None)))

    def modele_de(self, ref):
        fichier, _, sym = str(ref or '').partition('::')
        mod = fichier.replace('backend/django_core/', '')[:-3].replace('/', '.')
        cands = [m for m in self.apps.get_models() if m.__name__ == sym.split('.')[0]]
        return next((m for m in cands if m.__module__ == mod), cands[0] if len(cands) == 1 else None)

    @staticmethod
    def modele_vue(cls):
        qs, ser = getattr(cls, 'queryset', None), getattr(cls, 'serializer_class', None)
        return getattr(qs, 'model', None) or getattr(getattr(ser, 'Meta', None), 'model', None)

    @staticmethod
    def methodes(cb, cls):
        """[(verbe, fonction)] d'une route : actions d'un viewset, sinon méthodes HTTP (vue `@api_view` déballée)."""
        if getattr(cb, 'actions', None):
            return [(v, getattr(cls, a, None)) for v, a in cb.actions.items()]
        out = []
        for v in ('post', 'get', 'put', 'patch', 'delete'):
            f = getattr(cls, v, None)
            cellules = [c.cell_contents for c in getattr(f, '__closure__', None) or ()]
            out += [(v, next((c for c in cellules if inspect.isfunction(c)), f))] if f else []
        return out

    @staticmethod
    def appelle(f, nom):
        """`f` (ou une fonction imbriquée) nomme `nom` dans son CODE (appel, import, alias) — jamais une docstring.
        Lu sur `__code__.co_names`, sans source : `inspect.getsource` sur ~5 000 routes ne finit pas en conteneur."""
        try:
            pile = [getattr(inspect.unwrap(f), '__code__', None)]
        except ValueError:
            return False
        while pile:
            code = pile.pop()
            if code is not None and nom in code.co_names:
                return True
            pile += [k for k in getattr(code, 'co_consts', ()) if inspect.iscode(k)]
        return False

    def route_de(self, ref):
        """(motif, verbe, classe de vue) de la route qui joue `fichier::[Classe.]fonction`, ou None.

        `Classe.methode` : la vue dont le MRO porte la classe. Fonction nue : la vue qui porte une action de ce
        nom, ou dont une action l'APPELLE (une fonction de domaine n'a pas de route à elle) — à égalité, la vue
        dont le modèle a un objet courant, puis le plus de mots communs entre l'action et la fonction."""
        fichier, _, sym = str(ref or '').partition('::')
        if not fichier.endswith('.py') or not sym:
            return None
        classe, _, meth = sym.rpartition('.')
        meth = {'perform_create': 'create', 'perform_update': 'partial_update'}.get(meth, meth)
        cands = []
        for n, (motif, cb, cls) in enumerate(self.routes):
            if cls is None or (classe and classe not in {k.__name__ for k in cls.__mro__}):
                continue
            for verbe, f in self.methodes(cb, cls):
                nomf = getattr(f, '__name__', '')
                if classe and (getattr(cb, 'actions', None) or {}).get(verbe) == meth:
                    return motif, verbe, cls
                if not classe and f is not None and (nomf == meth or self.appelle(f, meth)):
                    Mv = self.modele_vue(cls)
                    cands.append((Mv is not None and Mv._meta.label in getattr(self, 'objets', {}), nomf == meth,
                                  len(set(nomf.split('_')) & set(meth.split('_'))), -n, (motif, verbe, cls)))
        return max(cands, key=lambda c: c[:4])[4] if cands else None

    def route_modele(self, M, action):
        return next((mo for mo, cb, cls in self.routes if cls and self.modele_vue(cls) is M
                     for a in (getattr(cb, 'actions', None) or {}).values() if a == action), None)

    def concret(self, motif, pk):
        """URL concrète : `pk`/`id` = objet courant de la vue ; `<x>_id` = objet courant du modèle `x`."""
        objets = getattr(self, 'objets', {})

        def valeur(m):
            nom = m.group(1) or m.group(2)
            base = re.sub(r'_(id|pk)$', '', nom).replace('_', '')
            v = pk if nom in ('pk', 'id') else next(
                (objets[k] for k in objets if k.rsplit('.', 1)[1].lower() == base), None)
            if v is None:
                raise LookupError(f'aucun objet courant pour `{nom}`')
            return str(v)
        return '/' + re.sub(r'[\^$\\?]', '', re.sub(r'\(\?P<(\w+)>[^)]*\)|<(?:\w+:)?(\w+)>', valeur, motif))

    def _attr(self, obj, chemin):
        """`a.b[c].d` : attribut / clé ; un gestionnaire lié devient sa liste ; `[c]` = 1er élément où `c` est vrai."""
        for seg in filter(None, chemin.split('.')):
            nom, _, cond = seg.rstrip(']').partition('[')
            obj = obj[int(nom)] if nom.isdigit() else obj[nom] if isinstance(obj, dict) else getattr(obj, nom)
            obj = list(obj.all()) if hasattr(obj, 'all') else obj
            obj = next(x for x in obj if self._attr(x, cond)) if cond else obj
        return obj

    def valeur(self, v):
        """Résout les références de --donnees sur les objets COURANTS du rejeu (jamais un pk figé) :
        `@Modele` (pk), `@Modele.chemin`, `@aujourdhui`, {"@liste": ref, "si": champ, "champs": {clé: champ}}."""
        if isinstance(v, dict) and '@liste' in v:
            return [{k: self.valeur_json(self._attr(x, c)) for k, c in v.get('champs', {}).items()}
                    for x in self.valeur(v['@liste']) if not v.get('si') or self._attr(x, v['si'])]
        if isinstance(v, (dict, list)):
            return {k: self.valeur(x) for k, x in v.items()} if isinstance(v, dict) else [self.valeur(x) for x in v]
        if not (isinstance(v, str) and v.startswith('@')):
            return v
        if v == '@aujourdhui':
            return datetime.date.today().isoformat()
        nom, _, chemin = v[1:].partition('.')
        label = next((k for k in self.objets if k.rsplit('.', 1)[1] == nom), None)
        if label is None:
            raise LookupError(f'{v} : aucun objet courant {nom}')
        obj = self.apps.get_model(label)._default_manager.get(pk=self.objets[label])
        return self.valeur_json(self._attr(obj, chemin)) if chemin else self.objets[label]

    @staticmethod
    def valeur_json(x):
        if x is None or isinstance(x, (list, dict, bool, int, float, str)):
            return x
        return x.isoformat() if hasattr(x, 'isoformat') else getattr(x, 'pk', None) or str(x)

    def appeler(self, verbe, url, corps=None):
        r = (getattr(self.client, verbe)(url, corps or {}, format='json') if verbe in ('post', 'put', 'patch')
             else getattr(self.client, verbe)(url))
        self.sorties.append(getattr(r, 'data', None))
        return r

    def etat(self, M):
        if M is None:
            return None
        qs, cur = M._default_manager.all(), self.objets.get(M._meta.label)
        obj = qs.filter(pk=cur).first() if cur is not None else None
        from django.forms.models import model_to_dict
        return qs.count(), qs.order_by('-pk').values_list('pk', flat=True).first(), \
            repr(model_to_dict(obj)) if obj else None

    def etrangere(self, x):
        if isinstance(x, dict):
            return any((k in ('company', 'company_id') and isinstance(v, int) and v != self.u.company_id)
                       or self.etrangere(v) for k, v in x.items())
        return isinstance(x, list) and any(self.etrangere(v) for v in x)

    def declencher(self, e, d, s):
        """Joue le déclencheur ; remplit `s` ; renvoie le motif d'une étape NON JOUÉE (ou NON_JOUABLE_API)."""
        dec = e.get('declencheur') or {}
        s['auto'] = s['auto'] and not d.get('source')  # geste manuel équivalent déclaré par --donnees
        refs = (d.get('source'), e.get('fonction_entree'), dec.get('source'))
        s['route'] = route = next((r for r in map(self.route_de, refs) if r), None)
        if route:
            motif, verbe, cls = route
            Mv = self.modele_vue(cls)
            s['pk'] = d.get('pk', self.objets.get(Mv._meta.label) if Mv else None)
            try:
                s['url'], s['corps'] = self.concret(motif, s['pk']), self.valeur(d.get('corps') or {})
            except (LookupError, AttributeError, StopIteration, ValueError) as exc:
                return f'{verbe.upper()} {motif} : {exc}'
            self.instantane = {m: self.etat(m) for m in self.modeles}  # un effet auto se compare à AVANT l'appel
            s['reps'].append(self.appeler(verbe, s['url'], s['corps']))
            s['trace'].append(f"{verbe.upper()} {s['url']} -> {s['reps'][0].status_code}")
            if Mv:
                s['vus'].add((Mv._meta.model_name, str(self.objets.get(Mv._meta.label))))
            return None
        if dec.get('type') not in ('beat', 'tache'):
            return None if dec.get('type') in AUTO else (
                f"NON_JOUABLE_API : aucune vue n'expose ni n'appelle {e.get('fonction_entree')} "
                f"(déclencheur {dec.get('type')} {dec.get('source')})")
        fichier, _, sym = str(e.get('fonction_entree') or '').partition('::')
        fn = __import__(fichier.replace('backend/django_core/', '')[:-3].replace('/', '.'), fromlist=['x'])
        for part in sym.split('.'):
            fn = getattr(fn, part)
        if any(p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
               for p in inspect.signature(fn).parameters.values()):
            return (f'{sym} (tâche planifiée {dec.get("source")}) exige des arguments : passer --donnees '
                    f'{{"{e["id"]}": {{"source": "<vue.py>::<Classe.action>"}}}} pour jouer le geste manuel équivalent')
        self.instantane = {m: self.etat(m) for m in self.modeles}
        fn()
        s['trace'].append(f'appel {sym}()')
        return None

    def oracles_parcours(self, e, d, s, M, avant, apres):
        """auto / checkpoint / aval. `refus_409` : la MÊME requête rejouée doit être refusée (4xx) — refus
        correct d'une action non répétable, jamais compté par l'oracle 2 (geste négatif délibéré, qa-explorer
        2) ; `"repeter": false` pour une étape légitimement répétable (tranche suivante, paiement partiel)."""
        cp, par, reps = e.get('checkpoint') or {}, s['par'], s['reps']
        par['auto'] = ('PASS' if apres != avant else 'FAIL') if s['auto'] else 'NA'
        valeurs, cle = d.get('checkpoint'), self.objets.get(getattr(getattr(M, '_meta', None), 'label', None))
        if cp.get('modifiable') and valeurs and M is not None and cle is not None:
            ecriture = self.route_modele(M, 'partial_update')
            r = self.appeler('patch', self.concret(ecriture, cle), valeurs) if ecriture else None
            relu = M._default_manager.filter(pk=cle).values(*valeurs).first() or {}
            par['checkpoint'] = 'PASS' if r is not None and r.status_code < 300 and all(
                str(relu.get(k)) == str(v) for k, v in valeurs.items()) else 'FAIL'
            s['trace'].append(f'PATCH checkpoint -> {getattr(r, "status_code", "sans route")}')
        types = {x.get('type') if isinstance(x, dict) else x for x in e.get('regle_aval') or []}
        if (d.get('attendu') or 0) >= 400:  # refus déclaré : il ne doit RIEN avoir écrit
            par['aval'] = 'PASS' if apres == avant else 'FAIL'
        elif 'refus_409' in types and reps and reps[0].status_code < 300 and d.get('repeter', True):
            r2 = self.appeler(s['route'][1], s['url'], s['corps'])
            par['aval'] = 'PASS' if 400 <= r2.status_code < 500 and r2.status_code != 401 else 'FAIL'
            s['trace'].append(f'rejouée -> {r2.status_code} (refus attendu)')
        elif types & {'recalcul', 'ecrase', 'reference'} and (reps or s['auto']):
            par['aval'] = 'PASS' if apres != avant else 'FAIL'

    def oracles_pdf(self, s):
        devis, o = self.objets.get('ventes.Devis'), s['o']
        if not devis or not any(n == 'devis' for n, _ in s['vus']):
            return
        pdf = self.client.get(f'/api/django/ventes/devis/{devis}/proposal/')  # seul chemin PDF client (règle 4)
        corps = b''.join(pdf.streaming_content) if getattr(pdf, 'streaming', False) else pdf.content
        ok = pdf.status_code == 200 and corps[:5] == b'%PDF-' and len(corps) >= 10000
        o['6'] = 'PASS' if ok else 'FAIL'
        with contextlib.suppress(ImportError):
            import fitz
            texte = ''.join(p.get_text() for p in fitz.open(stream=corps, filetype='pdf')) if ok else ''
            o['7'] = 'FAIL' if re.search(r"prix d'achat|prix_achat|coût d'achat|\bmarge\b", texte, re.I) else 'PASS'

    @staticmethod
    def sans_corps(e, r):
        data = getattr(r, 'data', None)
        dit = data.get('detail', ', '.join(map(str, data))) if isinstance(data, dict) else data
        return {'id': e['id'], 'verdict': 'NON_JOUEE', 'trace': (
            f'400 sans corps fourni (entrée requise ou refus) : « {str(dit)[:120]} » — passer --donnees '
            f'{{"{e["id"]}": {{"corps": {{…}}}}}} (exemple : docs/audits/parcours/PA4.donnees.json)')}

    def lire_cree(self, s, M, avant, apres):
        """Oracle 5 : l'objet CRÉÉ par un POST (nouvelle ligne du modèle de persistance) est relisible."""
        if s['reps'] and s['route'][1] == 'post' and s['reps'][0].status_code < 300 and apres[0] > avant[0]:
            lecture = self.route_modele(M, 'retrieve')
            if lecture:
                ok = self.appeler('get', self.concret(lecture, apres[1])).status_code == 200
                s['o']['5'] = 'PASS' if ok else 'FAIL'

    def etape(self, e):
        d = self.donnees.get(e['id'], {})
        s = {'o': {str(i): 'NA' for i in range(1, 11)}, 'par': {'auto': 'NA', 'checkpoint': 'NA', 'aval': 'NA'},
             'trace': [], 'vus': set(), 'reps': [], 'pk': None, 'url': None, 'corps': None,
             'auto': (e.get('declencheur') or {}).get('type') in AUTO}
        M = self.modele_de((e.get('checkpoint') or {}).get('persistance'))
        self.sorties.clear()
        avant = self.etat(M)
        motif = (f"NON_JOUABLE_API : déclarée par --donnees ({d['non_jouable']})" if d.get('non_jouable')
                 else self.declencher(e, d, s))
        if motif:
            return {'id': e['id'], 'trace': motif,
                    'verdict': 'NON_JOUABLE_API' if motif.startswith('NON_JOUABLE_API') else 'NON_JOUEE'}
        attendu = d.get('attendu')
        if s['reps'] and s['reps'][0].status_code == 400 and not d.get('corps') and attendu != 400:
            return self.sans_corps(e, s['reps'][0])
        if s['auto'] and not s['route'] and M in self.instantane:
            avant = self.instantane[M]
        apres = self.etat(M)
        if M is not None and apres and avant and apres[1] != avant[1]:
            self.objets[M._meta.label] = apres[1]  # l'objet créé appartient au modèle de PERSISTANCE de l'étape
            self.lire_cree(s, M, avant, apres)
        if M is not None:
            s['vus'].add((M._meta.model_name, str(self.objets.get(M._meta.label))))
        if s['reps']:
            s['o']['1'] = 'FAIL' if any(r.status_code >= 500 for r in s['reps']) else 'PASS'
            s['o']['2'] = 'FAIL' if any(400 <= r.status_code < 500 for r in s['reps']) else 'PASS'
            if attendu is not None:  # refus déclaré (qa-explorer 2 : 4xx voulu) — tout autre code échoue
                s['o']['2'] = 'PASS' if s['reps'][0].status_code == attendu else 'FAIL'
                s['trace'].append(f'{attendu} attendu (--donnees : {d.get("motif", "refus déclaré")})')
        self.oracles_parcours(e, d, s, M, avant, apres)
        self.oracles_pdf(s)
        s['o']['9'] = ('FAIL' if any(map(self.etrangere, self.sorties)) else 'PASS') if self.sorties else 'NA'
        return {'id': e['id'], 'trace': ' ; '.join(s['trace'])[:200], 'o': s['o'], 'par': s['par'], 'vus': s['vus']}

    def ordre(self):
        """[(étape, variante)] : la chaîne `suite` depuis la 1re étape ; une étape hors chaîne est une VARIANTE
        jouée juste avant son ancre (`avant` de --donnees, sinon l'étape de la chaîne de même `suite`, sinon sa
        `suite`) puis ANNULÉE (point de sauvegarde) — deux portes alternatives ne se jouent jamais l'une après
        l'autre sur le même dossier ; sans ancre, elle se joue à sa place dans la table."""
        par_id, chaine = {e['id']: e for e in self.etapes}, []
        cur = self.etapes[0]['id'] if self.etapes else None
        while isinstance(cur, str) and cur in par_id and cur not in chaine:
            chaine.append(cur)
            cur = par_id[cur].get('suite')

        def ancre(e):
            a, suite = (self.donnees.get(e['id']) or {}).get('avant'), e.get('suite')
            return a if a in chaine else next((c for c in chaine if par_id[c].get('suite') == suite),
                                              suite if isinstance(suite, str) and suite in chaine else None)
        ancres = {e['id']: ancre(e) for e in self.etapes if e['id'] not in chaine}
        out = []
        for e in self.etapes:
            if e['id'] in chaine:
                out += [(par_id[v], True) for v, a in ancres.items() if a == e['id']] + [(e, False)]
            elif ancres[e['id']] is None:
                out.append((e, False))
        return out

    def variante(self, e):
        from django.db import transaction
        point, objets = transaction.savepoint(), dict(self.objets)
        try:
            res = self.etape(e)
        finally:
            transaction.savepoint_rollback(point)
            self.objets = objets
        res['trace'], res['variante'] = 'variante annulée : ' + res['trace'], True
        return res

    def jouer(self):
        from django.core.management import call_command
        resultats = [self.variante(e) if v else self.etape(e) for e, v in self.ordre()]
        try:
            tampon = io.StringIO()
            call_command('audit_coherence', '--json', '--no-persist', stdout=tampon)
            violations = [(str(v.get('object_type', '')).lower(), str(v.get('object_id')))
                          for v in json.loads(tampon.getvalue()).get('violations', [])]
        except Exception:  # commande absente ou en erreur : oracle 10 laissé NA
            violations = None
        for res in (r for r in resultats if 'o' in r):
            vus = res.pop('vus')
            if violations is not None and not res.get('variante'):  # une variante annulée n'a plus d'objets
                res['o']['10'] = 'FAIL' if any(n in t and i == c for n, c in vus for t, i in violations) else 'PASS'
            res['verdict'] = 'FAIL' if 'FAIL' in [*res['o'].values(), *res['par'].values()] else 'PASS'
            res['o'] = ''.join(CODES[res['o'][str(i)]] for i in range(1, 11))
            res['par'] = ''.join(CODES[res['par'][k]] for k in ('auto', 'checkpoint', 'aval'))
        return {'etapes': resultats}


def partager(table: dict) -> tuple:
    """(étapes jouables, étapes déclarées manquantes — jamais jouées)."""
    etapes = table.get('etapes') or []
    return ([e for e in etapes if not check_parcours.est_manquante(e)],
            [e for e in etapes if check_parcours.est_manquante(e)])


def source_sonde(table, jouables, enreg, modele, donnees, sha='local') -> str:
    pa = table.get('parcours') or table.get('id') or 'PA'
    entete = {'constat': f'parcours {pa}', 'sha': sha, 'attendu': 'chaque étape jouée PASS (oracles 1-10 + parcours)'}
    return (f'SONDE = {entete!r}\nimport contextlib, datetime, inspect, io, json, os, re\n'
            f'CODES = {CODES!r}\nAUTO = {AUTO!r}\n'
            f'TABLE_ETAPES = json.loads({ascii(json.dumps(jouables))})\n'
            f'DONNEES = json.loads({ascii(json.dumps(donnees))})\n\n\n'
            + inspect.getsource(_Moteur) + '\n\ndef sonde(ctx):\n'
            '    with contextlib.redirect_stdout(io.StringIO()):\n'
            f'        res = _Moteur(TABLE_ETAPES, {enreg!r}, {modele!r}, DONNEES).jouer()\n'
            f'    return {MARQUE!r} + json.dumps(res, default=str)\n')


def _ecrire(dossier: Path, nom: str, sha, groupe, etapes, commande, hors='') -> Path:
    """Enregistrement AMET88 : `<nom>.md` (en-tête YAML) + `<nom>.results.json` (fait foi)."""
    couvre = sorted({t for e in etapes for t in e['taches']}, key=check_acceptation._cle)
    verdict = 'PASS' if all(e['verdict'] == 'PASS' for e in etapes) else 'FAIL'
    res = {'sha': sha, 'date': nom[:10], 'groupe': groupe, 'verdict': verdict, 'couvre': couvre,
           'couvre_avec_ecart': [], 'etapes': etapes}
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f'{nom}.results.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    tete = ''.join(f"  - id: {e['id']}\n    tache: [{', '.join(e['taches'])}]\n    verdict: {e['verdict']}\n"
                   for e in etapes)
    lignes = ''.join(f"| {e['id']} | {', '.join(e['taches'])} | {e['verdict']} | {e['trace']} |\n" for e in etapes)
    md = dossier / f'{nom}.md'
    md.write_text(f"---\nsha: {sha}\ndate: {nom[:10]}\ngroupe: {groupe}\ncouvre: [{', '.join(couvre)}]\n"
                  f"couvre_avec_ecart: []\nverdict: {verdict}\netapes:\n{tete}---\n\n"
                  f"Rejeu `{commande}` (pile locale, transaction annulée). Oracles 1-10 et oracles de parcours "
                  f"(auto, checkpoint, aval) : results.json.\n\n| Étape | Tâches | Verdict | Trace |\n"
                  f"|---|---|---|---|\n{lignes}{hors}", 'utf-8')
    return md


def _lire_resultats(rc, sortie: str, erreur: str) -> dict | None:
    ligne = next((x for x in sortie.splitlines() if x.startswith(sonde.MARQUE)), None)
    res = json.loads(ligne[len(sonde.MARQUE):]) if ligne else {}
    observe = res.get('observe', '')
    if MARQUE in observe and res.get('base_inchangee') is True:
        return {r['id']: r for r in json.loads(observe.split(MARQUE, 1)[1])['etapes']}
    print(f'ÉCHEC du rejeu (code {rc}, base inchangée : {res.get("base_inchangee")}) : '
          f'{(observe or erreur or sortie).strip()[-600:]}')
    return None


def _par_groupe(joues: dict, jouables: list, couvre=()) -> dict:
    """{groupe: {étape: [tâches]}} — une tâche dont une étape n'a pas été jouée (NON_JOUEE) n'est pas couverte ;
    une étape NON_JOUABLE_API (route absente, déclarée hors API) n'entre pas dans l'enregistrement. `couvre` :
    ids ajoutés à CHAQUE étape (acceptation de l'outil lui-même : `--couvre AMET98`)."""
    taches_de = {e['id']: [*(e.get('taches') or []), *couvre] for e in jouables}
    incompletes = {t for i, r in joues.items() if r['verdict'] == 'NON_JOUEE' for t in taches_de[i]}
    for t in sorted(incompletes):
        print(f"{t} : non couverte (une de ses étapes n'a pas été jouée)")
    groupes: dict = {}
    for ident, r in joues.items():
        for t in (sorted(set(taches_de[ident]) - incompletes) if r['verdict'] in ('PASS', 'FAIL') else []):
            groupes.setdefault(check_acceptation.groupe_de(t), {}).setdefault(ident, []).append(t)
    return groupes


def _enregistrer(groupes, joues, racine, nom, sha, commande) -> int:
    code = 0
    for groupe, par_etape in sorted(groupes.items()):
        dossier = racine / check_acceptation.DOSSIER / groupe
        if (dossier / f'{nom}.md').exists():
            print(f'ÉCHEC : {dossier / nom}.md existe déjà — rien écrasé')
            code = 1
            continue
        etapes = [{'id': i, 'taches': ts, 'verdict': joues[i]['verdict'], 'base_verdict': None,
                   'trace': f"{commande} : {joues[i]['trace'] or 'automatique'}",
                   'oracles': {str(k + 1): NOMS[c] for k, c in enumerate(joues[i]['o'])},
                   'parcours': {k: NOMS[c] for k, c in zip(('auto', 'checkpoint', 'aval'), joues[i]['par'])}}
                  for i, ts in par_etape.items()]
        hors = ''.join(f"\nNon jouée — {i} : {r['verdict']} — {r.get('trace', '')}\n"
                       for i, r in joues.items() if r['verdict'] not in ('PASS', 'FAIL'))
        md = _ecrire(dossier, nom, sha, groupe, etapes, commande, hors)
        erreurs: list = []
        couverts = check_acceptation.lire_enregistrement(md, erreurs)
        print(f"enregistrement {md.relative_to(racine).as_posix()} : couvre {sorted(couverts or [])}"
              + (f' — NON CONFORME : {erreurs}' if erreurs else ''))
        code |= bool(erreurs)
    if not groupes:
        print('aucune tâche couverte (taches[] vides ou étapes non jouées) : aucun enregistrement écrit')
    return code


def rejouer(table, pa, enreg, *, executer=sonde.executer_docker, racine=ROOT, sha=None, date=None,
            modele=None, donnees=None, conteneur=sonde.CONTENEUR, timeout=2400, dry_run=False, couvre=()) -> int:
    jouables, manquantes = partager(table)
    for e in manquantes:
        print(f"{e['id']} : MANQUANTE — non jouée ({e.get('raison', '')})")
    sha = sha or subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=racine).stdout.strip()
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(source_sonde(table, jouables, enreg, modele, donnees or {}, sha[:9] or 'local'))
    try:
        programme = sonde.programme(*sonde.charger(f.name), timeout)
    finally:
        os.unlink(f.name)
    if dry_run:
        print(programme)
        return 0
    cmd = ['docker', 'exec', '-i', conteneur, 'python', '-u', 'manage.py', 'shell']
    joues = _lire_resultats(*executer(cmd, programme, timeout))
    if joues is None:
        return 1
    for ident, r in joues.items():
        print(f"{ident} : {r['verdict']} — {r.get('trace', '')}"
              + (f" ; oracles 1-10 {r['o']} ; parcours auto/checkpoint/aval {r['par']}" if 'o' in r else ''))
    nom = f"{date or datetime.date.today().isoformat()}-{sha[:9]}"
    code = _enregistrer(_par_groupe(joues, jouables, couvre), joues, racine, nom, sha,
                        f'rejouer_parcours.py {pa} --enregistrement {enreg}')
    return 1 if code or any(r['verdict'] not in ('PASS', 'NON_JOUABLE_API') for r in joues.values()) else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('parcours', help='PA1 … PA7')
    p.add_argument('--enregistrement', required=True, help="pk de l'enregistrement de départ")
    p.add_argument('--modele', help='app.Modele de cet enregistrement (défaut : vue de la 1re étape)')
    p.add_argument('--donnees', help='JSON des corps / pk / valeurs de checkpoint par étape')
    p.add_argument('--conteneur', default=sonde.CONTENEUR)
    p.add_argument('--timeout', type=int, default=2400, help='secondes (Django démarre lentement sur Windows)')
    p.add_argument('--couvre', default='', help="ids ajoutés à chaque étape jouée (ex. AMET98 : l'outil lui-même)")
    p.add_argument('--dry-run', action='store_true', help='imprime le programme, sans docker')
    a = p.parse_args(argv)
    if 'prod' in a.conteneur.lower() or os.environ.get('DOCKER_HOST', '').startswith(('ssh://', 'tcp://')):
        p.error('jamais contre la prod : conteneur local seulement (DOCKER_HOST distant refusé)')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    tables = {(check_parcours.P.charger_table(c).get('parcours') or c.stem): c for c in check_parcours.tables()}
    if a.parcours not in tables:
        p.error(f'table {a.parcours} introuvable (connues : {", ".join(sorted(tables))})')
    donnees = json.loads(Path(a.donnees).read_text(encoding='utf-8')) if a.donnees else {}
    return rejouer(check_parcours.P.charger_table(tables[a.parcours]), a.parcours, a.enregistrement,
                   modele=a.modele, donnees=donnees, conteneur=a.conteneur, timeout=a.timeout, dry_run=a.dry_run,
                   couvre=[c for c in re.split(r'[,\s]+', a.couvre) if c])


if __name__ == '__main__':
    sys.exit(main())
