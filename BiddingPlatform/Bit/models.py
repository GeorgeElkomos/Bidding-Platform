from django.db import models


class Bit_Files(models.Model):
    file_id = models.AutoField(primary_key=True)
    bit = models.ForeignKey(
        "Bit", on_delete=models.CASCADE, related_name="files", db_column="bit_id"
    )
    # admin_type = models.CharField(max_length=50, default="bit")
    file_name = models.CharField(max_length=100)
    file_type = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    file_data = models.BinaryField()
    Uploaded_At = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


# Create your models here.
class Bit(models.Model):
    bit_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    created_by = models.ForeignKey(
        "User.User",
        on_delete=models.CASCADE,  # Changed from CASCADE to SET_NULL
        null=True,  # Required for SET_NULL
        blank=True,  # Allow blank in forms
        related_name="bits",
        db_column="created_by_id",
    )
    tender = models.ForeignKey(
        "Tender.Tender",
        on_delete=models.CASCADE,
        related_name="bits",
        db_column="tender_id",
    )
    cost = models.DecimalField(max_digits=15, decimal_places=2)
    Is_Accepted = models.BooleanField(
        default=None, blank=True, null=True
    )  # Indicates if the bit is accepted

    class Meta:
        unique_together = ('created_by', 'tender')  # Prevent multiple bids from same user for same tender

    def __str__(self):
        return self.title
