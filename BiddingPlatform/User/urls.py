from django.urls import path
from User.views import RejesterView, LoginView, UpdateuserInfo

urlpatterns = [
    path("register/", RejesterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("update/", UpdateuserInfo.as_view(), name="update_user_info"),
]
