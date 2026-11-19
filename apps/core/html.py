"""Foydalanuvchi kiritgan HTML'ni tozalash (stored XSS himoyasi)."""
import nh3

# TipTap (RichTextEditor: StarterKit, Underline, TextAlign, TaskList, TaskItem) chiqaradigan teglar
ALLOWED_TAGS = {
    "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "strike",
    "ul", "ol", "li", "h1", "h2", "h3", "h4", "blockquote", "code", "pre",
    "a", "span", "mark", "div", "label", "input",
}
_ALIGN = {"style"}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "target"},
    "p": _ALIGN, "h1": _ALIGN, "h2": _ALIGN, "h3": _ALIGN, "h4": _ALIGN,
    "span": {"style"},
    "ul": {"data-type"},
    "li": {"data-type", "data-checked"},
    "input": {"type", "checked"},
}
# style — faqat shu xususiyatlar qoladi (qolgani, masalan url(...), olib tashlanadi)
ALLOWED_STYLE_PROPERTIES = {"text-align", "color"}
# input faqat o'chirilgan checkbox bo'la oladi (TaskList belgisi)
FORCED_ATTRIBUTE_VALUES = {"input": {"type": "checkbox", "disabled": "disabled"}}


def clean_html(value):
    """Ruxsat etilmagan teg/atribut/skript/hodisa ishlovchilarini olib tashlaydi."""
    if not value:
        return value
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        filter_style_properties=ALLOWED_STYLE_PROPERTIES,
        set_tag_attribute_values=FORCED_ATTRIBUTE_VALUES,
    )
