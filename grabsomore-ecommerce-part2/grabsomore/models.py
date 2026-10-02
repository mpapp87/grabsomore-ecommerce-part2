from django.db import models
from django.conf import settings

class ResetToken(models.Model):
    # Reference to the user who requested the password reset
    """Store a hashed, expiring, single-use password reset token."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Token string, unique to avoid duplicates
    token = models.CharField(max_length=255, unique=True)
    # When this token expires
    expiry_date = models.DateTimeField()
    # Whether this token has already been used
    used = models.BooleanField(default=False)

    def __str__(self):
        # Show a short summary for easier debugging
        """Return a readable label for this record in the admin and debugging output."""
        return f"ResetToken(user={self.user.username}, token={self.token[:10]}..., used={self.used})"
