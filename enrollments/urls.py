from django.urls import path
from .views import EnrollmentCreateView, EnrollmentListView, LoginCandidatoView, TrocarSenhaView

urlpatterns = [
    path('submit/', EnrollmentCreateView.as_view(), name='enrollment-submit'),
    path('list/', EnrollmentListView.as_view(), name='enrollment-list'),
    
    path('candidato/login/', LoginCandidatoView.as_view(), name='login_candidato'),
    path('candidato/trocar-senha/', TrocarSenhaView.as_view(), name='trocar_senha'),
]