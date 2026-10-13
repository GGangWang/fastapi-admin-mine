"""固定业务字典标签及样式；业务值统一引用 app.common.dict_values。"""

from app.common.dict_values import (
    BooleanValue,
    CodeGenerationStatus,
    DataScope,
    EnableStatus,
    ExecutionStatus,
    JobExecutor,
    JobStatus,
    JobStore,
    LoginStatus,
    MenuClient,
    MenuScope,
    MenuType,
    OperationStatus,
    StorageConnectionMode,
    StorageEncoding,
    StorageEncryption,
    StorageLinkExpiry,
    StorageProtocol,
    StorageRegionCOS,
    StorageRegionOBS,
    StorageRegionOSS,
    StorageRegionS3,
    TicketStatus,
    TicketTypeEnum,
    TransferMode,
    TransferSourceMode,
    TransferStatus,
    TransportMode,
    TriggerType,
    VersionStatus,
)

from .constants import DictType


def register_frontend_dictionaries(registry, EnumDictionary, DictItem):
    registry.register(
        EnumDictionary(
            DictType.SYS_ENABLE_STATUS,
            "启停状态",
            (DictItem(EnableStatus.ENABLED.value, "启用", list_class="success", sort=0), DictItem(EnableStatus.DISABLED.value, "停用", list_class="danger", sort=1)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.GEN_CODE_STATUS, "代码生成状态", (DictItem(CodeGenerationStatus.NOT_GENERATED.value, "未生成", sort=0), DictItem(CodeGenerationStatus.GENERATED.value, "已生成", sort=1))
        )
    )
    registry.register(EnumDictionary(DictType.SYS_LOGIN_STATUS, "登录状态", (DictItem(LoginStatus.SUCCESS.value, "成功", sort=0), DictItem(LoginStatus.FAILURE.value, "失败", sort=1))))
    registry.register(EnumDictionary(DictType.SYS_MENU_CLIENT, "菜单终端", (DictItem(MenuClient.PC.value, "Web 菜单", sort=0), DictItem(MenuClient.APP.value, "APP 菜单", sort=1))))
    registry.register(EnumDictionary(DictType.SYS_MENU_STATUS, "菜单状态", (DictItem(EnableStatus.ENABLED.value, "启用", sort=0), DictItem(EnableStatus.DISABLED.value, "禁用", sort=1))))
    registry.register(EnumDictionary(DictType.SYS_ON_OFF, "开关", (DictItem(BooleanValue.TRUE.value, "开启", sort=0), DictItem(BooleanValue.FALSE.value, "关闭", sort=1))))
    registry.register(
        EnumDictionary(
            DictType.SYS_TICKET_STATUS,
            "工单状态",
            (
                DictItem(TicketStatus.PENDING.value, "待处理", list_class="warning", sort=0),
                DictItem(TicketStatus.PROCESSING.value, "处理中", list_class="info", sort=1),
                DictItem(TicketStatus.COMPLETED.value, "已完成", list_class="success", sort=2),
                DictItem(TicketStatus.CLOSED.value, "已关闭", list_class="info", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_TICKET_TYPE,
            "工单类型",
            (
                DictItem(TicketTypeEnum.SUGGESTION.value, "💡 建议", list_class="success", sort=0),
                DictItem(TicketTypeEnum.BUG.value, "🐛 缺陷", list_class="danger", sort=1),
                DictItem(TicketTypeEnum.OPTIMIZE.value, "⚡ 优化", list_class="warning", sort=2),
                DictItem(TicketTypeEnum.OTHER.value, "📋 其他", list_class="info", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_VERSION_STATUS,
            "版本状态",
            (
                DictItem(VersionStatus.DRAFT.value, "草稿", list_class="info", sort=0),
                DictItem(VersionStatus.PUBLISHED.value, "已发布", list_class="success", sort=1),
                DictItem(VersionStatus.ROLLED_BACK.value, "已回滚", list_class="danger", sort=2),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_JOB_STATUS,
            "任务状态",
            (
                DictItem(JobStatus.RUNNING.value, "运行中", list_class="success", sort=0),
                DictItem(JobStatus.PAUSED.value, "暂停中", list_class="warning", sort=1),
                DictItem(JobStatus.STOPPED.value, "已停止", list_class="danger", sort=2),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_EXECUTION_STATUS,
            "任务执行状态",
            (
                DictItem(ExecutionStatus.PENDING.value, "待执行", list_class="info", sort=0),
                DictItem(ExecutionStatus.RUNNING.value, "执行中", list_class="primary", sort=1),
                DictItem(ExecutionStatus.SUCCESS.value, "成功", list_class="success", sort=2),
                DictItem(ExecutionStatus.FAILED.value, "失败", list_class="danger", sort=3),
                DictItem(ExecutionStatus.TIMEOUT.value, "超时", list_class="warning", sort=4),
                DictItem(ExecutionStatus.CANCELLED.value, "已取消", list_class="info", sort=5),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_TRIGGER_TYPE,
            "任务触发方式",
            (
                DictItem(TriggerType.CRON.value, "Cron表达式", list_class="info", sort=0),
                DictItem(TriggerType.INTERVAL.value, "时间间隔", list_class="info", sort=1),
                DictItem(TriggerType.DATE.value, "固定日期", list_class="info", sort=2),
                DictItem(TriggerType.MANUAL.value, "一次性任务", list_class="info", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_JOB_STORE,
            "任务存储方式",
            (DictItem(JobStore.DEFAULT.value, "默认(Redis)", sort=0), DictItem(JobStore.SQLALCHEMY.value, "数据库(Sqlalchemy)", sort=1), DictItem(JobStore.MEMORY.value, "内存(Memory)", sort=2)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_EXECUTOR,
            "任务执行器",
            (DictItem(JobExecutor.DEFAULT.value, "异步协程(事件循环)", sort=0), DictItem(JobExecutor.THREAD_POOL.value, "线程池", sort=1), DictItem(JobExecutor.PROCESS_POOL.value, "进程池", sort=2)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_NODE_TRIGGER_TYPE,
            "节点触发方式",
            (DictItem(TriggerType.CRON.value, "Cron表达式", sort=0), DictItem(TriggerType.INTERVAL.value, "时间间隔", sort=1), DictItem(TriggerType.DATE.value, "固定时间", sort=2)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_LINK_EXPIRY,
            "存储链接有效期",
            (
                DictItem(StorageLinkExpiry.ONE_HOUR.value, "1小时", sort=0),
                DictItem(StorageLinkExpiry.ONE_DAY.value, "1天", sort=1),
                DictItem(StorageLinkExpiry.THREE_DAYS.value, "3天", sort=2),
                DictItem(StorageLinkExpiry.SEVEN_DAYS.value, "7天", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_PROTOCOL,
            "存储协议",
            (
                DictItem(StorageProtocol.FTP.value, "FTP", list_class="primary", sort=0),
                DictItem(StorageProtocol.FTPS.value, "FTPS", list_class="success", sort=1),
                DictItem(StorageProtocol.SFTP.value, "SFTP", list_class="warning", sort=2),
                DictItem(StorageProtocol.S3.value, "S3", list_class="info", sort=3),
                DictItem(StorageProtocol.OBS.value, "OBS(华为云)", list_class="success", sort=4),
                DictItem(StorageProtocol.OSS.value, "OSS(阿里云)", list_class="danger", sort=5),
                DictItem(StorageProtocol.COS.value, "COS(腾讯云)", list_class="warning", sort=6),
                DictItem(StorageProtocol.LOCAL.value, "本地目录", list_class="info", sort=7),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_ENCRYPTION,
            "存储加密方式",
            (
                DictItem(StorageEncryption.PLAIN.value, "只要求明文", sort=0),
                DictItem(StorageEncryption.TLS_IF_AVAILABLE.value, "显式TLS(可用时)", sort=1),
                DictItem(StorageEncryption.REQUIRE_EXPLICIT_TLS.value, "要求显式TLS", sort=2),
                DictItem(StorageEncryption.REQUIRE_IMPLICIT_TLS.value, "要求隐式TLS", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_CONNECTION_MODE,
            "存储连接模式",
            (
                DictItem(StorageConnectionMode.DEFAULT.value, "默认", sort=0),
                DictItem(StorageConnectionMode.ACTIVE.value, "主动 (PORT)", sort=1),
                DictItem(StorageConnectionMode.PASSIVE.value, "被动 (PASV)", sort=2),
            ),
        )
    )
    registry.register(EnumDictionary(DictType.STORAGE_ENCODING, "存储编码", (DictItem(StorageEncoding.UTF8.value, "UTF-8", sort=0), DictItem(StorageEncoding.GBK.value, "GBK", sort=1))))
    registry.register(
        EnumDictionary(
            DictType.STORAGE_TRANSFER_MODE,
            "传输模式",
            (DictItem(TransferMode.PARALLEL.value, "多目标（同时传输到多个存储源）", sort=0), DictItem(TransferMode.CHAIN.value, "链式（按目标顺序逐跳传输）", sort=1)),
        )
    )
    registry.register(
        EnumDictionary(DictType.STORAGE_SOURCE_MODE, "传输来源", (DictItem(TransferSourceMode.REMOTE.value, "远端存储源", sort=0), DictItem(TransferSourceMode.LOCAL.value, "本地文件", sort=1)))
    )
    registry.register(
        EnumDictionary(DictType.STORAGE_WORKFLOW_MODE, "工作流模式", (DictItem(TransferMode.PARALLEL.value, "多目标（并行）", sort=0), DictItem(TransferMode.CHAIN.value, "链式（逐跳）", sort=1)))
    )
    registry.register(
        EnumDictionary(DictType.STORAGE_TRANSPORT_MODE, "传输方式", (DictItem(TransportMode.STREAM.value, "流式传输", sort=0), DictItem(TransportMode.MULTIPART.value, "分片传输", sort=1)))
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_OPERATION_STATUS,
            "操作结果",
            (DictItem(str(OperationStatus.SUCCESS.value), "成功", list_class="success", sort=0), DictItem(str(OperationStatus.FAILURE.value), "失败", list_class="danger", sort=1)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_MENU_TYPE,
            "菜单类型",
            (
                DictItem(str(MenuType.CATALOG.value), "目录", list_class="warning", sort=0),
                DictItem(str(MenuType.MENU.value), "菜单", list_class="success", sort=1),
                DictItem(str(MenuType.BUTTON.value), "按钮", list_class="danger", sort=2),
                DictItem(str(MenuType.EXTERNAL_LINK.value), "外链", list_class="info", sort=3),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_MENU_SCOPE, "菜单终端展示", (DictItem(MenuScope.WEB.value, "Web", list_class="primary", sort=0), DictItem(MenuScope.APP.value, "App", list_class="success", sort=1))
        )
    )
    registry.register(
        EnumDictionary(
            DictType.SYS_DATA_SCOPE,
            "数据权限",
            (
                DictItem(str(DataScope.SELF.value), "仅本人数据权限", list_class="primary", sort=0),
                DictItem(str(DataScope.DEPARTMENT_AND_CHILDREN.value), "本部门及以下数据权限", list_class="warning", sort=1),
                DictItem(str(DataScope.ALL.value), "全部数据权限", list_class="success", sort=2),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_TRANSFER_DISPLAY_MODE,
            "传输模式展示",
            (DictItem(TransferMode.CHAIN.value, "链式", list_class="warning", sort=0), DictItem(TransferMode.PARALLEL.value, "多目标", list_class="primary", sort=1)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_TRANSFER_STATUS,
            "传输状态",
            (
                DictItem(TransferStatus.PENDING.value, "等待中", list_class="info", sort=0),
                DictItem(TransferStatus.RUNNING.value, "传输中", list_class="warning", sort=1),
                DictItem(TransferStatus.SUCCESS.value, "成功", list_class="success", sort=2),
                DictItem(TransferStatus.FAILED.value, "失败", list_class="danger", sort=3),
                DictItem(TransferStatus.CANCELED.value, "已取消", list_class="info", sort=4),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.TASK_NODE_TRIGGER_DISPLAY,
            "节点触发摘要",
            (DictItem(TriggerType.CRON.value, "Cron", sort=0), DictItem(TriggerType.INTERVAL.value, "间隔", sort=1), DictItem(TriggerType.DATE.value, "单次", sort=2)),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_PROTOCOL_SHORT,
            "存储协议简称",
            (
                DictItem(StorageProtocol.LOCAL.value, "本地", sort=0),
                DictItem(StorageProtocol.FTP.value, "FTP", sort=1),
                DictItem(StorageProtocol.FTPS.value, "FTPS", sort=2),
                DictItem(StorageProtocol.SFTP.value, "SFTP", sort=3),
                DictItem(StorageProtocol.S3.value, "S3", sort=4),
                DictItem(StorageProtocol.OSS.value, "OSS", sort=5),
                DictItem(StorageProtocol.OBS.value, "OBS", sort=6),
                DictItem(StorageProtocol.COS.value, "COS", sort=7),
            ),
        )
    )
    registry.register(EnumDictionary(DictType.SYS_DEFAULT_FLAG, "默认标识", (DictItem(BooleanValue.TRUE.value, "默认", sort=0), DictItem(BooleanValue.FALSE.value, "否", sort=1))))
    registry.register(
        EnumDictionary(
            DictType.STORAGE_REGION_S3,
            "S3区域",
            (
                DictItem(StorageRegionS3.US_EAST_1.value, "us-east-1", sort=0),
                DictItem(StorageRegionS3.US_WEST_2.value, "us-west-2", sort=1),
                DictItem(StorageRegionS3.AP_NORTHEAST_1.value, "ap-northeast-1", sort=2),
                DictItem(StorageRegionS3.AP_SOUTHEAST_1.value, "ap-southeast-1", sort=3),
                DictItem(StorageRegionS3.AP_SOUTH_1.value, "ap-south-1", sort=4),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_REGION_OSS,
            "OSS区域",
            (
                DictItem(StorageRegionOSS.CN_HANGZHOU.value, "cn-hangzhou", sort=0),
                DictItem(StorageRegionOSS.CN_BEIJING.value, "cn-beijing", sort=1),
                DictItem(StorageRegionOSS.CN_SHANGHAI.value, "cn-shanghai", sort=2),
                DictItem(StorageRegionOSS.CN_SHENZHEN.value, "cn-shenzhen", sort=3),
                DictItem(StorageRegionOSS.CN_HONGKONG.value, "cn-hongkong", sort=4),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_REGION_COS,
            "COS区域",
            (
                DictItem(StorageRegionCOS.AP_BEIJING.value, "ap-beijing", sort=0),
                DictItem(StorageRegionCOS.AP_SHANGHAI.value, "ap-shanghai", sort=1),
                DictItem(StorageRegionCOS.AP_GUANGZHOU.value, "ap-guangzhou", sort=2),
                DictItem(StorageRegionCOS.AP_CHENGDU.value, "ap-chengdu", sort=3),
                DictItem(StorageRegionCOS.AP_SINGAPORE.value, "ap-singapore", sort=4),
            ),
        )
    )
    registry.register(
        EnumDictionary(
            DictType.STORAGE_REGION_OBS,
            "OBS区域",
            (
                DictItem(StorageRegionOBS.CN_NORTH_1.value, "cn-north-1", sort=0),
                DictItem(StorageRegionOBS.CN_NORTH_4.value, "cn-north-4", sort=1),
                DictItem(StorageRegionOBS.CN_EAST_2.value, "cn-east-2", sort=2),
                DictItem(StorageRegionOBS.CN_SOUTH_1.value, "cn-south-1", sort=3),
            ),
        )
    )
