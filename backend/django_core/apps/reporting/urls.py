from django.urls import path
from .views import dashboard
from .search import global_search, notifications
from .pipeline import pipeline
from .reports import sales_report, stock_report, service_report

urlpatterns = [
    path('dashboard/', dashboard, name='reporting-dashboard'),
    path('search/', global_search, name='global-search'),
    path('notifications/', notifications, name='in-app-notifications'),
    path('pipeline/', pipeline, name='reporting-pipeline'),
    path('reports/sales/', sales_report, name='report-sales'),
    path('reports/stock/', stock_report, name='report-stock'),
    path('reports/service/', service_report, name='report-service'),
]
