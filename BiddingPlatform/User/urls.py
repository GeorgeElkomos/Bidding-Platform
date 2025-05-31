from django.urls import path
from User.views import (
    User_RegesterView,
    LoginView,
    UserDetailView,
    List_UserView,
    Delete_All_UsersView,
    Create_Super_User,
    Account_Request_Respond,
    Get_All_Pending_Users,
    Get_UserFile_Data,
    Add_UserFileView,
    Delete_UserFileView,
    Delete_UserView,
    Update_UserView,
    ListSuperUsersView,
)

urlpatterns = [
    path("register/", User_RegesterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("details/", UserDetailView.as_view(), name="user_detail"),
    path("getall/", List_UserView.as_view(), name="list_users"),
    path("getsuperadmins/", ListSuperUsersView.as_view(), name="list_superadmins"),
    path("deleteall/", Delete_All_UsersView.as_view(), name="delete_all_users"),
    path("createsuperuser/", Create_Super_User.as_view(), name="create_super_user"),
    path(
        "account_request_respond/",
        Account_Request_Respond.as_view(),
        name="account_request_respond",
    ),
    path(
        "get_all_pending_users/",
        Get_All_Pending_Users.as_view(),
        name="get_all_pending_users",
    ),
    path("get_user_file_data/", Get_UserFile_Data.as_view(), name="get_user_file_data"),
    path("add_user_file/", Add_UserFileView.as_view(), name="add_user_file"),
    path("delete_user_file/", Delete_UserFileView.as_view(), name="delete_user_file"),
    path("delete_user/", Delete_UserView.as_view(), name="delete_user"),
    path("update_user/", Update_UserView.as_view(), name="update_user"),
]
