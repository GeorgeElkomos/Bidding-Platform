from django.urls import path
from User.views import (
    User_RegesterView,
    LoginView,
    UserDetailView,
    List_UserView,
    Delete_All_UsersView,
    Create_Super_User,
    Account_Request_Respond,
)

urlpatterns = [
    path("register/", User_RegesterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("details/", UserDetailView.as_view(), name="user_detail"),
    path("getall/", List_UserView.as_view(), name="list_users"),
    path("deleteall/", Delete_All_UsersView.as_view(), name="delete_all_users"),
    path("createsuperuser/", Create_Super_User.as_view(), name="create_super_user"),
    path("account_request_respond/", Account_Request_Respond.as_view(), name="account_request_respond"),
]
