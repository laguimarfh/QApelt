from django.db import models

class CarData(models.Model):
    latest = models.CharField(max_length=50)
    primer = models.CharField(max_length=50)
    url = models.URLField()
    date = models.DateField()
    body_no = models.CharField(max_length=50)
    colour_code = models.CharField(max_length=10)
    
    # Dynamically added columns for points
    for i in range(1, 173):
        locals()[f'{i}C'] = models.CharField(max_length=10, null=True, blank=True)
        locals()[f'{i}B'] = models.CharField(max_length=10, null=True, blank=True)
        locals()[f'{i}P'] = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.body_no
