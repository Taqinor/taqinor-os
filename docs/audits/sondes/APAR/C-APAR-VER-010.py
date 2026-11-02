SONDE = {"constat": "C-APAR-VER-010", "sha": "56d5b623a",
         "attendu": "APAR79 rejoué de bout en bout : société à tva_standard 14 %, devis à taux_tva 14, onduleurs sans Produit.tva : les prix des cartes Éco/Max servies (offres_tailles.deriver, même dérivation que GET offres-tailles et la page client) sont IDENTIQUES à ceux obtenus avec les onduleurs à Produit.tva=14 explicite, et DIFFÉRENTS de ceux à Produit.tva=20 (témoin)"}


def _prix(bloc):
    out = []

    def walk(x, chemin=''):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ('prix_ttc', 'cout_ttc', 'prix_ht') and isinstance(v, (int, float)):
                    out.append((chemin + '.' + k, round(float(v), 2)))
                else:
                    walk(v, chemin + '.' + str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, chemin + '[%d]' % i)
    walk(bloc)
    return sorted(out)


def sonde(ctx):
    from decimal import Decimal
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes import offres_tailles as ot
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.utils import company_settings as cs

    def rendre(devis):
        devis = Devis.objects.get(pk=devis.pk)
        if hasattr(cs, '_MEMO'):
            try:
                cs._MEMO.clear()
            except Exception:
                pass
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        return ot.deriver(devis, data)

    essais = 0
    qs = Devis.objects.filter(mode_installation='residentiel', lignes__designation__icontains='onduleur', lead__isnull=False).exclude(etude_params__isnull=True).distinct().order_by('-id')
    for devis in qs[:6]:
        essais += 1
        try:
            bloc = rendre(devis)
        except Exception:
            continue
        if not bloc or not _prix(bloc):
            continue
        co = devis.company
        prof = CompanyProfile.get(company=co)
        CompanyProfile.objects.filter(pk=prof.pk).update(tva_standard=Decimal('14'))
        Devis.objects.filter(pk=devis.pk).update(taux_tva=Decimal('14'))
        onduleurs = Produit.objects.filter(company=co, nom__icontains='onduleur')
        onduleurs.update(tva=None)
        a = _prix(rendre(devis))
        onduleurs.update(tva=Decimal('14'))
        b = _prix(rendre(devis))
        onduleurs.update(tva=Decimal('20'))
        c = _prix(rendre(devis))
        print(f'devis {devis.reference} (société {co.pk}, {onduleurs.count()} onduleurs) ; '
              f'cartes sans Produit.tva={a[:4]} ; tva=14 explicite={b[:4]} ; témoin tva=20={c[:4]} ; '
              f'A==B : {a == b} ; B!=C (témoin sensible) : {b != c}')
        return {'repro': a != b, 'a_egal_b': a == b, 'temoin_sensible': b != c, 'devis': devis.reference}
    print(f'aucun devis résidentiel dérivable parmi {essais} essais')
    return {'repro': False, 'derivable': False}
