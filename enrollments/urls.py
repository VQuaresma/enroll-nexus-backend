from django.urls import path
from .views import (
    EnrollmentCreateView,
    EnrollmentListView,
    LoginCandidatoView,
    TrocarSenhaView,
    ImportarCandidatosView,
    PeriodoMatriculaListCreateView,   
    PeriodoMatriculaDetailView,
    EnrollmentStatusUpdateView,   
    EnrollmentComprovanteView,     
    EnrollmentDocumentosView,
    ComprovanteDataView,   
)

urlpatterns = [
    path('submit/', EnrollmentCreateView.as_view(), name='enrollment-submit'),
    path('list/', EnrollmentListView.as_view(), name='enrollment-list'),
    path('import/', ImportarCandidatosView.as_view(), name='enrollment-import'),

    path('candidato/login/', LoginCandidatoView.as_view(), name='login_candidato'),
    path('candidato/trocar-senha/', TrocarSenhaView.as_view(), name='trocar_senha'),

    path('<int:pk>/status/', EnrollmentStatusUpdateView.as_view(), name='enrollment-status'),        
    path('<int:pk>/comprovante/', EnrollmentComprovanteView.as_view(), name='enrollment-comprovante'), 
    path('<int:pk>/documentos/', EnrollmentDocumentosView.as_view(), name='enrollment-documentos'),

    path('periodos/', PeriodoMatriculaListCreateView.as_view(), name='periodos-list'),       
    path('periodos/<int:pk>/', PeriodoMatriculaDetailView.as_view(), name='periodos-detail'),

    path('<int:pk>/comprovante-dados/', ComprovanteDataView.as_view(), name='comprovante-dados'),
   
]
