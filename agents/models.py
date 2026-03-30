from django.db import migrations, models

class InternalTask(models.Model):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=50, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title