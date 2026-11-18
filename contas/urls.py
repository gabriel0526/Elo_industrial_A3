from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path(
        'entrar/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html', authentication_form=LoginForm
        ),
        name='login',
    ),
    path('sair/', auth_views.LogoutView.as_view(), name='logout'),
]
