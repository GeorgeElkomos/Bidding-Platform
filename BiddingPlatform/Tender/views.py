from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from User.models import Notification
from Tender.models import Tender, Tender_Files
from .permissions import IsSuperUser
from django.http import FileResponse
import io

# Create your views here.

class List_All_TendersView(APIView):
    """View to list all tenders."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenders = Tender.objects.all()
        tender_data = [
            {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "created_by": tender.created_by.username if tender.created_by else None,
            }
            for tender in tenders
        ]
        return Response(
            {"message": "Tenders retrieved successfully", "data": tender_data},
            status=status.HTTP_200_OK
        )

class Tender_DetailView(APIView):
    """View to get details of a specific tender by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tender_id = request.query_params.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            tender = Tender.objects.get(tender_id=tender_id)
            TenderFiles = tender.files.all().order_by("-Uploaded_At")
            
            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "created_by": tender.created_by.username if tender.created_by else None,
                "files": (
                    [
                        {
                            "file_id": cert.file_id,
                            "file_name": cert.File_Name,
                            "file_type": cert.File_Type,
                            "file_size": cert.File_Size,
                            "uploaded_at": cert.Uploaded_At,
                        }
                        for cert in TenderFiles
                    ]
                    if TenderFiles
                    else []
                ),
            }
            return Response(
                {"message": "Tender details retrieved successfully", "data": tender_data},
                status=status.HTTP_200_OK
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class Get_TenderFile_Data(APIView):
    """View to retrieve file data for a specific VAT certificate by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            tender_file = Tender_Files.objects.get(file_id=file_id)
            
            # For file downloads, we need to handle differently since we're returning binary data
            # We'll return metadata in a standard format when requested
            if request.query_params.get("metadata_only") == "true":
                file_metadata = {
                    "file_id": tender_file.file_id,
                    "file_name": tender_file.File_Name,
                    "file_type": tender_file.File_Type,
                    "file_size": tender_file.File_Size,
                    "uploaded_at": tender_file.Uploaded_At
                }
                return Response(
                    {"message": "File metadata retrieved successfully", "data": file_metadata},
                    status=status.HTTP_200_OK
                )
            else:
                # For actual file download, create a file-like object and return it
                file_stream = io.BytesIO(tender_file.File_Data)
                response = FileResponse(
                    file_stream, 
                    content_type=tender_file.File_Type,
                    as_attachment=True,
                    filename=tender_file.File_Name
                )
                return response
                
        except Tender_Files.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class Create_TenderView(APIView):
    """View to create a new tender. Only superusers can create tenders."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender = Tender.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                budget=data.get("budget"),
                created_by=request.user,  # Assuming the user is authenticated
            )

            # Handle file uploads
            vat_files = request.FILES.getlist("files")
            uploaded_files = []

            if vat_files:
                for file in vat_files:
                    # Read the file data
                    file_data = file.read()

                    # Create the attachment record
                    tender_file = Tender_Files.objects.create(
                        tender=tender,
                        file_name=file.name,
                        file_type=file.content_type,
                        file_size=file.size,
                        file_data=file_data,
                    )

                    uploaded_files.append({
                        "file_id": tender_file.file_id,
                        "file_name": file.name,
                        "file_type": file.content_type,
                        "file_size": file.size
                    })

            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "uploaded_files": uploaded_files,
                "files_count": len(uploaded_files)
            }
            # notify the user about the new tender creation
            Notification.send_notification(message=f"A new tender '{tender.title}' has been created.", target_type="NORMAL")
            # Notify all superusers about the new tender
            Notification.send_notification(message="A new tender has been created.", target_type="SUPER")
            return Response(
                {
                    "message": "Tender created successfully.",
                    "data": tender_data
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Update_TenderView(APIView):
    """View to update an existing tender. Only superusers can update tenders."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)

            # Only update fields that are provided in the request
            if "title" in data:
                tender.title = data["title"]
            if "description" in data:
                tender.description = data["description"]
            if "start_date" in data:
                tender.start_date = data["start_date"]
            if "end_date" in data:
                tender.end_date = data["end_date"]
            if "budget" in data:
                tender.budget = data["budget"]

            tender.save()
            
            updated_fields = [
                field
                for field in [
                    "title",
                    "description",
                    "start_date",
                    "end_date",
                    "budget",
                ]
                if field in data
            ]
            
            tender_data = {
                "tender_id": tender.tender_id,
                "updated_fields": updated_fields,
                "tender": {
                    "title": tender.title,
                    "description": tender.description,
                    "start_date": tender.start_date,
                    "end_date": tender.end_date,
                    "budget": tender.budget,
                }
            }
            # Notify the user about the tender update
            Notification.send_notification(message=f"The tender '{tender.title}' has been updated.", target_type="NORMAL")
            return Response(
                {
                    "message": "Tender updated successfully.",
                    "data": tender_data
                },
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Add_TenderFileView(APIView):
    """View to add multiple files to an existing tender."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)

            # Handle multiple file uploads
            files = request.FILES.getlist("files")
            if not files:
                return Response(
                    {"message": "At least one file is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            uploaded_files = []
            
            for file in files:
                # Read the file data as BLOB
                file_data = file.read()
                
                # Create unique filenames with timestamp if needed
                import datetime
                import os
                
                # Split the filename into name and extension
                file_name, file_extension = os.path.splitext(file.name)
                
                # Add current timestamp to ensure uniqueness
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{file_name}_{timestamp}{file_extension}"

                # Create the attachment record with BLOB data
                tender_file = Tender_Files.objects.create(
                    tender=tender,
                    file_name=unique_filename,
                    file_type=file.content_type,
                    file_size=file.size,
                    file_data=file_data,
                )
                
                uploaded_files.append({
                    "file_id": tender_file.file_id,
                    "file_name": unique_filename,
                    "original_filename": file.name,
                    "file_type": file.content_type,
                    "file_size": file.size
                })

            return Response(
                {
                    "message": f"{len(uploaded_files)} file(s) uploaded successfully.",
                    "data": {
                        "uploaded_files": uploaded_files,
                        "files_count": len(uploaded_files),
                        "tender_id": tender_id
                    }
                },
                status=status.HTTP_201_CREATED,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_TenderFileView(APIView):
    """View to delete a specific tender file by ID."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def delete(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender_file = Tender_Files.objects.get(file_id=file_id)
            tender_file.delete()

            return Response(
                {"message": "Tender file deleted successfully.", "data": {"file_id": file_id}},
                status=status.HTTP_200_OK,
            )
        except Tender_Files.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_TenderView(APIView):
    """View to delete a specific tender by ID."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def delete(self, request):
        try:
            tender_id = request.data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)
            tender.delete()
            # Notify the user about the tender deletion
            Notification.send_notification(message=f"The tender '{tender.title}' has been deleted.", target_type="NORMAL")
            return Response(
                {"message": "Tender deleted successfully.", "data": {"tender_id": tender_id}},
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )
