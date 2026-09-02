"""Country metadata used by the account UI and phone normalization.

The calling code is application-owned; clients never submit it directly.
"""

COUNTRIES = (
    # Keep compatibility with the existing 10-digit example used by BOTEN,
    # while accepting the standard 11-digit mainland mobile number.
    ("CN", "中国", "China", "+86", 10, 11),
    ("US", "美国", "United States", "+1", 10, 10),
    ("CA", "加拿大", "Canada", "+1", 10, 10),
    ("GB", "英国", "United Kingdom", "+44", 7, 15),
    ("DE", "德国", "Germany", "+49", 7, 15),
    ("FR", "法国", "France", "+33", 8, 15),
    ("IT", "意大利", "Italy", "+39", 6, 15),
    ("ES", "西班牙", "Spain", "+34", 9, 15),
    ("NL", "荷兰", "Netherlands", "+31", 8, 15),
    ("CH", "瑞士", "Switzerland", "+41", 8, 15),
    ("SE", "瑞典", "Sweden", "+46", 7, 15),
    ("RU", "俄罗斯", "Russia", "+7", 10, 10),
    ("AE", "阿联酋", "United Arab Emirates", "+971", 7, 15),
    ("SA", "沙特阿拉伯", "Saudi Arabia", "+966", 8, 15),
    ("IN", "印度", "India", "+91", 10, 10),
    ("JP", "日本", "Japan", "+81", 9, 15),
    ("KR", "韩国", "South Korea", "+82", 9, 15),
    ("SG", "新加坡", "Singapore", "+65", 8, 8),
    ("MY", "马来西亚", "Malaysia", "+60", 7, 15),
    ("TH", "泰国", "Thailand", "+66", 8, 15),
    ("VN", "越南", "Vietnam", "+84", 8, 15),
    ("ID", "印度尼西亚", "Indonesia", "+62", 8, 15),
    ("AU", "澳大利亚", "Australia", "+61", 9, 15),
    ("NZ", "新西兰", "New Zealand", "+64", 8, 15),
    ("BR", "巴西", "Brazil", "+55", 10, 11),
    ("MX", "墨西哥", "Mexico", "+52", 10, 10),
    ("ZA", "南非", "South Africa", "+27", 9, 15),
    ("TR", "土耳其", "Turkey", "+90", 10, 10),
)

BY_ISO = {item[0]: item for item in COUNTRIES}

def get_country(country: str):
    return BY_ISO.get((country or "").upper())

def public_countries(language: str = "zh"):
    return [
        {"code": iso, "name": en if language == "en" else zh, "name_zh": zh, "name_en": en, "calling_code": calling}
        for iso, zh, en, calling, _minimum, _maximum in COUNTRIES
    ]
