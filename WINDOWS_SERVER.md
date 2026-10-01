# 把本机当服务器跑（Windows 常驻部署）

放弃云服务器，直接让这台 Windows 机器 7x24 运行监控看板。

## 已完成的配置

| 项目 | 状态 |
| :--- | :--- |
| 系统级 Python 3.12.10（专用运行时） | 已安装 + requests |
| 看板访问口令 | 已生成，见 `auth.conf` |
| 服务启动脚本（含崩溃自重启） | `run_server.bat` |
| IPv6 变化检测与 DDNS | `ddns_update.py` |
| 电源改为永不睡眠 | 已设置 |
| 开机自启 / 防火墙 / 固定 IPv6 | 需管理员，见下 |

## 还需要你做两件事（都要管理员权限）

**1. 双击 `install_server.bat`（右键 → 以管理员身份运行）**

它会创建开机自启任务、放行防火墙 8000 端口、禁用 IPv6 临时地址（让外网地址稳定）、电源改常开。做完之后服务就会跑起来，重启电脑也会自动恢复。

**2.（可选）配动态域名**

家庭宽带的 IPv6 前缀会变，直接记 IP 会失效。到 [dynv6.com](https://dynv6.com) 免费注册一个域名（如 `bili-home.dynv6.net`），把 zone 和 token 填进 `ddns.conf`，之后手机上永远访问同一个网址。

不配也能用：`ddns_update.py` 检测到地址变化时会用项目已有的推送通道把新地址发到你手机。

## 怎么访问

| 场景 | 地址 |
| :--- | :--- |
| 本机 | http://localhost:8000 （免口令） |
| 家里其他设备 | http://192.168.10.82:8000 |
| 手机 / 外网 | http://[你的IPv6]:8000 或 http://你的域名:8000 |

首次从外网访问会要求输入口令，输入正确后浏览器记住一年，之后直接进。

**查看当前 IPv6：**

```bash
python ddns_update.py --show
```

## 常用命令

```bat
schtasks /run   /tn BiliMonitor        :: 立即启动
stop_server.bat                        :: 停止服务
schtasks /query /tn BiliMonitor /v     :: 查看任务状态
type logs\server.log                   :: 看日志
python ddns_update.py --force          :: 强制刷新一次动态域名
```

## 改访问口令

编辑 `auth.conf` 里的 `DASHBOARD_TOKEN`，然后 `stop_server.bat` 再启动即可。
**留空等于完全开放**——外网部署时不要这么做。

## 注意事项

- **口令走的是明文 HTTP**，不要在公共 Wi-Fi 下用；要 HTTPS 得再套一层反代。
- **断电恢复**：BIOS 里开「断电后自动开机」（AC Recovery / Power On After Power Loss），否则停电后需手动开机。
- **路由器绑定静态 DHCP**：把 `192.168.10.82` 固定给这台机器，避免内网 IP 变了。
- **历史数据会增长**：`3c_products_history.csv` 按 30 分钟巡检约 1.5MB/天，一年后 500MB+，
  `/api/data` 每次全量解析会变慢。建议把巡检间隔调到 1 小时，或定期归档历史文件。
- **电费**：机器常开的成本就是电费。笔记本/小主机约 3-6 元/月，普通台式机 15-25 元/月，
  高性能游戏台式机可能 30-50 元/月——不一定比云服务器省，取决于机器功耗。
