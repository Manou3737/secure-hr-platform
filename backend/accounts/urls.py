from django.urls import include, path

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


router = DefaultRouter()

router.register(
    "register",
    views.UserRegistrationViewSet,
    basename="register",
)

router.register(
    "verify-email",
    views.EmailVerificationViewSet,
    basename="verify-email",
)

router.register(
    "login",
    views.LoginViewSet,
    basename="login",
)

router.register(
    "logout",
    views.LogoutViewSet,
    basename="logout",
)

router.register(
    "password-change",
    views.PasswordChangeViewSet,
    basename="password-change",
)

router.register(
    "password-reset",
    views.PasswordResetRequestViewSet,
    basename="password-reset",
)

router.register(
    "password-reset-confirm",
    views.PasswordResetConfirmViewSet,
    basename="password-reset-confirm",
)

router.register(
    "account-status",
    views.AccountStatusViewSet,
    basename="account-status",
)

router.register(
    "privileges",
    views.PrivilegeManagementViewSet,
    basename="privileges",
)


urlpatterns = [
    path(
        "refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "me/",
        views.MeView.as_view(),
        name="me",
    ),
    path(
        "register/",
        views.UserRegistrationViewSet.as_view({"post": "create"}),
        name="register",
    ),
    path(
        "login/",
        views.LoginViewSet.as_view({"post": "create"}),
        name="login",
    ),
    path(
        "password-change/",
        views.PasswordChangeViewSet.as_view({"post": "create"}),
        name="password_change",
    ),
    path(
        "logout/",
        views.LogoutViewSet.as_view({"post": "create"}),
        name="logout",
    ),
    path(
        "",
        include(router.urls),
    ),
]
