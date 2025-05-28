from django.urls import path

from Bit.views import (
    Get_All_Bits_For_TenderView,
    Get_All_My_BitsView,
    Get_Bit_DetailView,
    Get_BitFile_Data,
    Create_BitView,
    Add_BitFileView,
    Delete_BitFileView,
    Delete_BitView,
    Update_BitView,
    Bit_Request_RespondView,
)

urlpatterns = [
    path("getallfortender/", Get_All_Bits_For_TenderView.as_view(), name="tender_list"),
    path("getmy/", Get_All_My_BitsView.as_view(), name="create_tender"),
    path("details/", Get_Bit_DetailView.as_view(), name="get_tender_file_data"),
    path("getfiledata/", Get_BitFile_Data.as_view(), name="tender_detail"),
    path("create/", Create_BitView.as_view(), name="update_tender"),
    path("addfile/", Add_BitFileView.as_view(), name="add_tender_file"),
    path("deletefile/", Delete_BitFileView.as_view(), name="delete_tender_file"),
    path("delete/", Delete_BitView.as_view(), name="delete_tender"),
    path("update/", Update_BitView.as_view(), name="update_bit"),
    path(
        "bit_request_respond/",
        Bit_Request_RespondView.as_view(),
        name="bit_request_respond",
    ),
]
