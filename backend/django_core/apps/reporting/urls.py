from django.urls import path

from .views import (
    dashboard,
    pipeline_value,
    sales_report,
    stock_report,
    service_report,
    journal_ventes_xlsx,
)

urlpatterns = [
    path('dashboard/', dashboard, name='reporting-dashboard'),
    # T7b — tableau de bord valeur du pipeline
    path('pipeline-value/', pipeline_value, name='reporting-pipeline-value'),
    # T13 / T14 / T15 — hub de rapports (chacun exportable en ?format=xlsx)
    path('sales/', sales_report, name='reporting-sales'),
    path('stock/', stock_report, name='reporting-stock'),
    path('service/', service_report, name='reporting-service'),
    # T12 — export comptable journal des ventes + TVA (toujours .xlsx)
    path('journal-ventes/', journal_ventes_xlsx, name='reporting-journal-ventes'),
]
