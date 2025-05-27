from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from User.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate

# Create your views here.


class RejesterView(APIView):
    """View for user registration.
    Handles user creation with username, email, and password.
    """

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")

        if not username or not email or not password:
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.object.create_user(
                username=username, email=email, password=password
            )
            Token = RefreshToken.for_user(user)  # Generate refresh token for the user
            return Response(
                {
                    "message": "User created successfully.",
                    "Token": str(Token.access_token),
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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


class UpdateuserInfo(APIView):
    """View for updating user information.
    Requires authentication and allows updating username, email, and password.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")
        user.first_name = first_name
        user.last_name = last_name

        user.save()
        return Response(
            {"message": "User information updated successfully."},
            status=status.HTTP_200_OK,
        )
