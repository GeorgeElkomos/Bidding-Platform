from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)


class VAT_Certificate_Manager(models.Model):
    Id = models.AutoField(primary_key=True)
    User = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="vat_certificates",
        db_column="User_Id",
    )
    File_Name = models.CharField(max_length=100, unique=True)
    File_Type = models.CharField(max_length=255)
    File_Size = models.PositiveIntegerField()
    File_Data = models.BinaryField()
    Uploaded_At = models.DateTimeField(auto_now_add=True)


class User_Manager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("Is_Accepted", True)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    User_Id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(unique=True, blank=True)
    website = models.URLField(blank=True)
    CR_number = models.CharField(
        max_length=50, blank=True
    )  # Commercial Registration number

    Is_Accepted = models.BooleanField(
        default=None, blank=True, null=True
    )  # Indicates if the company is accepted
    is_superuser = models.BooleanField(default=False)

    objects = User_Manager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "name"]

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "XX_User"
        verbose_name_plural = "XX_Users"
        db_table = "xx_user"
