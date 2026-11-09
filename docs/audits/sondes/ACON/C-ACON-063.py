# flake8: noqa  (sonde de MESURE d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""T5 — temps de rendu SYNCHRONE des livrables d'un gros calepinage (gunicorn `--timeout 120`) : layouts
synthétiques de 120 / 600 / 2 000 modules (1 pan, 1 pan, 4 pans × 500 — admis par la décision du 23/10).
Chronométré, rendus WeasyPrint RÉELS (`core.pdf.render_pdf`) :
  * composition pure : `geometrie_de_planche` + `svg_de_planche`, `octets_dxf` (ce que borne test_cal224_perf) ;
  * pack technique : chaque rendu de `pack_technique._rendus` passé à `_rendre_pieces` (mêmes refus/signalements),
    puis `_fusionner_localement` (PyMuPDF) — SANS le dépôt GED/MinIO (exclu : objets orphelins hors transaction) ;
  * dossier 82-21 : `reglementaire._rendus_du_module` (planche, note de calcul, schéma unifilaire) par
    `_rendre_pieces_produites` — sans le remplissage du gabarit (champs, peu coûteux).
SIMULÉ : le résultat servi (`rapport.resultat_du_rapport` patché → l'échantillon `contract_samples/
calepinage_resultat.json`, NON mis à l'échelle de N) pour que note / rapports se rendent ; seules les pièces qui
lisent la GÉOMÉTRIE (planche, plans, DXF) varient avec N. Transaction annulée. Aucun refus attendu : verdict = tableau."""
SONDE = {"constat": "C-ACON-063", "sha": "819fe0f8c",
         "attendu": "mesure : secondes par pièce et totaux pack / dossier à N = 120, 600, 2000 ; repro si un total dépasse 60 s à 2000",
         "modeles": ["calepinage.Calepinage"]}


def sonde(ctx):
    import json
    import math
    import pathlib
    import time
    from unittest import mock
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage
    import apps.calepinage.services.rapport as rapport_mod
    from apps.calepinage.services import pack_technique as pt
    from apps.calepinage.services import reglementaire as rg
    from apps.calepinage.services.planche import geometrie_de_planche, svg_de_planche
    from apps.calepinage.services.export_dxf import octets_dxf
    from apps.ventes.services import layout_hash

    racine = pathlib.Path(pt.__file__).resolve().parents[1]
    echantillon = json.loads((racine / 'contract_samples' / 'calepinage_resultat.json')
                             .read_text(encoding='utf-8'))['exemple']
    co = Company.objects.create(nom='Sonde ACON 063', slug='sonde-acon-063')
    lead = Lead.objects.create(company=co, nom='Usine', prenom='T5', gps_lat=33.5, gps_lng=-7.6)
    LAT0, LNG0 = 33.5, -7.6
    M_LAT = 111320.0
    M_LNG = 111320.0 * math.cos(math.radians(LAT0))

    def deg(x, y):  # mètres (est, nord) → [lng, lat]
        return [LNG0 + x / M_LNG, LAT0 + y / M_LAT]

    def layout(n_pans, par_pan):
        cols = 25
        rows = math.ceil(par_pan / cols)
        larg, haut = cols * 1.15 + 2.0, rows * 2.30 + 2.0
        zones, x0 = [], 0.0
        for p in range(n_pans):
            panels = [{'cx': 1.0 + (i % cols) * 1.15 + 0.575, 'cy': 1.0 + (i // cols) * 2.30 + 1.15}
                      for i in range(par_pan)]
            verts = [deg(x0, 0), deg(x0 + larg, 0), deg(x0 + larg, haut), deg(x0, haut)]
            zones.append({'id': f'z{p + 1}', 'label': f'Pan {p + 1}', 'vertices': verts,
                          'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 10.0, 'count': par_pan,
                                       'origin': deg(x0, 0), 'panels': panels}})
            x0 += larg + 5.0
        lat_max = LAT0 + (haut + 1) / M_LAT
        lng_max = LNG0 + (x0 + 1) / M_LNG
        outline = [[LAT0 - 1 / M_LAT, LNG0 - 1 / M_LNG], [LAT0 - 1 / M_LAT, lng_max],
                   [lat_max, lng_max], [lat_max, LNG0 - 1 / M_LNG]]
        return {'version': 2, 'panelWatt': 550, 'scenario': 'reseau', 'pin': {'lat': LAT0, 'lng': LNG0},
                'outline': outline, 'zones': zones,
                'result': {'panels': n_pans * par_pan, 'kwc': round(n_pans * par_pan * 0.55, 2)}}

    def chrono(fn):
        t = time.perf_counter()
        try:
            out = fn()
            return round(time.perf_counter() - t, 3), out, None
        except Exception as exc:  # noqa
            return round(time.perf_counter() - t, 3), None, f'{type(exc).__name__}: {exc}'[:140]

    def minute(rendus, journal):
        def enveloppe(code, fn):
            def f():
                t = time.perf_counter()
                try:
                    return fn()
                finally:
                    journal[code] = round(time.perf_counter() - t, 3)
            return f
        return {code: enveloppe(code, fn) for code, fn in rendus.items()}

    tableau = {}
    budget_debut = time.perf_counter()
    with mock.patch.object(rapport_mod, 'resultat_du_rapport', side_effect=lambda c: (echantillon, echantillon)):
        for n, (n_pans, par_pan) in ((120, (1, 120)), (600, (1, 600)), (2000, (4, 500))):
            L = layout(n_pans, par_pan)
            c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre=f'T5 {n}', roof_layout=L,
                                          layout_hash=layout_hash(L), resultat=echantillon)
            ligne = {'modules': sum(z['geometry']['count'] for z in L['zones'])}
            t, geo, err = chrono(lambda: geometrie_de_planche(L))
            ligne['geometrie_s'] = t
            if geo is not None:
                ligne['svg_planche_s'], svg, e2 = chrono(lambda: svg_de_planche(geo, titre='T5', pied='T5'))
                ligne['svg_ko'] = len(svg) // 1024 if svg else e2
                ligne['dxf_s'], _x, e3 = chrono(lambda: octets_dxf(geo))
            else:
                ligne['geometrie_err'] = err
            # pack technique (8 rendus réels + fusion)
            journal = {}
            t, res, err = chrono(lambda: pt._rendre_pieces(c, company=co, rendus=minute(pt._rendus(c, co), journal)))
            ligne['pack_rendus_s'] = t
            ligne['pack_par_piece_s'] = journal
            if res is not None:
                pieces, signalements = res
                ligne['pack_pieces_rendues'] = [p[0] for p in pieces]
                ligne['pack_pages'] = sum((p[3] or 0) for p in pieces)
                ligne['pack_signalements'] = [str(s)[:90] for s in signalements]
                tf, fus, ef = chrono(lambda: pt._fusionner_localement(pieces, pt.PackRefuse))
                ligne['pack_fusion_s'] = tf
                ligne['pack_total_s'] = round(t + tf, 3)
            else:
                ligne['pack_err'] = err
            # dossier 82-21 (rendus du module)
            journal2 = {}
            t2, res2, err2 = chrono(lambda: rg._rendre_pieces_produites(minute(rg._rendus_du_module(c, co), journal2)))
            ligne['dossier_rendus_s'] = t2
            ligne['dossier_par_piece_s'] = journal2
            if res2 is not None:
                ligne['dossier_pieces'] = [p[0] for p in res2[0]]
                ligne['dossier_signalements'] = [str(s)[:90] for s in res2[1]]
            else:
                ligne['dossier_err'] = err2
            tableau[n] = ligne
            print(n, json.dumps(ligne, default=str, ensure_ascii=False)[:1500])
            if time.perf_counter() - budget_debut > 700:
                tableau['arret'] = f'budget sonde dépassé après N={n}'
                break
    gros = tableau.get(2000) or {}
    obs = {'tableau': tableau,
           'seuil_gunicorn_s': 120,
           'pack_2000_s': gros.get('pack_total_s'), 'dossier_2000_s': gros.get('dossier_rendus_s')}
    obs['repro'] = bool((gros.get('pack_total_s') or 0) > 60 or (gros.get('dossier_rendus_s') or 0) > 60)
    print(json.dumps(obs, default=str, ensure_ascii=False)[:6000])
    return obs
