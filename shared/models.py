from django.db import models
import uuid

# Create your models here.
class BaseModel(models.Model):
    id = models.UUIDField(unique=True, default=uuid.uuid4, editable=True, primary_key=True)
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True