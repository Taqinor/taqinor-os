"""TAQINOR quote engine — v2 PROTOTYPE package.

A PARALLEL COPY used to prototype proposal improvements. It is NOT wired into
/proposal, the Celery task, or any live path — the working engine
(apps/ventes/quote_engine/) is untouched. Render a sample with:

    from apps.ventes.quote_engine_v2 import render
    render.render_pdf("/tmp/out.pdf")
"""
