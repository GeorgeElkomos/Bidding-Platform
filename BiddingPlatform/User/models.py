from enum import Enum
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
    File_Name = models.CharField(max_length=100)
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
    
    def create_technical_admin(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("Is_Accepted", True)
        extra_fields.setdefault("_admin_type", "technical")
        return self.create_user(username, email, password, **extra_fields)
    
    def create_commercial_admin(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("Is_Accepted", True)
        extra_fields.setdefault("_admin_type", "commercial")
        return self.create_user(username, email, password, **extra_fields)


class AdminType(Enum):
    TECHNICAL = 'technical'
    COMMERCIAL = 'commercial'
    
    @classmethod
    def choices(cls):
        return [(tag.value, tag.name.replace('_', ' ').title() + ' Admin') for tag in cls]

class User(AbstractBaseUser, PermissionsMixin):
    User_Id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(unique=True, blank=True)
    website = models.URLField(blank=True)
    CR_number = models.CharField(
        max_length=50, blank=True
    ) # Commercial Registration number
    
    Is_Accepted = models.BooleanField(
        default=None, blank=True, null=True
    )  # Indicates if the company is accepted
    
    is_superuser = models.BooleanField(default=False)
    ADMIN_TYPES = [e for e in AdminType]
    _admin_type = models.CharField(
        max_length=20,
        choices=AdminType.choices(),
        default=None,
        blank=True,
        db_column='admin_type'
    )
    objects = User_Manager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "name"]

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "XX_User"
        verbose_name_plural = "XX_Users"
        db_table = "xx_user"
        
        
    @property
    def admin_type(self):
        if self._admin_type:
            return AdminType(self._admin_type)
        return None

    @admin_type.setter
    def admin_type(self, value):
        if isinstance(value, AdminType):
            self._admin_type = value.value
        elif value is None:
            self._admin_type = None
        else:
            raise ValueError("admin_type must be an AdminType enum or None")


class NotificationReadStatus(models.Model):
    """
    Tracks the read status of notifications for each user.
    This allows for proper handling of broadcast notifications where each user has their own read status.
    """

    Id = models.AutoField(primary_key=True)
    User = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_statuses",
        db_column="User_Id",
    )
    Notification = models.ForeignKey(
        "Notification",
        on_delete=models.CASCADE,
        related_name="read_statuses",
        db_column="Notification_Id",
    )
    Is_Read = models.BooleanField(default=False)
    Read_At = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification Read Status"
        verbose_name_plural = "Notification Read Statuses"
        db_table = "notification_read_status"
        unique_together = (
            "User",
            "Notification",
        )  # Each user can have only one read status per notification

    def __str__(self):
        return f"{self.User.username} - {self.Notification.Message[:20]} - {'Read' if self.Is_Read else 'Unread'}"


class Notification(models.Model):
    NOTIFICATION_TARGETS = [
        ("ALL", "All Users"),
        ("SUPER", "Super Users"),
        ("NORMAL", "Normal Users"),
        ("SPECIFIC", "Specific User"),
    ]

    Id = models.AutoField(primary_key=True)
    User = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="User_Id",
        null=True,  # Allow null for broadcast notifications
        blank=True,  # Allow blank for broadcast notifications
    )
    Message = models.TextField()
    Created_At = models.DateTimeField(auto_now_add=True)
    Target_Type = models.CharField(
        max_length=10, choices=NOTIFICATION_TARGETS, default="SPECIFIC"
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        db_table = "notification"

    def __str__(self):
        if self.Target_Type != "SPECIFIC":
            return f"Broadcast Notification to {self.Target_Type}: {self.Message[:20]}"
        return f"Notification for {self.User.username}: {self.Message[:20]}"

    def __init__(self, *args, **kwargs):
        self._allow_save = False
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self._allow_save:
            raise ValueError(
                "Direct saving of notifications is not allowed. "
                "Please use Notification.send_notification() method instead."
            )
        super().save(*args, **kwargs)

    @classmethod
    def mark_as_read(cls, notification_id, user):
        """
        Mark a specific notification as read for a user.

        Args:
            notification_id (int): The ID of the notification to mark as read
            user: The user for whom to mark the notification as read

        Returns:
            bool: True if marked as read successfully, False otherwise

        Example:
            # Mark a specific notification as read
            success = Notification.mark_as_read(notification_id=1, user=some_user)
        """
        from django.utils import timezone

        try:
            notification = cls.objects.get(Id=notification_id)
            NotificationReadStatus.objects.update_or_create(
                User=user,
                Notification=notification,
                defaults={"Is_Read": True, "Read_At": timezone.now()},
            )
            return True
        except Exception:
            return False

    @classmethod
    def mark_multiple_as_read(cls, user):
        """
        Mark all unread notifications as read for a specific user using a single database query.

        Args:
            user: The user for whom to mark all notifications as read

        Returns:
            bool: True if the update was successful, False otherwise

        Example:
            # Mark all unread notifications as read for a user
            user = User.objects.get(username='john_doe')
            success = Notification.mark_multiple_as_read(user)
        """
        from django.utils import timezone

        try:
            # Get or create read statuses for all notifications that don't have a status yet
            existing_status_notifications = NotificationReadStatus.objects.filter(
                User=user
            ).values_list("Notification_id", flat=True)

            # Find notifications that don't have a read status for this user
            notifications_without_status = cls.objects.exclude(
                Id__in=existing_status_notifications
            )

            # Create read statuses in bulk for notifications that don't have one
            if notifications_without_status.exists():
                new_statuses = [
                    NotificationReadStatus(
                        User=user,
                        Notification_id=notification.Id,
                        Is_Read=True,
                        Read_At=timezone.now(),
                    )
                    for notification in notifications_without_status
                ]
                NotificationReadStatus.objects.bulk_create(new_statuses)

            # Update all existing unread statuses to read
            updated = NotificationReadStatus.objects.filter(
                User=user, Is_Read=False
            ).update(Is_Read=True, Read_At=timezone.now())

            return True
        except Exception:
            return False

    @classmethod
    def send_notification(cls, message, target_type="SPECIFIC", user=None):
        """
        Send and save a notification to the database and broadcast it via WebSocket if recipients are connected.

        Args:
            message (str): The notification message
            target_type (str): The type of notification target (ALL, SUPER, NORMAL, or SPECIFIC)
            user (User, optional): The specific user to send the notification to. Required if target_type is SPECIFIC.

        Returns:
            bool: True if the notification was successfully created and saved

        Example:
            # Send to specific user
            success = Notification.send_notification("Message", "SPECIFIC", user)

            # Send to all users
            success = Notification.send_notification("Message", "ALL")
        """
        from BiddingPlatform.consumers import (
            notify_users,
            notify_users_by_id,
            active_connections,
        )

        print(
            f"Sending notification: {message}, Target Type: {target_type}, User: {user}"
        )
        if target_type == "SPECIFIC":
            if user is None:
                raise ValueError("User must be provided for specific notifications")

        try:  # Create and save the notification
            notification = cls(
                Message=message,
                Target_Type=target_type,
                User=user if target_type == "SPECIFIC" else None,
            )
            notification._allow_save = True
            notification.save()
            notification._allow_save = False

            # Create read status records for target users
            if target_type == "SPECIFIC":
                NotificationReadStatus.objects.create(
                    User=user, Notification=notification
                )
                # Send WebSocket notification to specific user if connected
                if user.User_Id in active_connections:
                    notify_users_by_id(message, [user.User_Id])
            else:
                # Get target users based on notification type
                if target_type == "ALL":
                    users = User.objects.all()
                    # Broadcast to all users via WebSocket only if there are active connections
                    if active_connections:
                        notify_users(message)
                elif target_type == "SUPER":
                    users = User.objects.filter(is_superuser=True)
                    # Send to connected superusers via WebSocket
                    super_user_ids = users.values_list("User_Id", flat=True)
                    connected_super_users = [
                        uid for uid in super_user_ids if uid in active_connections
                    ]
                    if connected_super_users:
                        notify_users_by_id(message, connected_super_users)
                else:  # NORMAL
                    users = User.objects.filter(is_superuser=False)
                    # Send to connected normal users via WebSocket
                    normal_user_ids = users.values_list("User_Id", flat=True)
                    connected_normal_users = [
                        uid for uid in normal_user_ids if uid in active_connections
                    ]
                    if connected_normal_users:
                        notify_users_by_id(message, connected_normal_users)

                # Bulk create read status records for all target users
                read_statuses = [
                    NotificationReadStatus(User=u, Notification=notification)
                    for u in users
                ]
                NotificationReadStatus.objects.bulk_create(read_statuses)

            return True
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return False
