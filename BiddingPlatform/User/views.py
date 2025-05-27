from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
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
        print("Hello")
        users = User.objects.get(
            is_superuser=False
        )  # Assuming companies are not superusers
        print(len(users))
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

            # Create the user
            user = User.objects.create(
                username=company_data.get("username"),
                password=company_data.get("password"),
                name=company_data.get("name"),
                address=company_data.get("address", ""),
                phone_number=company_data.get("phone_number", ""),
                email=company_data.get("email", ""),
                website=company_data.get("website", ""),
                CR_number=company_data.get("CR_number", ""),
                Is_Accepted=None,  # Default to not accepted
            )

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
