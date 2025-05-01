from django.db import models

class Course(models.Model):
    course_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    section = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
