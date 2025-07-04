from django.shortcuts import render
from django.http import HttpResponse, FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from Tender.permissions import IsSuperUser
from User.models import AdminType, Notification, User, VAT_Certificate_Manager
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
import io
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

# Create your views here.

# Define a standard pagination class
class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class LoginView(APIView):
    """View for user login.
    Handles user authentication and returns a JWT token.
    """

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"message": "Username and password are required.", "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = authenticate(request, username=username, password=password)
            if user is None:
                return Response(
                    {"message": "Invalid credentials.", "data": []},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if user.Is_Accepted != True:
                return Response(
                    {"message": "Your account is not accepted yet.", "data": []},
                    status=status.HTTP_403_FORBIDDEN,
                )
            print("User authenticated:", user.email)
            Token = RefreshToken.for_user(user)  # Generate refresh token for the user
            return Response(
                {
                    "message": "Login successful.",
                    "data": {
                        "Token": str(Token.access_token),
                        "user_id": user.User_Id,
                        "username": user.username,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "User does not exist.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )


class List_UserView(APIView):
    """View to list all companies with pagination and search."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def get(self, request):
        # Get search parameters
        search_query = request.query_params.get('search', '')
        
        # Apply search filter if provided
        users = User.objects.filter(is_superuser=False)
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) | 
                Q(name__icontains=search_query) | 
                Q(email__icontains=search_query)
            )
            
        # Apply pagination
        paginator = StandardPagination()
        paginated_users = paginator.paginate_queryset(users, request)
        
        # Prepare data
        user_data = [
            {
                "user_Id": user.User_Id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "Is_Accepted": user.Is_Accepted
            }
            for user in paginated_users
        ]
        
        # Return paginated response
        return paginator.get_paginated_response({
            "message": "Users retrieved successfully", 
            "data": user_data
        })


class ListSuperUsersView(APIView):
    """View to list all superadmin users with pagination and search."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated and is a superuser

    def get(self, request):
        # Get search parameters
        search_query = request.query_params.get('search', '')
        
        # Apply search filter if provided
        superusers = User.objects.filter(is_superuser=True)
        if search_query:
            superusers = superusers.filter(
                Q(username__icontains=search_query) | 
                Q(name__icontains=search_query) | 
                Q(email__icontains=search_query)
            )
            
        # Apply pagination
        paginator = StandardPagination()
        paginated_superusers = paginator.paginate_queryset(superusers, request)
        
        # Prepare data
        superuser_data = [
            {
                "user_Id": user.User_Id,
                "username": user.username,
                "name": user.name,
                "email": user.email
            }
            for user in paginated_superusers
        ]
        
        # Return paginated response
        return paginator.get_paginated_response({
            "message": "Superusers retrieved successfully", 
            "data": superuser_data
        })


class UserDetailView(APIView):
    """View to retrieve details of a specific User by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            if IsSuperUser:
                User_id = request.query_params.get("User_Id", request.user.User_Id)
                if not User_id:
                    return Response(
                        {"message": "User_Id is required.", "data": []},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user = User.objects.get(User_Id=User_id)
            else:
                user = request.user
            # Get all VAT certificates for the user
            vat_certificates = user.vat_certificates.all().order_by("-Uploaded_At")

            User_data = {
                "User_Id": user.User_Id,
                "username": user.username,
                "name": user.name,
                "address": user.address,
                "phone_number": user.phone_number,
                "email": user.email,
                "website": user.website,
                "CR_number": user.CR_number,
                "Is_Accepted": user.Is_Accepted,
                "VAT_certificates": (
                    [
                        {
                            "file_id": cert.Id,
                            "file_name": cert.File_Name,
                            "file_type": cert.File_Type,
                            "file_size": cert.File_Size,
                            "uploaded_at": cert.Uploaded_At,
                        }
                        for cert in vat_certificates
                    ]
                    if vat_certificates
                    else []
                ),
            }
            return Response(
                {"message": "User details retrieved successfully", "data": User_data},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "User not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class User_RegesterView(APIView):
    """View for User registration with file uploads.
    Handles User creation and VAT certificate file uploads.
    """

    def post(self, request):
        """
        This endpoint accepts two formats:
        
        1. JSON format with multipart/form-data:
        - company_data: JSON string containing user information
        - vat_files: Multiple files as BLOB data
        
        2. Direct form fields:
        - username, password, name, etc. as individual form fields
        - files: Multiple files as BLOB data
        
        Example form-data (direct fields):
        username: "company123"
        password: "123"
        name: "Company Name Ltd"
        address: "123 Business St"
        phone_number: "+1234567890"
        email: "contact@company.com"
        website: "www.company.com"
        CR_number: "CR123456"
        files: [file1.pdf, file2.pdf] (as BLOB data)
        """
        try:
            # Check if we have company_data as JSON or individual fields
            company_data = request.data.get("company_data")
            
            # If company_data is not provided, construct it from individual fields
            if not company_data:
                company_data = {
                    "username": request.data.get("username"),
                    "password": request.data.get("password"),
                    "name": request.data.get("name"),
                    "email": request.data.get("email"),
                    "address": request.data.get("address"),
                    "phone_number": request.data.get("phone_number"),
                    "website": request.data.get("website"),
                    "CR_number": request.data.get("CR_number")
                }
            elif isinstance(company_data, str):
                # Parse the company_data JSON string if provided
                import json
                company_data = json.loads(company_data)
            
            # If still no company_data, return error
            if not company_data:
                return Response(
                    {"error": "User data is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate required fields
            required_fields = ["username", "password", "name", "email"]
            for field in required_fields:
                if not company_data.get(field):
                    return Response(
                        {"error": f"{field} is required."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Check if username already exists
            if User.objects.filter(username=company_data.get("username")).exists():
                return Response(
                    {"error": "Username already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if email already exists
            if User.objects.filter(email=company_data.get("email")).exists():
                return Response(
                    {"error": "Email already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create the user with create_user to properly hash the password
            user = User.objects.create_user(
                username=company_data.get("username"),
                password=company_data.get("password"),  # This will be hashed automatically
                email=company_data.get("email"),
                name=company_data.get("name"),
            )

            # Update additional fields
            user.address = company_data.get("address", "")
            user.phone_number = company_data.get("phone_number", "")
            user.website = company_data.get("website", "")
            user.CR_number = company_data.get("CR_number", "")
            user.Is_Accepted = None  # Default to not accepted
            user.save()

            # Handle file uploads as BLOB data - try both vat_files and files
            vat_files = request.FILES.getlist("vat_files") or request.FILES.getlist("files")
            uploaded_files = []

            if vat_files:
                for file in vat_files:
                    try:
                        # Validate file size (e.g., max 10MB)
                        max_file_size = 10 * 1024 * 1024  # 10MB
                        if file.size > max_file_size:
                            return Response(
                                {
                                    "error": f"File {file.name} is too large. Maximum size is 10MB."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Validate file type (optional - add allowed types)
                        allowed_types = [
                            "application/pdf",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application/vnd.ms-excel",
                            "image/jpeg",
                            "image/png",
                            "image/jpg",
                        ]
                        if file.content_type not in allowed_types:
                            return Response(
                                {
                                    "error": f"File type {file.content_type} is not allowed."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Read the file data as BLOB
                        file_data = file.read()

                        # Reset file pointer in case it's needed later
                        file.seek(0)

                        # Create the VAT certificate record with BLOB data
                        vat_cert = VAT_Certificate_Manager.objects.create(
                            User=user,
                            File_Name=file.name,
                            File_Type=file.content_type,
                            File_Size=file.size,
                            File_Data=file_data,  # Store as BLOB
                        )

                        uploaded_files.append(
                            {
                                "file_id": vat_cert.Id,
                                "file_name": file.name,
                                "file_size": file.size,
                                "file_type": file.content_type,
                            }
                        )

                    except Exception as file_error:
                        # If there's an error with a specific file, clean up and return error
                        user.delete()
                        return Response(
                            {
                                "error": f"Error processing file {file.name}: {str(file_error)}"
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            Notification.send_notification(
                message="New company registered", target_type="SUPER"
            )
            Notification.send_notification(
                message=f"Welcome {user.username}, your account is under review.",
                target_type="SPECIFIC",
                user=user,
            )
            return Response(
                {
                    "message": "Company registered successfully.",
                    "User_Id": user.User_Id,
                    "data": {
                        "uploaded_files": uploaded_files,
                        "files_count": len(uploaded_files),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid JSON format in company_data."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Registration failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_All_UsersView(APIView):
    """View to delete all users."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def delete(self, request):
        try:
            User.objects.all().delete()
            return Response({"message": "All users deleted successfully."}, status=204)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class Get_Admin_Types(APIView):
    """View to get all admin types."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def get(self, request):
        try:
            admin_types = [e.value for e in User.ADMIN_TYPES]  # Return string values
            return Response(
                {"message": "Admin types retrieved successfully.", "data": admin_types},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class Create_Super_User(APIView):
    """View to create a superuser."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def post(self, request):
        try:
            try:
                admin_type = AdminType(request.data.get("admin_type", None))
            except ValueError:
                admin_type = None  # or handle the error as you wish
            username = request.data.get("username")
            email = request.data.get("email")
            password = request.data.get("password")
            print("Creating superuser with data:", username, email, password)
            if not username or not email or not password:
                return Response(
                    {"error": "Username, email, and password are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if admin_type == AdminType.TECHNICAL:
                user = User.objects.create_technical_admin(
                username=username,
                email=email,
                password=password)
            elif admin_type == AdminType.COMMERCIAL:
                user = User.objects.create_commercial_admin(
                username=username,
                email=email,
                password=password)
            else:
                user = User.objects.create_superuser(
                    username=username, email=email, password=password
                )
            Notification.send_notification(
                message="New superuser created", target_type="SUPER"
            )
            return Response(
                {"message": "Superuser created successfully.", "User_Id": user.User_Id},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class Account_Request_Respond(APIView):
    """View to respond to account requests."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def post(self, request):
        try:
            User_Id = request.data.get("User_Id")
            response = request.data.get("response")  # Accept or Reject

            user = User.objects.get(User_Id=User_Id)
            if response == "Accept":
                user.Is_Accepted = True
            elif response == "Reject":
                user.Is_Accepted = False
            else:
                return Response(
                    {"error": "Invalid response. Use 'Accept' or 'Reject'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.save()
            Notification.send_notification(
                message=f"Your account has been {response.lower()}ed",
                target_type="SPECIFIC",
                user=user,
            )
            return Response(
                {"message": f"User {response.lower()}ed successfully."}, status=200
            )
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Get_All_Pending_Users(APIView):
    """View to get all pending users with pagination and search."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def get(self, request):
        try:
            # Get search parameters
            search_query = request.query_params.get('search', '')
            
            # Apply search filter if provided
            pending_users = User.objects.filter(Is_Accepted=None)
            if search_query:
                pending_users = pending_users.filter(
                    Q(username__icontains=search_query) | 
                    Q(name__icontains=search_query) | 
                    Q(email__icontains=search_query)
                )
                
            # Apply pagination
            paginator = StandardPagination()
            paginated_users = paginator.paginate_queryset(pending_users, request)
            
            # Prepare data
            pending_user_data = [
                {
                    "User_Id": user.User_Id,
                    "username": user.username,
                    "name": user.name,
                    "email": user.email,
                }
                for user in paginated_users
            ]
            
            # Return paginated response
            return paginator.get_paginated_response(pending_user_data)
            
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Get_UserFile_Data(APIView):
    """View to retrieve file data for a specific VAT certificate by ID."""

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")

            if not file_id:
                return Response(
                    {"message": "file_id parameter is required.", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            vat_certificate = VAT_Certificate_Manager.objects.get(Id=file_id)

            # For file downloads, we need to handle differently since we're returning binary data
            # We'll return metadata in a standard format when requested
            if request.query_params.get("metadata_only") == "true":
                file_metadata = {
                    "file_id": vat_certificate.Id,
                    "file_name": vat_certificate.File_Name,
                    "file_type": vat_certificate.File_Type,
                    "file_size": vat_certificate.File_Size,
                    "uploaded_at": vat_certificate.Uploaded_At,
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
                file_stream = io.BytesIO(vat_certificate.File_Data)
                response = FileResponse(
                    file_stream,
                    content_type=vat_certificate.File_Type,
                    as_attachment=True,
                    filename=vat_certificate.File_Name,
                )
                return response

        except VAT_Certificate_Manager.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": f"Error retrieving file: {str(e)}", "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class Add_UserFileView(APIView):
    """View to add multiple VAT certificate files for a user.

    Example request:
    POST /api/User/add_user_file/
    Content-Type: multipart/form-data

    Form data:
    {
        "files": [file1.pdf, file2.pdf, file3.pdf]  # Multiple file upload
    }
    """

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def post(self, request):
        try:
            user = request.user  # Get the authenticated user
            files = request.FILES.getlist("files")
            if not files:
                return Response(
                    {"message": "At least one file is required.", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            uploaded_files = []
            import datetime
            import os

            for file in files:
                # Split the filename into name and extension
                file_name, file_extension = os.path.splitext(file.name)

                # Add current timestamp to ensure uniqueness
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{file_name}_{timestamp}{file_extension}"

                # Create a new VAT certificate record
                vat_cert = VAT_Certificate_Manager.objects.create(
                    User=user,
                    File_Name=unique_filename,  # Use the unique filename
                    File_Type=file.content_type,
                    File_Size=file.size,
                    File_Data=file.read(),
                )

                uploaded_files.append(
                    {
                        "file_id": vat_cert.Id,
                        "file_name": unique_filename,
                        "original_filename": file.name,
                        "file_type": file.content_type,
                        "file_size": file.size,
                    }
                )
            # Send notification for new file uploads
            Notification.send_notification(
                message=f"{len(uploaded_files)} new file(s) uploaded by {user.username}",
                target_type="SPECIFIC",
                user=user,
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

        except User.DoesNotExist:
            return Response(
                {"message": "User not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []}, status=status.HTTP_400_BAD_REQUEST
            )


class Delete_UserFileView(APIView):
    """View to delete a VAT certificate file by ID."""

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def delete(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id parameter is required.", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            vat_certificate = VAT_Certificate_Manager.objects.get(
                Id=file_id, User=request.user
            )
            vat_certificate.delete()
            # Send notification for file deletion
            Notification.send_notification(
                message=f"File {vat_certificate.File_Name} deleted by {request.user.username}",
                target_type="SPECIFIC",
                user=request.user,
            )
            return Response(
                {"message": "File deleted successfully.", "data": {"file_id": file_id}},
                status=status.HTTP_200_OK,
            )
        except VAT_Certificate_Manager.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []}, status=status.HTTP_400_BAD_REQUEST
            )


class Delete_UserView(APIView):
    """View to delete a user by ID."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def delete(self, request):
        try:
            User_Id = request.data.get("User_Id")
            if not User_Id:
                return Response(
                    {"message": "User_Id is required.", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.get(User_Id=User_Id)
            user.delete()
            # Send notification for user deletion
            Notification.send_notification(
                message=f"User {user.username} deleted by {request.user.username}",
                target_type="SUPER",
            )
            return Response(
                {"message": "User deleted successfully.", "data": {"user_id": User_Id}},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "User not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []}, status=status.HTTP_400_BAD_REQUEST
            )


class Update_UserView(APIView):
    """View to update user details."""

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def put(self, request):
        try:
            # Fix the superuser check
            if request.user.is_superuser:
                User_Id = request.data.get("User_Id", request.user.User_Id)
                user = User.objects.get(User_Id=User_Id)
            else:
                user = request.user

            # Update user fields
            user.username = request.data.get("username", user.username)
            user.name = request.data.get("name", user.name)
            user.address = request.data.get("address", user.address)
            user.phone_number = request.data.get("phone_number", user.phone_number)
            user.email = request.data.get("email", user.email)
            user.website = request.data.get("website", user.website)
            user.CR_number = request.data.get("CR_number", user.CR_number)
            
            # Allow superusers to update the Is_Accepted status
            if request.user.is_superuser and "Is_Accepted" in request.data:
                user.Is_Accepted = request.data.get("Is_Accepted")

            # Save the updated user
            user.save()

            # Return updated user data
            user_data = {
                "User_Id": user.User_Id,
                "username": user.username,
                "name": user.name,
                "address": user.address,
                "phone_number": user.phone_number,
                "email": user.email,
                "website": user.website,
                "CR_number": user.CR_number,
                "Is_Accepted": user.Is_Accepted  # Include Is_Accepted in response
            }
            # send notification for user update
            Notification.send_notification(
                message=f"User {user.username} profile updated",
                target_type="SPECIFIC",
                user=user,
            )
            return Response(
                {"message": "User updated successfully.", "data": user_data},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "User not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []}, status=status.HTTP_400_BAD_REQUEST
            )


