from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.db import IntegrityError
from django.http import FileResponse
import io
from User.models import Notification
from Tender.permissions import IsCompany, IsSuperUser

from .models import Bit, Bit_Files
from Tender.models import Tender


# Create your views here.

class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100

class Get_All_Bits_For_TenderView(APIView):
    """
    View to get all bits for a specific tender.
    """

    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        try:
            tender_id = request.query_params.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            # Get search query parameter
            search_query = request.query_params.get('search', '').strip()
            
            # Get filter parameters
            min_cost = request.query_params.get('min_cost')
            max_cost = request.query_params.get('max_cost')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            is_accepted = request.query_params.get('is_accepted')
            
            tender = Tender.objects.get(tender_id=tender_id)
            bits = Bit.objects.filter(tender=tender)
            
            # Apply search filter if search query is provided
            if search_query:
                bits = bits.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(created_by__username__icontains=search_query)
                )
                
            # Apply additional filters
            if min_cost:
                bits = bits.filter(cost__gte=min_cost)
            if max_cost:
                bits = bits.filter(cost__lte=max_cost)
            if start_date:
                bits = bits.filter(date__gte=start_date)
            if end_date:
                bits = bits.filter(date__lte=end_date)
            if is_accepted is not None:
                is_accepted_bool = is_accepted.lower() == 'true'
                bits = bits.filter(Is_Accepted=is_accepted_bool)
                
            # Order by date (newest first)
            bits = bits.order_by('-date')
            
            # Apply pagination
            paginator = StandardPagination()
            paginated_bits = paginator.paginate_queryset(bits, request)

            # Serialize the bits data
            bits_data = [
                {
                    "bit_id": bit.bit_id,
                    "title": bit.title,
                    # "description": bit.description,
                    "date": bit.date,
                    "created_by": (
                        {
                            "user_id": bit.created_by.User_Id,
                            "username": bit.created_by.username,
                        }
                        if bit.created_by
                        else None
                    ),
                    "cost": str(bit.cost),  # Convert Decimal to string
                    "is_accepted": bit.Is_Accepted,
                }
                for bit in paginated_bits
            ]

            return paginator.get_paginated_response({
                "message": "Bits retrieved successfully",
                "search_query": search_query,
                "filters": {
                    "min_cost": min_cost,
                    "max_cost": max_cost,
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_accepted": is_accepted
                },
                "total_count": bits.count(),
                "data": bits_data
            })

        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Get_All_My_BitsView(APIView):
    """
    View to get all bits created by the authenticated user.
    """

    permission_classes = [IsAuthenticated, IsCompany]

    def get(self, request):
        try:
            user = request.user
            
            # Get search query parameter
            search_query = request.query_params.get('search', '').strip()
            
            # Get filter parameters
            min_cost = request.query_params.get('min_cost')
            max_cost = request.query_params.get('max_cost')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            is_accepted = request.query_params.get('is_accepted')
            tender_id = request.query_params.get('tender_id')
            
            bits = Bit.objects.filter(created_by=user)
            
            # Apply search filter if search query is provided
            if search_query:
                bits = bits.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(tender__title__icontains=search_query)
                )
                
            # Apply additional filters
            if min_cost:
                bits = bits.filter(cost__gte=min_cost)
            if max_cost:
                bits = bits.filter(cost__lte=max_cost)
            if start_date:
                bits = bits.filter(date__gte=start_date)
            if end_date:
                bits = bits.filter(date__lte=end_date)
            if is_accepted is not None:
                is_accepted_bool = is_accepted.lower() == 'true'
                bits = bits.filter(Is_Accepted=is_accepted_bool)
            if tender_id:
                bits = bits.filter(tender__tender_id=tender_id)
                
            # Order by date (newest first)
            bits = bits.order_by('-date')
            
            # Apply pagination
            paginator = StandardPagination()
            paginated_bits = paginator.paginate_queryset(bits, request)
              # Serialize the bits data
            bits_data = [
                {                    "bit_id": bit.bit_id,
                    "title": bit.title,
                    # "description": bit.description,
                    "date": bit.date,
                    "cost": str(bit.cost),  # Convert Decimal to string
                    "is_accepted": bit.Is_Accepted,
                    "creator_name": bit.created_by.name if bit.created_by else None,
                    "creator_username": bit.created_by.username if bit.created_by else None,
                    "tender": {
                        "tender_id": bit.tender.tender_id,
                        "title": bit.tender.title,
                    },
                }
                for bit in paginated_bits
            ]

            return paginator.get_paginated_response({
                "message": "Bits retrieved successfully",
                "search_query": search_query,
                "filters": {
                    "min_cost": min_cost,
                    "max_cost": max_cost,
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_accepted": is_accepted,
                    "tender_id": tender_id
                },
                "total_count": bits.count(),
                "data": bits_data
            })

        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Get_Bit_DetailView(APIView):
    """
    View to get the details of a specific bit.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            bit_id = request.query_params.get("bit_id")
            if not bit_id:
                return Response(
                    {"message": "bit_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.get(bit_id=bit_id)            # Serialize the bit data
            bit_data = {
                "bit_id": bit.bit_id,
                "title": bit.title,
                "description": bit.description,
                "date": bit.date,
                "created_by": (
                    {
                        "user_id": bit.created_by.User_Id,
                        "username": bit.created_by.username,
                    }
                    if bit.created_by
                    else None
                ),
                "cost": str(bit.cost),  # Convert Decimal to string
                "is_accepted": bit.Is_Accepted,
                "tender": {
                    "tender_id": bit.tender.tender_id,
                    "title": bit.tender.title,
                },
                "files": [
                    {
                        "file_id": file.file_id,
                        "file_name": file.file_name,
                        "file_type": file.file_type,
                        "file_size": file.file_size,
                        "uploaded_at": file.Uploaded_At,
                    }
                    for file in bit.files.all()
                ],
            }

            return Response(
                {"message": "Bit details retrieved successfully", "data": bit_data},
                status=status.HTTP_200_OK,
            )

        except Bit.DoesNotExist:
            return Response(
                {"message": "Bit not found", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Get_BitFile_Data(APIView):
    """
    View to get the file data of a specific bit file.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit_file = Bit_Files.objects.get(file_id=file_id)

            # For file downloads, we need to handle differently since we're returning binary data
            # We'll return metadata in a standard format when requested
            if request.query_params.get("metadata_only") == "true":
                file_metadata = {
                    "file_id": bit_file.file_id,
                    "file_name": bit_file.file_name,
                    "file_type": bit_file.file_type,
                    "file_size": bit_file.file_size,
                    "uploaded_at": bit_file.Uploaded_At,
                }
                return Response(
                    {
                        "message": "File metadata retrieved successfully",
                        "data": file_metadata,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                # For actual file download, create a file-like object and return it
                file_stream = io.BytesIO(bit_file.file_data)
                response = FileResponse(
                    file_stream,
                    content_type=bit_file.file_type,
                    as_attachment=True,
                    filename=bit_file.file_name,
                )
                return response

        except Bit_Files.DoesNotExist:
            return Response(
                {"message": "File not found", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Create_BitView(APIView):
    """
    View to create a new bit.
    """

    permission_classes = [IsAuthenticated, IsCompany]

    def post(self, request):
        try:
            data = request.data
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)
            user = request.user

            # Check if user already has a bid for this tender
            existing_bit = Bit.objects.filter(created_by=user, tender=tender).first()
            if existing_bit:
                return Response(
                    {"message": "You have already submitted a bid for this tender", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                date=data.get("date"),
                created_by=user,
                tender=tender,
                cost=data.get("cost"),
            )
            
            # Handle file uploads
            vat_files = request.FILES.getlist("files")
            if vat_files:
                for file in vat_files:
                    # Read the file data
                    file_data = file.read()

                    # Create unique filenames with timestamp to avoid conflicts
                    import datetime
                    import os

                    # Split the filename into name and extension
                    file_name, file_extension = os.path.splitext(file.name)

                    # Add current timestamp to ensure uniqueness
                    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                    unique_filename = f"{file_name}_{timestamp}{file_extension}"

                    # Create the attachment record
                    Bit_Files.objects.create(
                        bit=bit,
                        file_name=unique_filename,
                        file_type=file.content_type,
                        file_size=file.size,
                        file_data=file_data,
                    )

            bit_data = {
                "bit_id": bit.bit_id,
                "title": bit.title,
                "description": bit.description,
                "cost": str(bit.cost),
                "date": bit.date,            }
            # Notify the tender creator about the new bit
            Notification.send_notification(
                message=f"New Bit Created for Tender {tender.title} by {user.username}", target_type="SUPER"
            )
            return Response(
                {"message": "Bit created successfully", "data": bit_data},
                status=status.HTTP_201_CREATED,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except IntegrityError:
            return Response(
                {"message": "You have already submitted a bid for this tender", "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Add_BitFileView(APIView):
    """View to add multiple files to an existing bit.

    Example request:
    POST /api/bit/add_file/
    Content-Type: multipart/form-data

    Form data:
    - bit_id: 123  (Required)
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

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            bit_id = data.get("bit_id")
            if not bit_id:
                return Response(
                    {"error": "bit_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.get(bit_id=bit_id)

            # Handle multiple file uploads
            files = request.FILES.getlist("files")
            if not files:
                return Response(
                    {"error": "At least one file is required", "data": []},
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
                file_name, file_extension = os.path.splitext(file.name)                # Add current timestamp to ensure uniqueness
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                unique_filename = f"{file_name}_{timestamp}{file_extension}"

                # Create the attachment record with BLOB data
                bit_file = Bit_Files.objects.create(
                    bit=bit,
                    file_name=unique_filename,
                    file_type=file.content_type,
                    file_size=file.size,
                    file_data=file_data,
                )

                uploaded_files.append(
                    {
                        "file_id": bit_file.file_id,
                        "file_name": unique_filename,
                        "original_filename": file.name,
                        "file_type": file.content_type,
                        "file_size": file.size,
                    }
                )

            return Response(
                {
                    "message": f"{len(uploaded_files)} file(s) uploaded successfully.",
                    "data": {
                        "uploaded_files": uploaded_files,
                        "files_count": len(uploaded_files),
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        except Bit.DoesNotExist:
            return Response(
                {"message": "Bit not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_BitFileView(APIView):
    """View to delete a specific tender file by ID."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"error": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            Bit_file = Bit_Files.objects.get(file_id=file_id)
            Bit_file.delete()

            return Response(
                {
                    "message": "Bit file deleted successfully.",
                    "data": {"file_id": file_id},
                },
                status=status.HTTP_200_OK,
            )
        except Bit_Files.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_BitView(APIView):
    """View to delete a specific bit by ID."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            bit_id = request.data.get("bit_id")
            if not bit_id:
                return Response(
                    {"error": "bit_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.get(bit_id=bit_id)
            bit.delete()

            return Response(
                {"message": "Bit deleted successfully.", "data": {"bit_id": bit_id}},
                status=status.HTTP_200_OK,
            )
        except Bit.DoesNotExist:
            return Response(
                {"message": "Bit not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Update_BitView(APIView):
    """View to update an existing bit."""

    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            data = request.data
            bit_id = data.get("bit_id")
            if not bit_id:
                return Response(
                    {"error": "bit_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.get(bit_id=bit_id)

            # Update the bit fields
            bit.title = data.get("title", bit.title)
            bit.description = data.get("description", bit.description)
            bit.date = data.get("date", bit.date)
            bit.cost = data.get("cost", bit.cost)
            bit.save()

            bit_data = {
                "bit_id": bit.bit_id,
                "title": bit.title,
                "description": bit.description,
                "date": bit.date,
                "cost": str(bit.cost),
            }
            # Notify the tender creator about the bit update
            Notification.send_notification(
                message=f"Bit {bit.title} updated by {request.user.username}", target_type="SUPER"
            )
            # notify the user who created the bit
            Notification.send_notification(
                message=f"Your Bit {bit.title} has been updated by {request.user.username}",
                user=bit.created_by.User_Id,
            )
            return Response(
                {"message": "Bit updated successfully.", "data": bit_data},
                status=status.HTTP_200_OK,
            )
        except Bit.DoesNotExist:
            return Response(
                {"message": "Bit not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Bit_Request_RespondView(APIView):
    """View to respond to a bit (accept or reject)."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        try:
            data = request.data
            bit_id = data.get("bit_id")
            if not bit_id:
                return Response(
                    {"error": "bit_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit = Bit.objects.get(bit_id=bit_id)
            action = data.get("action")  # 'Accept' or 'Reject'

            if action == "Accept":
                bit.Is_Accepted = True
            elif action == "Reject":
                bit.Is_Accepted = False
            else:
                return Response(
                    {"error": "Invalid action. Use 'Accept' or 'Reject'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bit.save()

            bit_data = {
                "bit_id": bit.bit_id,
                "Is_Accepted": bit.Is_Accepted,
                "action": action,
            }
            # notify the user who created the bit about the action taken
            Notification.send_notification(
                message=f"Your Bit {bit.title} has been {action.lower()}ed by {request.user.username}",
                user=bit.created_by.User_Id,
            )
            return Response(
                {"message": f"Bit {action}ed successfully.", "data": bit_data},
                status=status.HTTP_200_OK,
            )
        except Bit.DoesNotExist:
            return Response(
                {"message": "Bit not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )
