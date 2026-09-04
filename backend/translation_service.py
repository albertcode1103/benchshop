"""Conservative local translation drafts for catalog editing.

The service intentionally returns an empty draft when a phrase cannot be
translated without leaving Chinese text behind. It never overwrites reviewed
content; the admin UI decides whether to apply each suggestion.
"""

import re
from typing import Dict


CJK_TEXT = re.compile(r"[\u3400-\u9fff]")

EXACT_TRANSLATIONS = {
    "可选配置": "Optional Configurations",
    "维修工具": "Service Tools",
    "设备附件": "Accessories",
    "颜色": "Color",
    "电机": "Motor",
    "电源": "Power Supply",
    "通道": "Channel",
    "绿色": "Green",
    "红色": "Red",
    "黑色": "Black",
    "白色": "White",
    "蓝色": "Blue",
    "黄色": "Yellow",
    "设备概况": "Overview",
    "最大转速": "Maximum Speed",
    "额定功率": "Rated Power",
    "外形尺寸": "Dimensions",
    "重量": "Weight",
    "共轨喷油器测试套件": "Common Rail Injector Test Kits",
    "HEUI 中压胎具": "HEUI Medium-Pressure Fixtures",
    "BT618机械试验台拓展功能": "BT618 Mechanical Test Bench Extensions",
    "共轨泵工装": "Common Rail Pump Fixtures",
    "单体泵泵喷嘴胎具": "Unit Pump and Unit Injector Fixtures",
    "凸轮箱扩展功能": "Cam Box Extensions",
    "设备": "Product",
    "配置": "Configuration",
    "工具": "Tool",
    "附件": "Accessory",
}

TOKEN_TRANSLATIONS = (
    ("共轨喷油器", "Common Rail Injector"),
    ("共轨泵", "Common Rail Pump"),
    ("试验台", "Test Bench"),
    ("测试套件", "Test Kit"),
    ("测试", "Test"),
    ("工装", "Fixture"),
    ("胎具", "Fixture"),
    ("扩展功能", "Extension"),
    ("适配器", "Adapter"),
    ("电机", "Motor"),
    ("电源", "Power Supply"),
    ("通道", "Channel"),
    ("内置", "Built-in"),
    ("外置", "External"),
    ("变压器", "Transformer"),
    ("伺服", "Servo"),
    ("机械", "Mechanical"),
    ("免费", "Included"),
    ("绿色", "Green"),
    ("红色", "Red"),
)


def translation_draft(text: str) -> Dict[str, object]:
    source = str(text or "").strip()
    if not source:
        return {"source": source, "draft": "", "complete": True}
    if not CJK_TEXT.search(source):
        return {"source": source, "draft": source, "complete": True}
    exact = EXACT_TRANSLATIONS.get(source)
    if exact:
        return {"source": source, "draft": exact, "complete": True}
    draft = source
    for chinese, english in TOKEN_TRANSLATIONS:
        draft = draft.replace(chinese, " {} ".format(english))
    draft = " ".join(draft.split())
    if CJK_TEXT.search(draft):
        return {"source": source, "draft": "", "complete": False}
    return {"source": source, "draft": draft, "complete": True}
