# apps/imports/urls.py

"""URLs für Importe und Review."""

from django.urls import path
from apps.imports.views import DemoImportView, ImportJobListView, ReviewCandidateDetailView, ReviewQueueView, UploadImportView

urlpatterns = [
    path('imports/jobs/', ImportJobListView.as_view(), name='import-jobs'),
    path('imports/upload/', UploadImportView.as_view(), name='import-upload'),
    path('imports/demo/', DemoImportView.as_view(), name='import-demo'),
    path('imports/review/', ReviewQueueView.as_view(), name='review-queue'),
    path('imports/review/<str:public_id>/', ReviewCandidateDetailView.as_view(), name='review-candidate-detail'),
]
