"""业务枚举值：供业务判断、入库及字典注册共同引用，不依赖字典服务。"""

from enum import Enum, IntEnum, StrEnum, unique

from app.common.enums import TicketTypeEnum as TicketTypeEnum


@unique
class EnableStatus(IntEnum):
    """EnableStatus 业务编码。"""

    ENABLED = 0
    DISABLED = 1


@unique
class CodeGenerationStatus(IntEnum):
    """CodeGenerationStatus 业务编码。"""

    NOT_GENERATED = 0
    GENERATED = 1


@unique
class LoginStatus(IntEnum):
    """LoginStatus 业务编码。"""

    SUCCESS = 1
    FAILURE = 2


@unique
class MenuClient(StrEnum):
    """MenuClient 业务编码。"""

    PC = "pc"
    APP = "app"


@unique
class BooleanValue(Enum):
    """BooleanValue 业务编码。"""

    TRUE = True
    FALSE = False


@unique
class TicketStatus(IntEnum):
    """TicketStatus 业务编码。"""

    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    CLOSED = 3


@unique
class VersionStatus(IntEnum):
    """VersionStatus 业务编码。"""

    DRAFT = 0
    PUBLISHED = 1
    ROLLED_BACK = 2


@unique
class JobStatus(IntEnum):
    """JobStatus 业务编码。"""

    RUNNING = 0
    PAUSED = 1
    STOPPED = 2


@unique
class ExecutionStatus(StrEnum):
    """ExecutionStatus 业务编码。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@unique
class TriggerType(StrEnum):
    """TriggerType 业务编码。"""

    CRON = "cron"
    INTERVAL = "interval"
    DATE = "date"
    MANUAL = "manual"


@unique
class JobStore(StrEnum):
    """JobStore 业务编码。"""

    DEFAULT = "default"
    SQLALCHEMY = "sqlalchemy"
    MEMORY = "memory"


@unique
class JobExecutor(StrEnum):
    """JobExecutor 业务编码。"""

    DEFAULT = "default"
    THREAD_POOL = "threadpool"
    PROCESS_POOL = "processpool"


@unique
class StorageLinkExpiry(IntEnum):
    """StorageLinkExpiry 业务编码。"""

    ONE_HOUR = 3600
    ONE_DAY = 86400
    THREE_DAYS = 259200
    SEVEN_DAYS = 604800


@unique
class StorageProtocol(str, Enum):
    """StorageProtocol 业务编码。"""

    FTP = "ftp"
    FTPS = "ftps"
    SFTP = "sftp"
    S3 = "s3"
    OBS = "obs"
    OSS = "oss"
    COS = "cos"
    LOCAL = "local"


@unique
class StorageEncryption(IntEnum):
    """StorageEncryption 业务编码。"""

    PLAIN = 0
    TLS_IF_AVAILABLE = 1
    REQUIRE_EXPLICIT_TLS = 2
    REQUIRE_IMPLICIT_TLS = 3


@unique
class StorageConnectionMode(IntEnum):
    """StorageConnectionMode 业务编码。"""

    DEFAULT = 0
    ACTIVE = 1
    PASSIVE = 2


@unique
class StorageEncoding(StrEnum):
    """StorageEncoding 业务编码。"""

    UTF8 = "UTF-8"
    GBK = "GBK"


@unique
class TransferMode(StrEnum):
    """TransferMode 业务编码。"""

    PARALLEL = "parallel"
    CHAIN = "chain"


@unique
class TransferSourceMode(StrEnum):
    """TransferSourceMode 业务编码。"""

    REMOTE = "remote"
    LOCAL = "local"


@unique
class TransportMode(StrEnum):
    """TransportMode 业务编码。"""

    STREAM = "stream"
    MULTIPART = "multipart"


@unique
class OperationStatus(IntEnum):
    """OperationStatus 业务编码。"""

    SUCCESS = 1
    FAILURE = 0


@unique
class MenuType(IntEnum):
    """MenuType 业务编码。"""

    CATALOG = 1
    MENU = 2
    BUTTON = 3
    EXTERNAL_LINK = 4


@unique
class MenuScope(StrEnum):
    """MenuScope 业务编码。"""

    WEB = "web"
    APP = "app"


@unique
class DataScope(IntEnum):
    """DataScope 业务编码。"""

    SELF = 1
    DEPARTMENT_AND_CHILDREN = 2
    ALL = 3


@unique
class TransferStatus(StrEnum):
    """TransferStatus 业务编码。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


@unique
class StorageRegionS3(StrEnum):
    """StorageRegionS3 业务编码。"""

    US_EAST_1 = "us-east-1"
    US_WEST_2 = "us-west-2"
    AP_NORTHEAST_1 = "ap-northeast-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"
    AP_SOUTH_1 = "ap-south-1"


@unique
class StorageRegionOSS(StrEnum):
    """StorageRegionOSS 业务编码。"""

    CN_HANGZHOU = "cn-hangzhou"
    CN_BEIJING = "cn-beijing"
    CN_SHANGHAI = "cn-shanghai"
    CN_SHENZHEN = "cn-shenzhen"
    CN_HONGKONG = "cn-hongkong"


@unique
class StorageRegionCOS(StrEnum):
    """StorageRegionCOS 业务编码。"""

    AP_BEIJING = "ap-beijing"
    AP_SHANGHAI = "ap-shanghai"
    AP_GUANGZHOU = "ap-guangzhou"
    AP_CHENGDU = "ap-chengdu"
    AP_SINGAPORE = "ap-singapore"


@unique
class StorageRegionOBS(StrEnum):
    """StorageRegionOBS 业务编码。"""

    CN_NORTH_1 = "cn-north-1"
    CN_NORTH_4 = "cn-north-4"
    CN_EAST_2 = "cn-east-2"
    CN_SOUTH_1 = "cn-south-1"


@unique
class BusinessStatus(IntEnum):
    """BusinessStatus 业务编码。"""

    NORMAL = 0
    DISABLED = 1


@unique
class DictionarySource(StrEnum):
    """DictionarySource 业务编码。"""

    DATABASE = "database"
    ENUM = "enum"
