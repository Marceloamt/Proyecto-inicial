from django.db import models

# Create your models here.
class Myapp(models.Model):
    field1 = models.CharField(max_length=255)
    field2 = models.CharField(max_length=255)