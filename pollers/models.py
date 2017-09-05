from django.db import models
from django.db.models import Sum


class Category(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)
    position = models.IntegerField(default=0)
    is_visible = models.IntegerField(default=1)

    def __str__(self):
        return self.name


class Card(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)
    number = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return self.name


class History(models.Model):
    card = models.ForeignKey(Card, related_name='+', null=True)

    amount = models.DecimalField(max_digits=8, decimal_places=2)
    datetime = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=30, null=True, blank=True)
    details = models.CharField(max_length=30, null=True, blank=True)
    category = models.ForeignKey(Category, related_name='+', null=True)
    is_active = models.IntegerField(default=0)

    balance = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    raw_text = models.CharField(max_length=500, null=True, blank=True)

    gmail_id = models.CharField(max_length=30, null=True, blank=True)
    telegram_message_id = models.IntegerField(null=True, default=None, blank=True)

    @staticmethod
    def get_report(date_from, date_to):
        rep = History.objects \
            .values('category__name', 'category_id') \
            .filter(is_active=1, datetime__gte=date_from, datetime__lt=date_to) \
            .annotate(amount=Sum('amount')) \
            .order_by('category__position')

        return rep
