from django.urls import path
from . import views

urlpatterns = [
    path('perfil/',           views.PerfilView.as_view()),
    path('perfil/senha/',     views.AlterarSenhaView.as_view()),
    path('admins/',           views.AdminUsuariosView.as_view()),
    path('admins/<int:user_id>/', views.AdminUsuarioDetailView.as_view()),
    path('parametros/',       views.ParametrosView.as_view()),
]