"""Stable account-domain errors shared by API validation and UI translation."""

from typing import Any, Dict, Optional


ACCOUNT_ERROR_MESSAGES = {
    "ACCOUNT_NOT_FOUND": {"zh-CN": "账号不存在或已被移除", "en": "The account no longer exists"},
    "ACCOUNT_EMAIL_INVALID": {"zh-CN": "邮箱格式无效", "en": "Enter a valid email address"},
    "ACCOUNT_EMAIL_DUPLICATE": {"zh-CN": "该邮箱已被其他账号使用", "en": "This email is already used by another account"},
    "ACCOUNT_PHONE_INVALID": {"zh-CN": "手机号格式或长度无效", "en": "Enter a valid phone number for the selected country"},
    "ACCOUNT_PHONE_DUPLICATE": {"zh-CN": "该手机号已被其他账号使用", "en": "This phone number is already used by another account"},
    "ACCOUNT_PHONE_COUNTRY_INVALID": {"zh-CN": "请选择有效国家", "en": "Select a valid country"},
    "ACCOUNT_CONTACT_REQUIRED": {"zh-CN": "邮箱和手机号至少保留一项", "en": "Keep at least an email address or phone number"},
    "ACCOUNT_NAME_REQUIRED": {"zh-CN": "请填写姓名", "en": "Enter a name"},
    "ACCOUNT_NAME_TOO_LONG": {"zh-CN": "姓名不能超过 100 个字符", "en": "The name cannot exceed 100 characters"},
    "ACCOUNT_PASSWORD_TOO_SHORT": {"zh-CN": "密码至少需要 8 个字符", "en": "The password must contain at least 8 characters"},
    "ACCOUNT_PASSWORD_TOO_LONG": {"zh-CN": "密码不能超过 128 个字符", "en": "The password cannot exceed 128 characters"},
    "ACCOUNT_ROLE_INVALID": {"zh-CN": "账号角色无效", "en": "Select a supported account role"},
    "ACCOUNT_SELF_DISABLE_FORBIDDEN": {"zh-CN": "不能停用当前登录账号", "en": "You cannot disable your current account"},
    "ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN": {"zh-CN": "不能修改当前登录账号的管理员角色", "en": "You cannot remove your own administrator access"},
    "ACCOUNT_SELF_ARCHIVE_FORBIDDEN": {"zh-CN": "不能归档当前登录账号", "en": "You cannot archive your current account"},
    "ACCOUNT_LAST_ADMIN_REQUIRED": {"zh-CN": "系统必须至少保留一个可用管理员账号", "en": "At least one enabled administrator account is required"},
    "ACCOUNT_SESSION_EXPIRED": {"zh-CN": "登录状态已失效，请重新登录", "en": "Your session has expired. Sign in again"},
    "ACCOUNT_PERMISSION_DENIED": {"zh-CN": "当前账号没有执行此操作的权限", "en": "Your account does not have permission to perform this action"},
    "ACCOUNT_VERSION_CONFLICT": {"zh-CN": "该账号已被其他管理员修改，请重新加载后再编辑", "en": "This account was changed by another administrator. Reload it and try again"},
    "ACCOUNT_ARCHIVED": {"zh-CN": "该账号已归档", "en": "This account is archived"},
    "ACCOUNT_NOT_ARCHIVED": {"zh-CN": "该账号未归档", "en": "This account is not archived"},
    "ACCOUNT_CURRENT_PASSWORD_INVALID": {"zh-CN": "当前密码不正确", "en": "The current password is incorrect"},
    "ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH": {"zh-CN": "两次输入的新密码不一致", "en": "The new passwords do not match"},
    "ACCOUNT_IDENTIFIER_REQUIRED": {"zh-CN": "请填写邮箱或手机号", "en": "Enter an email address or phone number"},
    "ACCOUNT_CREDENTIALS_INVALID": {"zh-CN": "邮箱、手机号或密码不正确", "en": "The email, phone number, or password is incorrect"},
    "ACCOUNT_RATE_LIMITED": {"zh-CN": "请求过于频繁，请稍后再试", "en": "Too many requests. Try again later"},
    "ACCOUNT_VALIDATION_FAILED": {"zh-CN": "请检查填写内容", "en": "Check the entered information"},
    "SERVER_UNAVAILABLE": {"zh-CN": "服务器处理失败，请稍后重试", "en": "The server could not complete the request. Try again later"},
    "SAVED_CONFIG_NOT_FOUND": {"zh-CN": "配置不存在或已被删除", "en": "Configuration not found or removed"},
    "SAVED_CONFIG_VERSION_CONFLICT": {"zh-CN": "配置已在其他窗口修改，请重新加载", "en": "Configuration changed in another window. Reload and try again"},
    "CONFIG_SELECTION_INVALID": {"zh-CN": "部分选项已不可用，请重新选择", "en": "Some options are no longer available. Review your selection"},
    "BATCH_SELECTION_EMPTY": {"zh-CN": "请至少选择一项配置", "en": "Select at least one configuration"},
    "BATCH_SELECTION_LIMIT": {"zh-CN": "每次最多处理 20 项配置", "en": "You can process up to 20 configurations at a time"},
    "CART_BATCH_SELECTION_LIMIT": {"zh-CN": "每次最多处理 100 个购物车项目", "en": "You can process up to 100 cart items at a time"},
    "CART_ITEM_REFERENCE_INVALID": {"zh-CN": "购物车项目类型或编号无效", "en": "A cart item type or identifier is invalid"},
    "CONFIG_ACCESS_DENIED": {"zh-CN": "无权操作该配置", "en": "You do not have access to this configuration"},
    "PDF_GENERATION_FAILED": {"zh-CN": "PDF 生成失败，请稍后重试", "en": "PDF generation failed. Try again later"},
    "SHARE_CREATION_FAILED": {"zh-CN": "分享码生成失败，请重试", "en": "Could not create a share code. Try again"},
    "CATALOG_PRODUCT_NOT_FOUND": {"zh-CN": "设备不存在或已被删除", "en": "The product does not exist or was removed"},
    "CATALOG_REQUIRED_FIELD": {"zh-CN": "请完整填写设备型号和中英文名称", "en": "Complete the model and bilingual product names"},
    "CATALOG_MODEL_DUPLICATE": {"zh-CN": "该设备型号已被其他设备使用", "en": "This product model is already used by another product"},
    "CATALOG_TRANSLATION_REQUIRED": {"zh-CN": "中文和英文名称均不能为空", "en": "Both Chinese and English names are required"},
    "CATALOG_TRANSLATION_STATUS_INVALID": {"zh-CN": "翻译状态无效", "en": "The translation status is invalid"},
    "CATALOG_TRANSLATION_REQUEST_TOO_LARGE": {"zh-CN": "一次提交的翻译内容过多", "en": "The translation draft request is too large"},
    "CATALOG_REQUEST_TOO_LARGE": {"zh-CN": "提交内容过大，请减少图片以外的文本或配置数量", "en": "The catalog request is too large. Reduce the submitted text or option count"},
    "CATALOG_VALIDATION_FAILED": {"zh-CN": "目录资料格式不正确，请检查标记的字段", "en": "Some catalog fields are invalid. Review the marked fields"},
    "CATALOG_OPTION_DUPLICATE": {"zh-CN": "同一配置不能重复选择", "en": "The same configuration cannot be selected more than once"},
    "CATALOG_OPTION_NOT_AVAILABLE": {"zh-CN": "部分可选配置不存在、已停用或不属于可选配置目录", "en": "Some optional configurations are missing, disabled, or outside the optional catalog"},
    "CATALOG_VERSION_CONFLICT": {"zh-CN": "设备已在其他窗口修改，请重新加载后再保存", "en": "The product changed in another window. Reload it and try again"},
    "CATALOG_PRICE_INVALID": {"zh-CN": "价格必须是大于或等于 0 的有效金额", "en": "Prices must be valid amounts greater than or equal to zero"},
    "CATALOG_FREE_PRICE_CONFLICT": {"zh-CN": "免费选项不能同时填写价格", "en": "A free option cannot also contain a price"},
    "CATALOG_CURRENCY_INVALID": {"zh-CN": "货币仅支持人民币或美元", "en": "Only CNY and USD are supported"},
    "CATALOG_TYPE_INVALID": {"zh-CN": "目录类型无效", "en": "The catalog type is invalid"},
    "CATALOG_CATEGORY_NOT_FOUND": {"zh-CN": "配置分类不存在或已被删除", "en": "The catalog category does not exist or was removed"},
    "CATALOG_CATEGORY_NOT_AVAILABLE": {"zh-CN": "配置分类已停用或不可用于添加项目", "en": "The catalog category is disabled or unavailable"},
    "CATALOG_CATEGORY_NOT_LEAF": {"zh-CN": "只能在最末级分类中添加配置项目", "en": "Catalog items can only be added to a leaf category"},
    "CATALOG_CATEGORY_PARENT_INVALID": {"zh-CN": "只能在可选配置目录下添加二级分类", "en": "A subcategory can only be added under Optional Configurations"},
    "CATALOG_CATEGORY_DUPLICATE": {"zh-CN": "同一目录下已存在相同分类名称", "en": "A category with this name already exists in the same catalog"},
    "CATALOG_CATEGORY_PROTECTED": {"zh-CN": "系统顶层目录不能修改或删除", "en": "System root categories cannot be changed or deleted"},
    "CATALOG_CATEGORY_NOT_EMPTY": {"zh-CN": "分类仍包含子分类或配置项目，不能删除", "en": "Move or remove child categories and items before deleting this category"},
    "CATALOG_ITEM_NOT_FOUND": {"zh-CN": "配置项目不存在或已被删除", "en": "The catalog item does not exist or was removed"},
    "CATALOG_ITEM_NOT_AVAILABLE": {"zh-CN": "维修工具或设备附件不存在、已停用或不可购买", "en": "The tool or accessory is missing, disabled, or unavailable"},
    "CATALOG_CODE_REQUIRED": {"zh-CN": "请填写配置编号", "en": "Enter a catalog item code"},
    "CATALOG_CODE_DUPLICATE": {"zh-CN": "该配置编号已被其他项目使用", "en": "This catalog item code is already in use"},
    "CATALOG_ITEM_TYPE_CHANGE_FORBIDDEN": {"zh-CN": "已被设备使用的配置不能改为维修工具或设备附件", "en": "An item used by a product cannot be moved to a different catalog type"},
    "CATALOG_MEDIA_NOT_FOUND": {"zh-CN": "上传的图片不存在或已失效，请重新上传", "en": "The uploaded image is missing or expired. Upload it again"},
    "CATALOG_QUANTITY_INVALID": {"zh-CN": "数量必须在 1 至 999 之间", "en": "Quantity must be between 1 and 999"},
    "CATALOG_CART_ITEM_NOT_FOUND": {"zh-CN": "购物车中的工具或附件不存在或已被删除", "en": "The tool or accessory is no longer in the cart"},
    "CATALOG_CART_VERSION_CONFLICT": {"zh-CN": "购物车项目已在其他窗口修改，请重新加载", "en": "The cart item changed in another window. Reload and try again"},
    "PRODUCT_COLOR_REQUIRED": {"zh-CN": "设备至少需要保留一个启用的外观颜色", "en": "Keep at least one enabled product color"},
    "PRODUCT_COLOR_DUPLICATE": {"zh-CN": "外观颜色存在重复项", "en": "A product color is duplicated"},
    "PRODUCT_COLOR_INVALID": {"zh-CN": "颜色值必须使用六位十六进制格式", "en": "Use a six-digit hexadecimal color value"},
    "PRODUCT_COLOR_DEFAULT_INVALID": {"zh-CN": "启用的外观颜色必须且只能设置一个默认项", "en": "Enabled colors must have exactly one default"},
    "PRODUCT_IMAGE_SIZE_INVALID": {"zh-CN": "图片宽高必须是大于 0 的有效数值", "en": "Image dimensions must be greater than zero"},
    "PRODUCT_SPECIFICATION_INCOMPLETE": {"zh-CN": "参数表每一项都需要填写中英文项目和中英文数据", "en": "Each specification requires bilingual labels and values"},
    "PRODUCT_SPECIFICATION_DUPLICATE": {"zh-CN": "参数表存在重复项目", "en": "A specification row is duplicated"},
    "PRODUCT_SPECIFICATION_INVALID": {"zh-CN": "参数表项目不属于当前设备", "en": "The specification does not belong to this product"},
    "BASE_OPTION_GROUP_INVALID": {"zh-CN": "基本配置分组重复或类型无效", "en": "A base-option group is duplicated or invalid"},
    "BASE_OPTION_GROUP_REQUIRED": {"zh-CN": "设备必须配置电机和电源分组", "en": "The product must include motor and power groups"},
    "BASE_OPTION_REQUIRED": {"zh-CN": "已启用的基本配置分组至少需要一个选项", "en": "An enabled base-option group requires at least one option"},
    "BASE_OPTION_DUPLICATE": {"zh-CN": "基本配置选项重复", "en": "A base option is duplicated"},
    "BASE_OPTION_NOT_AVAILABLE": {"zh-CN": "所选基本配置不存在、已停用或不属于当前设备", "en": "The selected base option is missing, disabled, or belongs to another product"},
    "BASE_OPTION_PRICE_ROLE_INVALID": {"zh-CN": "电机和通道价格应填写在基础价格方案中", "en": "Motor and channel prices must be entered in a base-price variant"},
    "PRICE_VARIANT_REQUIRED": {"zh-CN": "设备至少需要一个基础价格方案", "en": "The product requires at least one base-price variant"},
    "PRICE_VARIANT_OPTION_REQUIRED": {"zh-CN": "价格方案必须选择电机或通道", "en": "A price variant must select a motor or channel"},
    "PRICE_VARIANT_OPTION_INVALID": {"zh-CN": "价格方案引用了无效的电机或通道", "en": "The price variant references an invalid motor or channel"},
    "PRICE_VARIANT_DUPLICATE": {"zh-CN": "同一电机和通道组合只能有一个价格方案", "en": "A motor and channel combination can have only one price variant"},
    "PRICE_VARIANT_COVERAGE_INVALID": {"zh-CN": "每个已启用的电机和通道组合都必须有且只有一个价格方案", "en": "Every enabled motor and channel combination must have exactly one price variant"},
    "PRICE_VARIANT_NOT_FOUND": {"zh-CN": "当前电机和通道组合尚未设置基础价格", "en": "No base price is configured for this motor and channel combination"},
}


class AccountError(Exception):
    def __init__(
        self,
        code: str,
        *,
        field: Optional[str] = None,
        status_code: int = 422,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.code = code
        self.field = field
        self.status_code = status_code
        self.params = params or {}
        self.headers = headers or {}
        super().__init__(self.message("zh-CN"))

    def message(self, language: str = "zh-CN") -> str:
        messages = ACCOUNT_ERROR_MESSAGES.get(self.code, {})
        template = messages.get("en" if language.lower().startswith("en") else "zh-CN") or self.code
        try:
            return template.format(**self.params)
        except (KeyError, ValueError):
            return template
