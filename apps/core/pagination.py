from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Standart paginatsiya:
    - Sukut bo'yicha 20 ta element
    - ?page_size=N orqali o'zgartirish mumkin (max 200)
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200
