from django.db import transaction
from django.utils import timezone
from pypinyin import lazy_pinyin, Style


def chinese_to_initials(chinese_text):
    """
    Convert Chinese text to Pinyin initials.
    Example: "请购单" -> "QGD"
    """
    initials = lazy_pinyin(chinese_text, style=Style.FIRST_LETTER)
    return ''.join(initial.upper() for initial in initials)


@transaction.atomic
def get_next_sequence(date):
    """
    Get next sequence number for the given date (thread-safe).
    Uses database row-level locking to ensure uniqueness.
    """
    from workflows.models import DailySequence
    
    # Use select_for_update for row-level locking
    seq, created = DailySequence.objects.select_for_update().get_or_create(
        date=date,
        defaults={'sequence': 0}
    )
    
    # Increment sequence
    seq.sequence += 1
    seq.save()
    
    return seq.sequence


def generate_t_tag(query_type_chinese, target_dept_code, date=None):
    """
    Generate a unique ticket tag/identifier.
    
    Args:
        query_type_chinese (str): Chinese query type (e.g., "请购单")
        target_dept_code (str): Target department code (e.g., "PD", "HRTJ")
        date (datetime.date, optional): Date for the tag. Defaults to today.
    
    Returns:
        str: Ticket tag in format "TYPE-DEPT-YYMMDD-SEQ"
             Example: "QGD-PD-260122-001"
    """
    if date is None:
        date = timezone.now().date()
    
    # Convert Chinese to initials
    type_code = chinese_to_initials(query_type_chinese)
    
    # Format date as YYMMDD
    date_str = date.strftime('%y%m%d')
    
    # Get next sequence number (thread-safe)
    sequence = get_next_sequence(date)
    
    # Format sequence with leading zeros (3 digits)
    sequence_str = f"{sequence:03d}"
    
    # Combine all parts
    t_tag = f"{type_code}-{target_dept_code}-{date_str}-{sequence_str}"
    
    return t_tag
