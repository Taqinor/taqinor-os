# CPDF — la recette de rendu du guide §4 ne rend PAS le PDF C&I (27/10)

`generate_premium_pdf(build_quote_data(devis, opts), chemin)` = le moteur LEGACY (gabarit résidentiel premium :
« Pourquoi choisir… », « NOS HYPOTHÈSES » avec 60 %/96 % figés, « NOTRE ENGAGEMENT »). Un devis commercial /
industriel n'est JAMAIS servi par ce chemin en vrai (AMOT79) : `/proposal` passe par
`builder.generate_premium_devis_pdf` → `registre_renderers()` → `commercial.renderer` / `industriel.renderer`.
Plusieurs constats CORC/CEC « page 3 » (60 %/96 %, NOTRE ENGAGEMENT par-dessus BON POUR ACCORD, « approximatif ») viennent
probablement de ce faux chemin — à re-vérifier sur le vrai rendu.

Rendu fidèle, sans MinIO (recopie du dispatch) :

```python
from apps.ventes.quote_engine import builder as B
def rendre(d, opts, chemin):
    o = dict(opts); o['_embed_roof_render'] = True; o['_embed_calepinage_planche'] = True
    data = B.build_quote_data(d, o)
    dr = B.echapper_textes_client(data)
    od = dict(opts); od['pdf_mode'] = data.get('pdf_mode') or od.get('pdf_mode') or 'full'
    for marche, r, sert in B.registre_renderers():
        if sert(d, od):
            open(chemin, 'wb').write(r.render_pdf_bytes(dr)); return marche
    from apps.ventes.quote_engine.generate_devis_premium import generate_premium_pdf
    generate_premium_pdf(data, chemin); return 'legacy'   # le une-page C&I passe bien ici
```
Script complet : `backend/django_core/_cpdf_rendu.py` du worktree sharp-cartwright-8e73c2. La une-page (`pdf_mode='onepage'`) reste au legacy (c'est le vrai chemin).
