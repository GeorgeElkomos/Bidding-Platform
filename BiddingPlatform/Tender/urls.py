from django.urls import path

from Tender.views import (
    List_All_TendersView,
    Create_TenderView,
    Get_TenderFile_Data,
    Tender_DetailView,
    Update_TenderView,
    Delete_TenderFileView,
    Add_TenderFileView,
    Delete_TenderView,
    Evaluate_Tender_Bits
)

urlpatterns = [
    path("getall/", List_All_TendersView.as_view(), name="tender_list"),
    path("create/", Create_TenderView.as_view(), name="create_tender"),
    path("getfiledata/", Get_TenderFile_Data.as_view(), name="get_tender_file_data"),
    path("details/", Tender_DetailView.as_view(), name="tender_detail"),

    path("update/", Update_TenderView.as_view(), name="update_tender"),
    path("addfile/", Add_TenderFileView.as_view(), name="add_tender_file"),
    path("deletefile/", Delete_TenderFileView.as_view(), name="delete_tender_file"),
    path("delete/", Delete_TenderView.as_view(), name="delete_tender"),
    path("evaluate/", Evaluate_Tender_Bits.as_view(), name="evaluate_tender"),
    
]
