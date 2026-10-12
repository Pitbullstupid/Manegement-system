from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-otp/", views.ResendOTPView.as_view(), name="resend-otp"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/verify/", views.LoginVerifyView.as_view(), name="login-verify"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),  # có sẵn của simplejwt
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("users/", views.UserListView.as_view(), name="user-list"),  # chỉ ADMIN
]
