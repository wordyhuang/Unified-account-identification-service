from django.urls import path
from . import views

urlpatterns = [
    path("authorize", views.authorize, name="oauth_authorize"),
    path("authorize/confirm", views.authorize_confirm, name="oauth_authorize_confirm"),
    path("authorize/deny", views.authorize_deny, name="oauth_authorize_deny"),
    path("login", views.oauth_login_page, name="oauth_login_page"),
    path("token", views.token_exchange, name="oauth_token_exchange"),
]