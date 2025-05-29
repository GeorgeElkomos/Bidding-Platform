from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from Tender.models import Tender, Tender_Files
from .permissions import IsSuperUser

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
        return Response(tender_data, status=status.HTTP_200_OK)

class Tender_DetailView(APIView):
    """View to get details of a specific tender by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tender_id = request.query_params.get("tender_id")
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
            return Response(tender_data, status=status.HTTP_200_OK)
        except Tender.DoesNotExist:
            return Response(
                {"error": "Tender not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

class Get_TenderFile_Data(APIView):
    """View to retrieve file data for a specific VAT certificate by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")
            vat_certificate = Tender_Files.objects.get(file_id=file_id)
            file_data = vat_certificate.File_Data

            # Return the file data as a binary response
            response = Response(file_data, content_type=vat_certificate.File_Type)
            response["Content-Disposition"] = (
                f'attachment; filename="{vat_certificate.File_Name}"'
            )
            return response
        except Tender_Files.DoesNotExist:
            return Response({"error": "File not found."}, status=404)

class Create_TenderView(APIView):
    """View to create a new tender. Only superusers can create tenders.

    Request Format:
    - Must use multipart/form-data
    - Text fields and files are sent as form fields

    Form Fields:
    - title: "Construction Project 2025"     (Text)
    - description: "Building construction"    (Text)
    - start_date: "2025-06-01T09:00:00Z"    (Text)
    - end_date: "2025-12-31T18:00:00Z"      (Text)
    - budget: "1500000.00"                   (Text)
    - files: [File Upload]                   (File, can add multiple)

    In Postman:
    1. Select POST method
    2. Select 'Body' tab
    3. Select 'form-data'
    4. Add each field as a key-value pair
    5. For files, click the 'File' type button on the right of the key field
    6. Can add multiple files using the same key 'files'

    Response:
    {
        "message": "Tender created successfully.",
        "tender_id": 1
    }

    Notes:
    - Dates must be in ISO format with timezone (YYYY-MM-DDThh:mm:ssZ)
    - Budget must be a decimal number as string
    - Files are uploaded as actual files, not base64 or other encoding
    - Only superusers can create tenders
    """

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
            if vat_files:
                for file in vat_files:
                    # Read the file data
                    file_data = file.read()

                    # Create the attachment record
                    Tender_Files.objects.create(
                        tender=tender,
                        file_name=file.name,
                        file_type=file.content_type,
                        file_size=file.size,
                        file_data=file_data,
                    )

            return Response(
                {
                    "message": "Tender created successfully.",
                    "tender_id": tender.tender_id,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Update_TenderView(APIView):
    """View to update an existing tender. Only superusers can update tenders.

    Request Format:
    - Can send any field that needs to be updated
    - Omitted fields will remain unchanged

    Example requests:
    // Update just the title
    {
        "tender_id": 1,
        "title": "New Title"
    }

    // Update just the start_date
    {
        "tender_id": 1,
        "start_date": "2025-07-01T09:00:00Z"
    }

    // Update multiple fields
    {
        "tender_id": 1,
        "title": "New Title",
        "budget": "2000000.00"
    }
    """

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"error": "tender_id is required"},
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

            return Response(
                {
                    "message": "Tender updated successfully.",
                    "updated_fields": [
                        field
                        for field in [
                            "title",
                            "description",
                            "start_date",
                            "end_date",
                            "budget",
                        ]
                        if field in data
                    ],
                },
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"error": "Tender not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Add_TenderFileView(APIView):
    """View to add multiple files to an existing tender.
    
    Example request:
    POST /api/tender/add_file/
    Content-Type: multipart/form-data
    
    Form data:
    - tender_id: 123  (Required)
    - files: [file1.pdf, file2.xlsx, file3.pdf]  (Multiple file upload)
    
    Response:
    {
        "message": "3 file(s) uploaded successfully.",
        "uploaded_files": [
            {
                "file_id": 1,
                "file_name": "document1.pdf",
                "file_type": "application/pdf",
                "file_size": 1024567
            },
            ...
        ],
        "files_count": 3
    }
    """

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"error": "tender_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)

            # Handle multiple file uploads
            files = request.FILES.getlist("files")
            if not files:
                return Response(
                    {"error": "At least one file is required"},
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
                    "uploaded_files": uploaded_files,
                    "files_count": len(uploaded_files)
                },
                status=status.HTTP_201_CREATED,
            )
        except Tender.DoesNotExist:
            return Response(
                {"error": "Tender not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
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
                    {"error": "file_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender_file = Tender_Files.objects.get(file_id=file_id)
            tender_file.delete()

            return Response(
                {"message": "Tender file deleted successfully."},
                status=status.HTTP_200_OK,
            )
        except Tender_Files.DoesNotExist:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
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
                    {"error": "tender_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)
            tender.delete()

            return Response(
                {"message": "Tender deleted successfully."},
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"error": "Tender not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
