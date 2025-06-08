from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.core.exceptions import ValidationError
from User.models import Notification
from Tender.models import Tender, Tender_Files
from Bit.models import Bit, Bit_Files
from .permissions import IsSuperUser
from django.http import FileResponse
from asgiref.sync import sync_to_async
import io
import logging
import asyncio
import os
import re
import json
import datetime
from typing import List, Dict, Any, Union, BinaryIO
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Tender_and_Bids_files_By_Tender_Id(APIView):
    """View to retrieve all files budgets related to a specific tender by its ID and its bids files and budgets."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        try:
            # Get tender ID from request parameters
            tender_id = request.query_params.get("tender_id")
            
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": {}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Get the tender
            tender = Tender.objects.get(tender_id=tender_id)
            
            # Get all tender files
            tender_files = tender.files.all().order_by("-Uploaded_At")
            
            # Get all bids for this tender
            bids = tender.bits.all().order_by("-date")
            
            # Prepare tender data
            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "created_by": tender.created_by.username if tender.created_by else None,
                "files": [
                    {
                        "file_id": file.file_id,
                        "file_name": file.file_name,
                        "file_type": file.file_type,
                        "file_size": file.file_size,
                        "uploaded_at": file.Uploaded_At,
                    }
                    for file in tender_files
                ]
            }
            
            # Prepare bids data
            bids_data = []
            for bid in bids:
                # Get files for each bid
                bid_files = bid.files.all().order_by("-Uploaded_At")
                
                bid_data = {
                    "bit_id": bid.bit_id,
                    "title": bid.title,
                    "description": bid.description,
                    "date": bid.date,
                    "cost": bid.cost,
                    "is_accepted": bid.Is_Accepted,
                    "created_by": bid.created_by.username if bid.created_by else None,
                    "files": [
                        {
                            "file_id": file.file_id,
                            "file_name": file.file_name,
                            "file_type": file.file_type,
                            "file_size": file.file_size,
                            "uploaded_at": file.Uploaded_At,
                        }
                        for file in bid_files
                    ]
                }
                bids_data.append(bid_data)
            
            # Prepare summary statistics
            summary = {
                "total_bids": len(bids_data),
                "accepted_bids": len([bid for bid in bids_data if bid["is_accepted"] is True]),
                "pending_bids": len([bid for bid in bids_data if bid["is_accepted"] is None]),
                "rejected_bids": len([bid for bid in bids_data if bid["is_accepted"] is False]),
                "lowest_bid": min([bid["cost"] for bid in bids_data]) if bids_data else None,
                "highest_bid": max([bid["cost"] for bid in bids_data]) if bids_data else None,
                "average_bid": sum([bid["cost"] for bid in bids_data]) / len(bids_data) if bids_data else None,
                "tender_files_count": len(tender_files),
                "total_bid_files": sum([len(bid["files"]) for bid in bids_data])
            }
            
            response_data = {
                "tender": tender_data,
                "bids": bids_data,
                "summary": summary
            }
            
            return Response(
                {
                    "message": "Tender and bids data retrieved successfully",
                    "data": response_data
                },
                status=status.HTTP_200_OK
            )
            
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error in Tender_and_Bids_files_By_Tender_Id: {str(e)}")
            return Response(
                {"message": f"An error occurred: {str(e)}", "data": {}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

            




class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100

class List_All_TendersView(APIView):
    """View to list all tenders with search and pagination."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get search query parameter
        search_query = request.query_params.get('search', '').strip()
        
        # Start with all tenders
        tenders = Tender.objects.all()
        
        # Apply search filter if search query is provided
        if search_query:
            tenders = tenders.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(created_by__username__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        tenders = tenders.order_by('-start_date')
        
        # Apply pagination
        paginator = StandardPagination()
        paginated_tenders = paginator.paginate_queryset(tenders, request)
        
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
            for tender in paginated_tenders
        ]
        
        return paginator.get_paginated_response({
            "message": "Tenders retrieved successfully",
            "search_query": search_query,
            "total_count": tenders.count(),
            "data": tender_data
        })

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
                "created_by": tender.created_by.username if tender.created_by else None,                "files": (
                    [
                        {
                            "file_id": cert.file_id,
                            "file_name": cert.file_name,
                            "file_type": cert.file_type,
                            "file_size": cert.file_size,
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
                    status=status.HTTP_400_BAD_REQUEST,                )
                
            tender_file = Tender_Files.objects.get(file_id=file_id)
            
            # For file downloads, we need to handle differently since we're returning binary data
            # We'll return metadata in a standard format when requested
            if request.query_params.get("metadata_only") == "true":
                file_metadata = {
                    "file_id": tender_file.file_id,
                    "file_name": tender_file.file_name,
                    "file_type": tender_file.file_type,
                    "file_size": tender_file.file_size,
                    "uploaded_at": tender_file.Uploaded_At
                }
                return Response(
                    {"message": "File metadata retrieved successfully", "data": file_metadata},
                    status=status.HTTP_200_OK
                )
            else:
                # For actual file download, create a file-like object and return it
                file_stream = io.BytesIO(tender_file.file_data)
                response = FileResponse(
                    file_stream, 
                    content_type=tender_file.file_type,
                    as_attachment=True,
                    filename=tender_file.file_name
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
                created_by=request.user, 
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



