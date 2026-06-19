from django.urls import path
from .views import dashboard
from .search import global_search, notifications
from .pipeline import pipeline
from .reports import sales_report, stock_report, service_report
from .insights import (
    recurring_revenue, audit_log, job_costing, analytics, commissions,
)
from .archive import archive_client, archive_chantier
from .calendar import calendar_events, calendar_reschedule
from .geo import geo_points
from .balance_export import balance_agee_export

urlpatterns = [
    path('dashboard/', dashboard, name='reporting-dashboard'),
    path('search/', global_search, name='global-search'),
    path('notifications/', notifications, name='in-app-notifications'),
    path('calendar/', calendar_events, name='reporting-calendar'),
    path('calendar/reschedule/', calendar_reschedule,
         name='reporting-calendar-reschedule'),
    path('geo/', geo_points, name='reporting-geo'),
    path('pipeline/', pipeline, name='reporting-pipeline'),
    path('reports/sales/', sales_report, name='report-sales'),
    path('reports/stock/', stock_report, name='report-stock'),
    path('reports/service/', service_report, name='report-service'),
    path('insights/recurring-revenue/', recurring_revenue,
         name='insights-recurring-revenue'),
    path('insights/audit-log/', audit_log, name='insights-audit-log'),
    path('insights/job-costing/', job_costing, name='insights-job-costing'),
    path('insights/analytics/', analytics, name='insights-analytics'),
    path('insights/commissions/', commissions, name='insights-commissions'),
    path('archive/client/<int:pk>/', archive_client,
         name='reporting-archive-client'),
    path('archive/chantier/<int:pk>/', archive_chantier,
         name='reporting-archive-chantier'),
    # Export .xlsx de la balance âgée (créances par client + tranches d'âge),
    # borné à la société (miroir de l'export journal des ventes).
    path('balance-agee/export/', balance_agee_export,
         name='reporting-balance-agee-export'),
]
