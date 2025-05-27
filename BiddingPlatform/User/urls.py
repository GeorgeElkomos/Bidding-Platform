from django.urls import path
from User.views import (
    User_RegesterView,
    LoginView,
    UserDetailView,
    List_UserView,
    Delete_All_UsersView,
)

urlpatterns = [
    path("register/", User_RegesterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("details/", UserDetailView.as_view(), name="user_detail"),
    path("getall/", List_UserView.as_view(), name="list_users"),
    path("deleteall/", Delete_All_UsersView.as_view(), name="delete_all_users"),
]
