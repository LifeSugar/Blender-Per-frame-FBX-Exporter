# FBX Sequence Exporter

## 项目简介
FBX Sequence Exporter 是一个 Blender 插件，用于将所选对象导出为按帧拆分的 FBX 序列，或一键导出每个对象单独的 FBX 文件。插件内置命名、排序、坐标轴与缩放等常用选项，并提供实时进度与取消能力，适合动画、游戏以及 DCC 流水线中的批量 FBX 导出场景。

- 插件作者：GouGouTang ([LifeSugar/Blender-Per-frame-FBX-Exporter](https://github.com/LifeSugar/Blender-Per-frame-FBX-Exporter))
- 当前版本：v1.7
- 推荐 Blender：4.0 或更新版本（最低兼容 2.83，manifest 目标 4.2+）
- 许可证：GPL-3.0-or-later

## 功能亮点
- **两种导出模式**：
  - *Per-Frame Sequence*：对所选对象的每一帧分别生成 FBX。
  - *Per-Object*：在当前帧为每个对象导出一个独立 FBX。
- **可控命名**：支持自定义前缀、对象名拼接、序号位数与帧号补零，方便导入到引擎或后续工具。
- **排序策略**：可按 Outliner 层级、对象名称或当前选择顺序导出，兼顾场景结构与自定义流程。
- **曲线临时转网格**：导出时可自动评估曲线对象并生成临时网格，确保 FBX 中包含可渲染几何。
- **动画控制**：可配置导出帧区间、帧间隔、是否烘焙动画与应用 Mesh Modifier。
- **坐标与尺度**：暴露 Blender FBX 导出常用选项（全局缩放、轴向、Bake Space Transform、Apply Scalings）。
- **进度反馈与可取消**：状态栏与侧边栏实时显示进度，并可在导出过程中按 ESC 或点击 Cancel 终止。

## 安装说明
1. 克隆或下载本仓库，保留目录结构（`__init__.py` 与 `blender_manifest.toml`）。
2. 在 Blender 中打开 `Edit > Preferences > Add-ons`。
3. 点击右上角的 `Install...`，选择仓库压缩包（或将文件夹打包后选择该压缩包）。
4. 勾选 `FBX Sequence Exporter` 启用插件。
5. 启用后可在 3D 视图按 `N` 打开侧边栏，在 `FBX Exporter` 标签页中找到插件面板。

> **手动安装**：也可将仓库文件夹复制到 `%APPDATA%/Blender Foundation/Blender/<版本号>/scripts/addons/`，重启 Blender 并在偏好设置中启用。

## 快速上手
1. 在场景中选择需要导出的对象（支持 Mesh、Armature、Empty、Curve 等）。
2. 打开 `FBX Exporter` 面板，设置 `Export Folder`（支持相对路径，如 `//FBX_Sequence/` 指向当前 blend 文件所在目录）。
3. 选择 `Export Mode`：
   - `Per-Frame Sequence`：设置 `Start Frame`、`End Frame` 与 `Frame Interval`。
   - `Per-Object`：若需要控制对象顺序或序号位数，调整 `Object Order` 与 `Object Index Digits`。
4. 配置命名与变换选项：
   - `Naming Mode` / `Custom Prefix`。
   - `Scale`、`Apply Scalings`、`Forward`/`Up`、`Bake Space Transform`。
   - `Use Mesh Modifiers`、`Bake Animation`。
5. 点击 `Export FBX` 开始批量导出；面板与状态栏会展示进度与当前处理对象。

### 导出过程中
- 进度条全部完成后，插件会还原原始选择与活动对象，并在信息栏提示导出成功。
- 如需中止导出，可在面板点击 `Cancel` 或按下 `ESC`。

## 选项速查表
| 选项 | 区域 | 说明 |
| --- | --- | --- |
| Export Mode | Export Mode | 切换按帧序列或按对象导出模式。|
| Object Order | Export Mode (`Per-Object`) | Outliner 深度优先、对象名排序或当前选择顺序。|
| Object Index Digits | Export Mode (`Per-Object`) | 控制导出文件序号补零位数。|
| Naming Mode | File Naming | `PREFIX` 使用前缀；`PREFIX_PLUS_OBJ` 使用前缀+对象名。空前缀时回退到对象名。|
| Custom Prefix | File Naming | 自定义文件名前缀，导出时自动去除非法字符。|
| Export Folder | Main | 导出目录；支持相对路径（以 `//` 开头）与绝对路径。|
| Match Scene Frame Range | Main | 一键同步场景帧区间到导出设置。|
| Start/End Frame | Main (`Sequence`) | 控制序列导出的帧范围。|
| Frame Interval | Main (`Sequence`) | 设置帧间隔（每 1/2/3 帧）。|
| Scale / Apply Scalings | Transform | 对应 Blender FBX 导出缩放选项。|
| Forward / Up | Transform | 指定 FBX 前向与上向轴。|
| Bake Space Transform | Transform | 保留 FBX 的变换空间（减少坐标偏差）。|
| Use Mesh Modifiers | Other Options | 导出前应用 Mesh Modifier。|
| Bake Animation | Other Options | 控制是否烘焙动画数据。|

## 常见问题
- **导出路径无效**：当 `Export Folder` 留空或指向 `//` 时导出会失败；请指定有效的绝对或相对路径。
- **曲线对象未导出几何**：插件自动在导出时将曲线评估为网格，无需手动转 Mesh；若仍为空，请确认曲线有可渲染几何并在当前帧处于可见状态。
- **进度条不显示**：Blender 旧版 UI 不支持进度控件时会退回到滑块显示，这是正常行为。

## 开发与扩展
- `__init__.py` 包含全部插件代码，可以直接在 Blender Text Editor 中运行 `register()` 调试。
- `blender_manifest.toml` 用于 Blender Extension 平台打包，可根据项目需求更新 `name`、`tagline` 等字段。
- 修改后可使用 `zip -r FBXSequenceExporter.zip .`（或使用系统压缩）打包部署。

## 许可证
本项目根据 GPL-3.0-or-later 许可发布。分发时请附带许可证文本，并在修改后保留原作者信息。
