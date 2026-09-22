# Command & Conquer Trainers

Windows 11 单人修改器项目，按游戏分为三个独立目录：

| 目录 | 游戏 | 状态 |
|---|---|---|
| [`RedAlert2`](RedAlert2) | 红色警戒2《尤里的复仇》 | 支持已验证的 CnCNet / Ares / Phobos 版本 |
| [`RedAlert3`](RedAlert3) | 红色警戒3原版与《起义时刻》 | 支持原版 1.13、起义时刻 1.01 |
| [`CommandConquer3`](CommandConquer3) | 命令与征服3原版与《凯恩之怒》 | 支持原版 1.09/1.10、凯恩之怒 1.02/1.03 |

三个修改器只用于单人战役或离线遭遇战。程序不会修改游戏文件；连接时会校验进程、游戏模块 SHA-256、映像基址、战局对象和补丁原始指令，正常退出时恢复本程序安装的指令。

## 红色警戒2：尤里的复仇

源码和成品位于 [`RedAlert2`](RedAlert2)。可直接下载 [`YRTrainer-Portable.exe`](RedAlert2/dist/YRTrainer-Portable.exe)。进入单人地图后连接游戏，打开 Num Lock，热键只在游戏前台响应。

| 小键盘 | 功能 |
|---|---|
| `*` | 连接游戏／断开并恢复 |
| `1` | 增加或设置金钱 |
| `2` | 开关我方额外供电 |
| `3` | 所选单位回血 |
| `4` | 所选单位加入普通伤害保护 |
| `5` | 所选单位归我 |
| `6` | 地图全开 |
| `7` | 开关我方建筑瞬间建造 |
| `-` | 开关我方单位快速生产 |
| `8` | 全科技 |
| `9` | 远距离放置 |
| `0` | 清空单位保护 |
| `+` | 我方超级武器立即就绪 |
| `.` | 开关我方超级武器无冷却 |

红警2实现参考：

- [AdjWang/RA2YurisRevengeTrainer](https://github.com/AdjWang/RA2YurisRevengeTrainer)
- [Phobos-developers/YRpp](https://github.com/Phobos-developers/YRpp)
- [CnCNet/yrpp-spawner](https://github.com/CnCNet/yrpp-spawner)

当前红警2 EXE SHA-256：`3475506E7C6299F8CB24FD7028C9551BA31FEAFEB76F89A1C99908A6713593E8`。

## 红色警戒3与起义时刻

源码和成品位于 [`RedAlert3`](RedAlert3)。可直接下载 [`RA3Trainer-Portable.exe`](RedAlert3/dist/RA3Trainer-Portable.exe)，无需安装 Python。

支持的游戏模块：

- 原版 `ra3_1.13.game`：`E4016847423869B3D4E6A5AE4C74228F2083C65E34416104635602C5526B3EEE`
- 起义时刻 `ra3ep1_1.1.game`：`B1DA83EFD229570BAB9DE3A14E48B2D1E6128E302BD52384858FA8A413AE330B`

使用方法：

1. 启动原版或《起义时刻》，进入单人战役或遭遇战；不要同时运行两款游戏。
2. 启动 `RA3Trainer-Portable.exe`，点击“连接游戏”或按小键盘 `*`。
3. 打开 Num Lock。其他热键只在游戏窗口位于前台时响应。

| 小键盘 | 功能 |
|---|---|
| `*` | 连接游戏／断开并恢复 |
| `1` | 将金钱设为界面填写值，默认 100000 |
| `2` | 开关无限电力 |
| `3` | 开关无限支援协议点 999 |
| `4` | 开关单位与建筑瞬间建造 |
| `5` | 开关超级武器／支援能力无冷却 |
| `6` | 开关我方步兵、车辆与建筑免普通攻击伤害 |
| `0` | 关闭全部功能 |

原版 1.13 已在苏军战役中验证金钱、电力、协议点、单位和建筑瞬间建造、磁力卫星无冷却，以及步兵、车辆和建筑免伤。《起义时刻》1.01 已在盟军遭遇战中验证全部上述功能。免伤会排除火焰、残骸等临时效果对象，敌军仍会正常受伤。

全图可见没有加入红警3修改器：现有实现只能清除地形黑幕，无法可靠显示半透明阴影区域内的敌军。

当前红警3 EXE SHA-256：`98F4EA39118D10D082947CEDB38F783B2B3E0A74BD67D2011D3C0DC33D178E5A`。

## 命令与征服3与凯恩之怒

源码和成品位于 [`CommandConquer3`](CommandConquer3)。可直接下载 [`CNC3Trainer-Portable.exe`](CommandConquer3/dist/CNC3Trainer-Portable.exe)，无需安装开发工具。

支持的游戏模块：

- 原版 1.09：`8EE145C5F6DF2A8C853E073D8F43294F09EC9669150AFDF3E9644C830A19D15A`
- 原版 1.10：`AF568A89B6D0D4F69EC690CF1D443539CB15AFE197B96AC3FC5BF0EC0A56D141`
- 凯恩之怒 1.02：`ED685B85CF2646FE79CEE57543A992B0165065F1FD2B59C31B1A200C6C7A0E9A`
- 凯恩之怒 1.03：`1716C954AB80CF05752F4A4A467D34313A95A55A408718270F96382E330572F3`

功能包括设置或保持最低资金、无限电力、我方单位与建筑无敌、剧情初始单位保护、护盾不减、快速生产，以及《凯恩之怒》全球征服资金。热键只在游戏窗口位于前台时响应，读档或进入新地图会自动关闭功能。

原版 1.10 已在 GDI 战役中完成实机验证。当前 C&C3 EXE SHA-256：`BFAB88B51B57DB15888620C2FD837D2A7C222DE2962B59ABFF6FEACA8A11C6ED`。

## 构建

三个目录均包含独立的 `build.ps1`。红警2与红警3构建使用 Python 3.12；C&C3 修改器使用 Windows 自带的 .NET Framework C# 编译器。在仓库根目录运行：

```powershell
.\build-all.ps1
```

红警3界面使用 Windows 原生控件；运行成品不依赖 Python 或 Tk。运行时 x86 指令由 [Keystone Engine](https://github.com/keystone-engine/keystone) 生成。
