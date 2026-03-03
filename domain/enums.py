# domain/enums.py
from enum import Enum

class ApprovalCategory(Enum):
    APPROVED = "approved"
    OFF_LABEL = "off_label"