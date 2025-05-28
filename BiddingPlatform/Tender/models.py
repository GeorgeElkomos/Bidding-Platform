from django.db import models


class Tender_Files(models.Model):
    file_id = models.AutoField(primary_key=True)
    tender = models.ForeignKey(
        "Tender", on_delete=models.CASCADE, related_name="files", db_column="tender_id"
    )
    file_name = models.CharField(max_length=100, unique=True)
    file_type = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    file_data = models.BinaryField()
    Uploaded_At = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


# Create your models here.
class Tender(models.Model):
    tender_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "User.User",
        on_delete=models.SET_NULL,  # Changed from CASCADE to SET_NULL
        null=True,  # Required for SET_NULL
        blank=True,  # Allow blank in forms
        related_name="tenders",
        db_column="created_by_id",
    )
    budget = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return self.title
