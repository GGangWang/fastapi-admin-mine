-- 资源纳管系统：仅更新仍使用上游默认值的品牌参数。
-- 执行后重启后端以刷新 Redis 参数缓存，再退出并重新登录。
BEGIN;
UPDATE sys_param SET config_value = '/api/v1/static/image/logo.svg' WHERE config_key = 'logo_url' AND config_value = 'https://service.res-nexus.com/api/v1/static/image/logo.svg';
UPDATE sys_param SET config_value = '/api/v1/static/image/favicon.svg' WHERE config_key = 'favicon' AND config_value = 'https://service.res-nexus.com/api/v1/static/image/favicon.ico';
UPDATE sys_param SET config_value = '/api/v1/static/image/background.svg' WHERE config_key = 'login_bg' AND config_value = 'https://service.res-nexus.com/api/v1/static/image/background.svg';
UPDATE sys_param SET config_value = 'ResNexus' WHERE config_key = 'copyright' AND config_value = 'Copyright © 2025-2027 service.res-nexus.com 版权所有';
UPDATE sys_param SET config_value = '' WHERE config_key = 'keep_record' AND config_value = '陕ICP备2025069493号-1';
UPDATE sys_param SET config_value = '/fastlink/tutorial' WHERE config_key = 'help_doc' AND config_value = 'https://docs.res-nexus.com';
UPDATE sys_param SET config_value = '' WHERE config_key = 'privacy' AND config_value = 'https://res-nexus.com/privacy';
UPDATE sys_param SET config_value = '' WHERE config_key = 'clause' AND config_value = 'https://res-nexus.com/clause';
UPDATE sys_param SET config_value = '' WHERE config_key = 'git_code' AND config_value = 'https://github.com/res-nexus/res-nexus';
UPDATE sys_param SET config_value = 'ResNexus' WHERE config_key = 'sys_name' AND config_value = '资源纳管系统';
UPDATE sys_param SET config_value = '统一纳管资源，提升管理效率' WHERE config_key = 'login_title' AND config_value = '一款兼具设计美学与高效开发的后台系统';
UPDATE sys_param SET config_value = '集中管理资源信息、访问权限与运行状态，让资源管理清晰可控。' WHERE config_key = 'login_subtitle' AND config_value = '提供安全、高效、可扩展的管理解决方案，助力企业数字化转型与业务增长。';
COMMIT;

-- Upgrade installations already using the previous product title.
BEGIN;
UPDATE sys_param SET config_value = 'ResNexus' WHERE config_key = 'sys_name' AND config_value IN ('资源纳管系统', 'Resource Management System');
UPDATE sys_param SET config_value = 'ResNexus' WHERE config_key = 'copyright' AND config_value IN ('资源纳管系统', 'Resource Management System');
COMMIT;
