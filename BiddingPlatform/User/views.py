from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from Tender.permissions import IsSuperUser
from User.models import User, VAT_Certificate_Manager
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate

# Create your views here.


class LoginView(APIView):
    """View for user login.
    Handles user authentication and returns a JWT token.
    """

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = authenticate(request, username=username, password=password)
            if user is None:
                return Response(
                    {"error": "Invalid credentials."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if user.Is_Accepted != True:
                return Response(
                    {"error": "Your account is not accepted yet."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            print("User authenticated:", user.email)
            Token = RefreshToken.for_user(user)  # Generate refresh token for the user
            return Response(
                {
                    "message": "Login successful.",
                    "Token": str(Token.access_token),
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )


class List_UserView(APIView):
    """View to list all companies."""

    def get(self, request):
        users = User.objects.filter(
            is_superuser=False
        )  # Assuming companies are not superusers
        user_data = [
            {
                "user_Id": user.User_Id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
            }
            for user in users
        ]
        return Response(user_data, status=200)


class UserDetailView(APIView):
    """View to retrieve details of a specific User by ID."""

    def get(self, request):
        try:
            User_id = request.query_params.get("User_Id")
            user = User.objects.get(User_Id=User_id)
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
            return Response(User_data, status=200)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)


class User_RegesterView(APIView):
    """View for User registration with file uploads.
    Handles User creation and VAT certificate file uploads.
    """

    def post(self, request):
        """
        This endpoint expects form-data with:
        - company_data: JSON string containing user information
        - vat_files: Multiple files

        Example form-data:
        company_data: {
            "username": "company123",
            "password": "123",
            "name": "Company Name Ltd",
            "address": "123 Business St",
            "phone_number": "+1234567890",
            "email": "contact@company.com",
            "website": "www.company.com",
            "CR_number": "CR123456"
        }
        vat_files: [file1.pdf, file2.xlsx, file3.pdf]
        """
        try:
            # Parse the company_data JSON string
            company_data = request.data.get("company_data")
            if isinstance(company_data, str):
                import json

                company_data = json.loads(company_data)

            # Create the user with create_user to properly hash the password
            user = User.objects.create_user(
                username=company_data.get("username"),
                password=company_data.get(
                    "password"
                ),  # This will be hashed automatically
                email=company_data.get("email", ""),
                name=company_data.get("name"),
            )

            # Update additional fields
            user.address = company_data.get("address", "")
            user.phone_number = company_data.get("phone_number", "")
            user.website = company_data.get("website", "")
            user.CR_number = company_data.get("CR_number", "")
            user.Is_Accepted = None  # Default to not accepted
            user.save()
            # Handle file uploads
            vat_files = request.FILES.getlist("vat_files")
            if vat_files:
                for file in vat_files:
                    # Read the file data
                    file_data = file.read()

                    # Create the attachment record
                    VAT_Certificate_Manager.objects.create(
                        User=user,
                        File_Name=file.name,
                        File_Type=file.content_type,
                        File_Size=file.size,
                        File_Data=file_data,
                    )

            return Response(
                {
                    "message": "Company registered successfully.",
                    "User_Id": user.User_Id,
                },
                status=201,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Delete_All_UsersView(APIView):
    """View to delete all users."""

    def delete(self, request):
        try:
            User.objects.all().delete()
            return Response({"message": "All users deleted successfully."}, status=204)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Create_Super_User(APIView):
    """View to create a superuser."""

    def post(self, request):
        try:
            username = request.data.get("username")
            email = request.data.get("email")
            password = request.data.get("password")
            print("Creating superuser with data:", username, email, password)
            if not username or not email or not password:
                return Response(
                    {"error": "Username, email, and password are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_superuser(
                username=username, email=email, password=password
            )
            return Response(
                {"message": "Superuser created successfully.", "User_Id": user.User_Id},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class Account_Request_Respond(APIView):
    """View to respond to account requests."""

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
            return Response(
                {"message": f"User {response.lower()}ed successfully."}, status=200
            )
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Get_All_Pending_Users(APIView):
    """View to get all pending users."""

    def get(self, request):
        try:
            pending_users = User.objects.filter(Is_Accepted=None)
            pending_user_data = [
                {
                    "User_Id": user.User_Id,
                    "username": user.username,
                    "name": user.name,
                    "email": user.email,
                }
                for user in pending_users
            ]
            return Response(pending_user_data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Get_UserFile_Data(APIView):
    """View to retrieve file data for a specific VAT certificate by ID."""

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")
            vat_certificate = VAT_Certificate_Manager.objects.get(Id=file_id)
            file_data = vat_certificate.File_Data

            # Return the file data as a binary response
            response = Response(file_data, content_type=vat_certificate.File_Type)
            response["Content-Disposition"] = (
                f'attachment; filename="{vat_certificate.File_Name}"'
            )
            return response
        except VAT_Certificate_Manager.DoesNotExist:
            return Response({"error": "File not found."}, status=404)


class Add_UserFileView(APIView):
    """View to add a VAT certificate file for a user.

    Example request:
    POST /api/add-user-file/
    Content-Type: multipart/form-data

    Form data:
    {
        "file": [file1.pdf]  # Single file upload
    }
    """

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def post(self, request):
        try:
            user = request.user  # Get the authenticated user
            files = request.FILES.get("file")
            if not file:
                return Response(
                    {"error": "file is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for file in files:
                # Create a new VAT certificate record
                VAT_Certificate_Manager.objects.create(
                    User=user,
                    File_Name=file.name,
                    File_Type=file.content_type,
                    File_Size=file.size,
                    File_Data=file.read(),
                )
            return Response({"message": "File uploaded successfully."}, status=201)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Delete_UserFileView(APIView):
    """View to delete a VAT certificate file by ID."""

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def delete(self, request):
        try:
            file_id = request.query_params.get("file_id")
            vat_certificate = VAT_Certificate_Manager.objects.get(
                Id=file_id, User=request.user
            )
            vat_certificate.delete()
            return Response({"message": "File deleted successfully."}, status=204)
        except VAT_Certificate_Manager.DoesNotExist:
            return Response({"error": "File not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Delete_UserView(APIView):
    """View to delete a user by ID."""

    permission_classes = [
        IsAuthenticated,
        IsSuperUser,
    ]  # Ensure the user is authenticated

    def delete(self, request):
        try:
            User_Id = request.data.get("User_Id")
            user = User.objects.get(User_Id=User_Id)
            user.delete()
            return Response({"message": "User deleted successfully."}, status=204)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class Update_UserView(APIView):
    """View to update user details."""

    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def put(self, request):
        try:
            if IsSuperUser:
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

            # Save the updated user
            user.save()
            return Response({"message": "User updated successfully."}, status=200)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
