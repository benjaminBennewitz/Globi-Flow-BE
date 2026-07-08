# apps/imports/urls.py

"""URLs für Importe und Review."""

from django.urls import path
from apps.imports.views import DemoImportView, ImportJobDetailView, ImportJobListView, ManualImportView, ReviewCandidateBulkUpdateView, ReviewCandidateDetailView, ReviewQueueView, UploadImportView

urlpatterns = [
    path('imports/', ImportJobListView.as_view(), name='imports-root'),
    path('imports/jobs/', ImportJobListView.as_view(), name='import-jobs'),
    path('imports/jobs/<str:public_id>/', ImportJobDetailView.as_view(), name='import-job-detail'),
    path('imports/upload/', UploadImportView.as_view(), name='import-upload'),
    path('imports/manual/', ManualImportView.as_view(), name='import-manual'),
    path('imports/demo/', DemoImportView.as_view(), name='import-demo'),
    path('imports/review/', ReviewQueueView.as_view(), name='review-queue'),
    path('imports/review/bulk/', ReviewCandidateBulkUpdateView.as_view(), name='review-candidate-bulk'),
    path('imports/review/<str:public_id>/', ReviewCandidateDetailView.as_view(), name='review-candidate-detail'),
]
